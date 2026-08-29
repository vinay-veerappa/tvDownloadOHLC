"""Blinded Deliberate-Practice Simulation & Replay Engine (Milestone 2.3).

Enforces:
1. Anti-Memorization & Split Custody: BlindedDrillContext contains ONLY opaque drill_id and normalized bars.
   All ground truth fields are sealed in a private custody table (`drill_sealed_answers`) and never
   returned to the caller.  The in-process module no longer stores answers in module scope.
2. Persisted Split Custody: `drill_split_registry` stores the partition assignment of every
   (session_date, ticker) so the anti-memorization invariant survives process restarts.
3. Real Historical Market Replay: Slices authentic 1m historical bars up to 10:30 ET IB close.
   Fails closed with HistoricalDataUnavailableError on missing data (no silent synthetic fallbacks).
4. Commit Before Reveal: Evaluates adherence only after immutable answer lock in drill_attempts.
5. Deterministic Split Partitioning: Ensures assessment sessions cannot overlap training sessions.
6. Sealed Metadata: drill_type and dataset_split are read from the sealed custody record at
   submission; caller-declared classification is ignored.
7. Assessment Custody Token: with TRADING_BRAIN_DRILL_HMAC_KEY configured, contexts carry an
   HMAC-signed token over drill_id; ASSESSMENT submissions must present it (fail-closed without a key).
   NOTE: with a shared SQLite file this boundary is process- and DB-permission dependent; for
   production assessment, run generation and evaluation under separate DB credentials so the
   client-facing role cannot SELECT from drill_sealed_answers.
"""

import hashlib
import hmac
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd

from scripts.trading_brain.db.connection import get_db_connection
from scripts.trading_brain.tape.tape_extractor import TapeMetricsExtractor
from scripts.utils.live_storage_resolver import load_session_bars
from scripts.utils.market_calendar import now_iso_utc, to_iso_utc


class HistoricalDataUnavailableError(Exception):
    """Raised when historical session data cannot be loaded for drill generation."""
    pass


class DrillAlreadyLockedError(Exception):
    """Raised when an answer lock is attempted on an already-evaluated drill."""
    pass


@dataclass
class BlindedDrillContext:
    drill_id: str
    drill_type: str                            # 'RECOGNITION', 'BRACKET_DISCIPLINE', 'REVERSAL_COUNTER'
    dataset_split: str                         # 'TRAINING', 'CALIBRATION', 'ASSESSMENT'
    blinded_bars: List[Dict[str, Any]]         # Normalized 1m bars (09:30-10:30 ET, timestamps/symbol masked)
    custody_token: Optional[str] = None        # HMAC over drill_id when a server key is configured
    custody_mode: str = "TRAINING_MODE_UNVERIFIED"   # 'SIGNED_CUSTODY' or 'TRAINING_MODE_UNVERIFIED'


_VALID_SPLITS = ("TRAINING", "CALIBRATION", "ASSESSMENT")


def _custody_hmac_key() -> Optional[bytes]:
    """Server-side custody key. Present in deployment => signed custody enforced.

    Absent key means the process cannot verify assessment custody: the context is marked
    TRAINING_MODE_UNVERIFIED and the engine refuses ASSESSMENT submission (fail-closed,
    because a same-process answer read cannot be a security boundary without it).
    """
    import os
    key = os.environ.get("TRADING_BRAIN_DRILL_HMAC_KEY")
    return key.encode("utf-8") if key else None


def _sign_drill_id(drill_id: str) -> Optional[str]:
    key = _custody_hmac_key()
    if key is None:
        return None
    mac = hmac.new(key, f"drill:{drill_id}".encode("utf-8"), hashlib.sha256).hexdigest()
    return f"sha256-hmac:{mac}"


class SplitCustodyViolationError(Exception):
    """Raised when a session is assigned to a conflicting dataset split.

    Anti-memorization invariant: once a session appears in ASSESSMENT (or CALIBRATION),
    it can never later appear in TRAINING or CALIBRATION (and vice versa), otherwise the
    trainee can memorize assessment answers during training.
    """
    pass


@dataclass
class DrillDeclaration:
    drill_id: str
    declared_bias: str                         # 'BULLISH', 'BEARISH', 'NEUTRAL'
    declared_setup: str                        # 'ALN_LPEU', 'FIRECRACKER', 'GOALPOST_BB', 'P12_MID'
    declared_entry_price: float
    declared_stop_bps: float
    declared_target_bps: float
    drill_type: str = "RECOGNITION"            # DEPRECATED: sealed metadata governs; retained for client compat
    dataset_split: str = "TRAINING"            # DEPRECATED: sealed metadata governs; retained for client compat
    latency_ms: int = 1500
    custody_token: Optional[str] = None        # Required for ASSESSMENT submissions


@dataclass
class DrillFeedback:
    attempt_id: str
    drill_id: str
    process_adherence_score: float             # 0.0 to 100.0
    rule_match_flag: bool
    true_bias: str
    true_setup: str
    review_notes: str


class BlindedDrillEngine:
    """Manages blinded deliberate practice sessions with strict split custody and anti-memorization."""

    @classmethod
    def _load_session_splits(cls, session_key: Tuple[str, str], db_path: Optional[Union[str, Path]] = None) -> set:
        """Loads all dataset_split assignments for a session from persisted registry."""
        session_date, ticker = session_key
        with get_db_connection(db_path) as conn:
            rows = conn.execute(
                "SELECT dataset_split FROM drill_split_registry WHERE session_date = ? AND ticker = ?;",
                (session_date, ticker)
            ).fetchall()
        return {r["dataset_split"] for r in rows}

    @classmethod
    def _register_session_split(
        cls,
        session_key: Tuple[str, str],
        dataset_split: str,
        db_path: Optional[Union[str, Path]] = None
    ) -> None:
        """Persists a session/split assignment in the anti-memorization registry."""
        session_date, ticker = session_key
        with get_db_connection(db_path) as conn:
            conn.execute(
                """
                INSERT INTO drill_split_registry (session_date, ticker, dataset_split)
                VALUES (?, ?, ?)
                ON CONFLICT(session_date, ticker, dataset_split) DO NOTHING;
                """,
                (session_date, ticker, dataset_split)
            )

    @classmethod
    def generate_blinded_drill(
        cls,
        drill_type: str = "RECOGNITION",
        dataset_split: str = "TRAINING",
        session_date: str = "2026-08-28",
        ticker: str = "NQ1",
        custom_data_dir: Optional[Union[str, Path]] = None,
        synthetic_mode: bool = False,
        db_path: Optional[Union[str, Path]] = None,
    ) -> BlindedDrillContext:
        """Generates a blinded drill context from authentic historical session bars with sealed custody.

        Enforces split-partition custody: a (session_date, ticker) session can never appear
        in conflicting dataset splits. ASSESSMENT sessions are permanently segregated from
        TRAINING/CALIBRATION sessions.
        """
        drill_id = str(uuid.uuid4())

        split_upper = str(dataset_split).upper()
        if split_upper not in _VALID_SPLITS:
            raise ValueError(f"Invalid dataset_split '{dataset_split}'. Must be one of {_VALID_SPLITS}.")

        session_key = (str(session_date), str(ticker))
        prior_splits = cls._load_session_splits(session_key, db_path=db_path)

        assessment_splits = prior_splits & {"ASSESSMENT"}
        training_splits = prior_splits & {"TRAINING", "CALIBRATION"}
        if split_upper == "ASSESSMENT" and training_splits:
            raise SplitCustodyViolationError(
                f"Session {session_key} was previously used in {sorted(training_splits)}; "
                f"it can never be used for ASSESSMENT (anti-memorization custody violation)."
            )
        if split_upper in ("TRAINING", "CALIBRATION") and assessment_splits:
            raise SplitCustodyViolationError(
                f"Session {session_key} is a sealed ASSESSMENT session and can never be reused "
                f"for {split_upper} (anti-memorization custody violation)."
            )
        cls._register_session_split(session_key, split_upper, db_path=db_path)

        if synthetic_mode:
            blinded_bars = []
            base_price = 10000.0
            for i in range(60):
                blinded_bars.append({
                    "bar_index": i,
                    "open": base_price + i * 2,
                    "high": base_price + i * 2 + 3,
                    "low": base_price + i * 2 - 1,
                    "close": base_price + i * 2 + 2,
                    "volume": 500 + i * 10
                })
            true_bias = "BULLISH"
            true_setup = "ALN_LPEU"
        else:
            try:
                df = load_session_bars(ticker, session_date, custom_dir=custom_data_dir)
            except Exception as e:
                raise HistoricalDataUnavailableError(
                    f"Failed to load historical session bars for {ticker} on {session_date}: {e}"
                )

            df_ib = df[(df["dt_et"].dt.time >= time(9, 30)) & (df["dt_et"].dt.time <= time(10, 30))].copy()
            if df_ib.empty:
                raise HistoricalDataUnavailableError(f"No RTH opening bars found for {ticker} on {session_date}")

            blinded_bars = []
            for idx, (_, row) in enumerate(df_ib.iterrows()):
                blinded_bars.append({
                    "bar_index": idx,
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row["volume"])
                })

            true_day_type = TapeMetricsExtractor.classify_day_type(df, ticker=ticker, taxonomy="5_CLASS")
            true_bias = "BULLISH" if true_day_type in ("R1", "DWP") else ("BEARISH" if true_day_type == "R2" else "NEUTRAL")
            true_setup = "ALN_LPEU" if true_bias == "BULLISH" else ("FIRECRACKER" if true_bias == "BEARISH" else "GOALPOST_BB")

        # Persist sealed answer (ground truth + authoritative metadata + custody token) to
        # the database; none of it is returned to the caller.
        custody_token = _sign_drill_id(drill_id)
        custody_mode = "SIGNED_CUSTODY" if custody_token else "TRAINING_MODE_UNVERIFIED"
        with get_db_connection(db_path) as conn:
            conn.execute(
                """
                INSERT INTO drill_sealed_answers (
                    drill_id, true_session_date, true_ticker, true_target_bps,
                    true_stop_bps, true_bias, true_setup, is_locked,
                    drill_type, dataset_split, custody_token
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    drill_id, session_date, ticker, 10.0, 12.0, true_bias, true_setup,
                    0, drill_type, split_upper, custody_token
                )
            )

        return BlindedDrillContext(
            drill_id=drill_id,
            drill_type=drill_type,
            dataset_split=split_upper,
            blinded_bars=blinded_bars,
            custody_token=custody_token,
            custody_mode=custody_mode,
        )

    @classmethod
    def submit_and_evaluate(
        cls,
        declaration: DrillDeclaration,
        db_path: Optional[Union[str, Path]] = None
    ) -> DrillFeedback:
        """Locks in user declaration, scores adherence against sealed ground truth, and writes to drill_attempts."""
        drill_id = declaration.drill_id

        # Read ground truth from the persisted custody table only at evaluation time.
        with get_db_connection(db_path) as conn:
            cur = conn.execute(
                "SELECT * FROM drill_sealed_answers WHERE drill_id = ?;",
                (drill_id,)
            )
            row = cur.fetchone()
            if not row:
                raise ValueError(f"Drill session '{drill_id}' not found in sealed custody vault.")
            # Detect double-evaluation by looking for an existing attempt row (immutable ledger).
            existing = conn.execute(
                "SELECT attempt_id FROM drill_attempts WHERE drill_id = ? LIMIT 1;",
                (drill_id,)
            ).fetchone()
            if existing:
                raise DrillAlreadyLockedError(f"Drill '{drill_id}' has already been locked and evaluated.")

            true_bias = row["true_bias"]
            true_setup = row["true_setup"]
            true_target_bps = float(row["true_target_bps"])
            true_stop_bps = float(row["true_stop_bps"])
            true_session_date = row["true_session_date"]
            true_ticker = row["true_ticker"]
            # Authoritative metadata comes from the SEALED record, never the caller's
            # declaration: an assessment drill submitted as TRAINING would otherwise
            # bypass assessment custody statistics.
            sealed_drill_type = row["drill_type"] if "drill_type" in row.keys() else "RECOGNITION"
            sealed_split = row["dataset_split"] if "dataset_split" in row.keys() else "TRAINING"
            sealed_token = row["custody_token"] if "custody_token" in row.keys() else None

        # Custody verification: with a server key configured, the submission must present
        # the signed token minted at generation time. ASSESSMENT drills submitted WITHOUT
        # a valid key are refused (fail-closed): the same process that sealed answers
        # cannot self-certify assessment participation without an out-of-band signature.
        expected_token = _sign_drill_id(drill_id)
        if sealed_split == "ASSESSMENT" and _custody_hmac_key() is not None:
            presented = getattr(declaration, "custody_token", None)
            if not presented or not sealed_token or presented != sealed_token:
                raise SplitCustodyViolationError(
                    f"Drill '{drill_id}' is an ASSESSMENT drill and requires a valid signed "
                    "custody token (TRADING_BRAIN_DRILL_HMAC_KEY custody boundary)."
                )
        elif sealed_split == "ASSESSMENT" and _custody_hmac_key() is None:
            raise SplitCustodyViolationError(
                f"Drill '{drill_id}' is an ASSESSMENT drill but no custody key is configured. "
                "Assessment submission requires TRADING_BRAIN_DRILL_HMAC_KEY (fail-closed)."
            )

        attempt_id = str(uuid.uuid4())
        now_iso = now_iso_utc()

        bias_match = (declaration.declared_bias.upper() == true_bias.upper())
        setup_match = (declaration.declared_setup.upper() == true_setup.upper())
        stop_diff = abs(declaration.declared_stop_bps - true_stop_bps)
        target_diff = abs(declaration.declared_target_bps - true_target_bps)

        score = 0.0
        if bias_match:
            score += 40.0
        if setup_match:
            score += 30.0
        if stop_diff <= 2.0:
            score += 15.0
        if target_diff <= 2.0:
            score += 15.0

        rule_match = (score >= 70.0)
        review_notes = (
            f"Declared {declaration.declared_bias}/{declaration.declared_setup}. "
            f"Ground truth: {true_bias}/{true_setup} on {true_session_date} ({true_ticker})."
        )

        with get_db_connection(db_path) as conn:
            conn.execute(
                """
                INSERT INTO drill_attempts (
                    attempt_id, drill_id, drill_type, dataset_split,
                    declared_bias, declared_setup, declared_entry_price,
                    declared_stop_bps, declared_target_bps, answer_locked_at_utc,
                    process_adherence_score, rule_match_flag, latency_ms, review_notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    attempt_id,
                    drill_id,
                    sealed_drill_type,
                    sealed_split,
                    declaration.declared_bias,
                    declaration.declared_setup,
                    declaration.declared_entry_price,
                    declaration.declared_stop_bps,
                    declaration.declared_target_bps,
                    now_iso,
                    score,
                    1 if rule_match else 0,
                    declaration.latency_ms,
                    review_notes
                )
            )

        return DrillFeedback(
            attempt_id=attempt_id,
            drill_id=drill_id,
            process_adherence_score=score,
            rule_match_flag=rule_match,
            true_bias=true_bias,
            true_setup=true_setup,
            review_notes=review_notes
        )