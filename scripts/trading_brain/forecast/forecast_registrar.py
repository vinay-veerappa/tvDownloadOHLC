"""Two-Phase Sealed Pre-Market Forecast Snapshot Registrar (Milestone 0.4).

Enforces:
1. Phase 1 Pre-Cutoff Run Initiation: Seals input bar manifests & content hashes before cutoff.
2. Phase 2 Commit Completion: Evaluates server clock against cutoff and grace period:
   - <= cutoff -> LIVE_PRODUCTION
   - > cutoff and <= cutoff + grace -> FORECAST_LATE_RECEIVED (demoted)
   - > cutoff + grace -> REJECTED with ForecastCutoffExpiredError
3. Strict database-enforced uniqueness: exactly 1 LIVE_PRODUCTION forecast per (session_date, ticker).
"""

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from scripts.trading_brain.db.connection import get_db_connection
from scripts.utils.market_calendar import get_session_cutoff_utc


class ForecastCutoffExpiredError(Exception):
    """Raised when a forecast commit attempt occurs after the certified commit grace period has expired."""
    pass


class ForecastInputValidationError(Exception):
    """Raised when forecast inputs violate temporal cutoff or schema rules."""
    pass


@dataclass
class ForecastRun:
    forecast_run_id: str
    session_date: str
    ticker: str
    model_version_id: str
    effective_cutoff_utc: str
    commit_grace_period_sec: int
    status: str
    started_at_utc: str
    inputs_sealed_at_utc: Optional[str] = None
    committed_at_utc: Optional[str] = None


@dataclass
class ForecastSnapshotPayload:
    prob_r1: Optional[float] = None
    prob_r2: Optional[float] = None
    prob_dnp: Optional[float] = None
    prob_dwp: Optional[float] = None
    prob_rotational_chop: Optional[float] = None
    predicted_day_type: Optional[str] = None
    predicted_bias: Optional[str] = None
    p12_vector_direction: Optional[str] = None
    p12_equilibrium_level: Optional[float] = None
    candle_science_target_high: Optional[float] = None
    candle_science_target_low: Optional[float] = None
    expected_move_high: Optional[float] = None
    expected_move_low: Optional[float] = None
    git_hash: str = "main"
    config_hash: str = "default_config"
    abstain_flag: bool = False
    abstain_reason: Optional[str] = None


class ForecastRegistrar:
    """Service class for two-phase sealed forecast registration and cutoff enforcement."""

    @staticmethod
    def create_forecast_run(
        session_date: str,
        ticker: str,
        model_version_id: str,
        input_manifest: List[Dict[str, Any]],
        commit_grace_period_sec: int = 120,
        cutoff_time_et: str = "08:45:00",
        db_path: Optional[Union[str, Path]] = None
    ) -> ForecastRun:
        """Phase 1: Initiates a forecast run and seals input manifests before cutoff.
        
        Raises ForecastCutoffExpiredError if initiated after cutoff.
        """
        now_dt = datetime.now(timezone.utc)
        cutoff_dt = get_session_cutoff_utc(session_date, cutoff_time_et_str=cutoff_time_et)
        
        # Enforce that run initiation occurs before cutoff
        if now_dt > cutoff_dt:
            raise ForecastCutoffExpiredError(
                f"Cannot create live forecast run after session cutoff: now={now_dt.isoformat()} > cutoff={cutoff_dt.isoformat()}"
            )
            
        # Verify that all input manifests precede or equal cutoff
        for inp in input_manifest:
            max_ts = inp.get("max_timestamp_utc")
            if max_ts:
                inp_dt = datetime.fromisoformat(max_ts.replace("Z", "+00:00"))
                if inp_dt > cutoff_dt:
                    raise ForecastInputValidationError(
                        f"Input {inp.get('provider_name')} max timestamp {max_ts} exceeds cutoff {cutoff_dt.isoformat()}"
                    )
                    
        run_id = str(uuid.uuid4())
        now_iso = now_dt.isoformat()
        cutoff_iso = cutoff_dt.isoformat()
        
        with get_db_connection(db_path) as conn:
            conn.execute(
                """
                INSERT INTO forecast_runs (
                    forecast_run_id, session_date, ticker, model_version_id,
                    effective_cutoff_utc, commit_grace_period_sec, status,
                    started_at_utc, inputs_sealed_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, 'INPUTS_SEALED', ?, ?);
                """,
                (run_id, session_date, ticker, model_version_id, cutoff_iso, commit_grace_period_sec, now_iso, now_iso)
            )
            
            # Seal input manifest
            for inp in input_manifest:
                conn.execute(
                    """
                    INSERT INTO forecast_run_inputs (
                        input_id, forecast_run_id, provider_name, data_type,
                        max_timestamp_utc, content_hash
                    ) VALUES (?, ?, ?, ?, ?, ?);
                    """,
                    (
                        str(uuid.uuid4()),
                        run_id,
                        inp.get("provider_name", "UNKNOWN"),
                        inp.get("data_type", "BARS"),
                        inp.get("max_timestamp_utc", now_iso),
                        inp.get("content_hash", "hash")
                    )
                )
                
        return ForecastRun(
            forecast_run_id=run_id,
            session_date=session_date,
            ticker=ticker,
            model_version_id=model_version_id,
            effective_cutoff_utc=cutoff_iso,
            commit_grace_period_sec=commit_grace_period_sec,
            status="INPUTS_SEALED",
            started_at_utc=now_iso,
            inputs_sealed_at_utc=now_iso
        )

    @staticmethod
    def commit_forecast_run(
        forecast_run_id: str,
        payload: ForecastSnapshotPayload,
        db_path: Optional[Union[str, Path]] = None
    ) -> Dict[str, Any]:
        """Phase 2: Commits forecast predictions with asymmetric cutoff enforcement.
        
        - <= cutoff -> LIVE_PRODUCTION
        - <= cutoff + grace -> FORECAST_LATE_RECEIVED (demoted)
        - > cutoff + grace -> Rejects and transitions run to EXPIRED.
        """
        now_dt = datetime.now(timezone.utc)
        forecast_id = str(uuid.uuid4())
        
        with get_db_connection(db_path) as conn:
            # Query run state
            cur = conn.execute("SELECT * FROM forecast_runs WHERE forecast_run_id = ?;", (forecast_run_id,))
            run_row = cur.fetchone()
            if not run_row:
                raise ValueError(f"Forecast run {forecast_run_id} not found.")
                
            if run_row["status"] != "INPUTS_SEALED":
                raise ValueError(f"Forecast run {forecast_run_id} is in status '{run_row['status']}', expected 'INPUTS_SEALED'.")
                
            cutoff_dt = datetime.fromisoformat(run_row["effective_cutoff_utc"].replace("Z", "+00:00"))
            grace_sec = run_row["commit_grace_period_sec"]
            
            # Determine forecast_mode based on database clock
            if now_dt <= cutoff_dt:
                forecast_mode = "LIVE_PRODUCTION"
            elif (now_dt - cutoff_dt).total_seconds() <= grace_sec:
                forecast_mode = "FORECAST_LATE_RECEIVED"
            else:
                # Mark run expired
                conn.execute(
                    "UPDATE forecast_runs SET status = 'EXPIRED' WHERE forecast_run_id = ?;",
                    (forecast_run_id,)
                )
                raise ForecastCutoffExpiredError(
                    f"Commit deadline expired for run {forecast_run_id}: committed at {now_dt.isoformat()} > deadline {cutoff_dt.isoformat()} + {grace_sec}s"
                )
                
            # Insert immutable forecast snapshot (omitting received_at_utc & created_at_utc so SQLite generates them)
            conn.execute(
                """
                INSERT INTO forecast_snapshots (
                    forecast_id, forecast_run_id, session_date, ticker, model_version_id,
                    forecast_mode, effective_cutoff_utc, prob_r1, prob_r2, prob_dnp,
                    prob_dwp, prob_rotational_chop, predicted_day_type, predicted_bias,
                    p12_vector_direction, p12_equilibrium_level, candle_science_target_high,
                    candle_science_target_low, expected_move_high, expected_move_low,
                    git_hash, config_hash, abstain_flag, abstain_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    forecast_id,
                    forecast_run_id,
                    run_row["session_date"],
                    run_row["ticker"],
                    run_row["model_version_id"],
                    forecast_mode,
                    run_row["effective_cutoff_utc"],
                    payload.prob_r1,
                    payload.prob_r2,
                    payload.prob_dnp,
                    payload.prob_dwp,
                    payload.prob_rotational_chop,
                    payload.predicted_day_type,
                    payload.predicted_bias,
                    payload.p12_vector_direction,
                    payload.p12_equilibrium_level,
                    payload.candle_science_target_high,
                    payload.candle_science_target_low,
                    payload.expected_move_high,
                    payload.expected_move_low,
                    payload.git_hash,
                    payload.config_hash,
                    1 if payload.abstain_flag else 0,
                    payload.abstain_reason
                )
            )
            
            # Transition run to COMMITTED
            conn.execute(
                "UPDATE forecast_runs SET status = 'COMMITTED', committed_at_utc = ? WHERE forecast_run_id = ?;",
                (now_dt.isoformat(), forecast_run_id)
            )
            
            # Fetch server-generated receipt
            cur = conn.execute("SELECT received_at_utc FROM forecast_snapshots WHERE forecast_id = ?;", (forecast_id,))
            received_at = cur.fetchone()["received_at_utc"]
            
        return {
            "forecast_id": forecast_id,
            "forecast_run_id": forecast_run_id,
            "session_date": run_row["session_date"],
            "ticker": run_row["ticker"],
            "forecast_mode": forecast_mode,
            "received_at_utc": received_at,
            "effective_cutoff_utc": run_row["effective_cutoff_utc"]
        }

    @staticmethod
    def register_replay_forecast(
        session_date: str,
        ticker: str,
        model_version_id: str,
        payload: ForecastSnapshotPayload,
        effective_cutoff_utc: Optional[str] = None,
        db_path: Optional[Union[str, Path]] = None
    ) -> Dict[str, Any]:
        """Registers a historical replay audit forecast (mode = REPLAY_AUDIT)."""
        forecast_id = str(uuid.uuid4())
        cutoff_iso = effective_cutoff_utc or get_session_cutoff_utc(session_date).isoformat()
        
        with get_db_connection(db_path) as conn:
            conn.execute(
                """
                INSERT INTO forecast_snapshots (
                    forecast_id, session_date, ticker, model_version_id,
                    forecast_mode, effective_cutoff_utc, prob_r1, prob_r2, prob_dnp,
                    prob_dwp, prob_rotational_chop, predicted_day_type, predicted_bias,
                    p12_vector_direction, p12_equilibrium_level, candle_science_target_high,
                    candle_science_target_low, expected_move_high, expected_move_low,
                    git_hash, config_hash, abstain_flag, abstain_reason
                ) VALUES (?, ?, ?, ?, 'REPLAY_AUDIT', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    forecast_id,
                    session_date,
                    ticker,
                    model_version_id,
                    cutoff_iso,
                    payload.prob_r1,
                    payload.prob_r2,
                    payload.prob_dnp,
                    payload.prob_dwp,
                    payload.prob_rotational_chop,
                    payload.predicted_day_type,
                    payload.predicted_bias,
                    payload.p12_vector_direction,
                    payload.p12_equilibrium_level,
                    payload.candle_science_target_high,
                    payload.candle_science_target_low,
                    payload.expected_move_high,
                    payload.expected_move_low,
                    payload.git_hash,
                    payload.config_hash,
                    1 if payload.abstain_flag else 0,
                    payload.abstain_reason
                )
            )
            cur = conn.execute("SELECT received_at_utc FROM forecast_snapshots WHERE forecast_id = ?;", (forecast_id,))
            received_at = cur.fetchone()["received_at_utc"]
            
        return {
            "forecast_id": forecast_id,
            "session_date": session_date,
            "ticker": ticker,
            "forecast_mode": "REPLAY_AUDIT",
            "received_at_utc": received_at
        }
