"""Two-Phase Sealed Forecast Registrar (Milestone 0.4)."""

import hashlib
import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from scripts.trading_brain.db.connection import get_db_connection
from scripts.utils.market_calendar import get_session_cutoff_utc, now_iso_utc, parse_iso_utc, to_iso_utc

VALID_DAY_TYPES = {"R1", "R2", "DNP", "DWP", "ROTATIONAL_CHOP"}


class ForecastCutoffExpiredError(Exception):
    pass


class ForecastInputValidationError(Exception):
    pass


@dataclass
class ForecastRunContext:
    run_id: str
    session_date: str
    ticker: str
    model_version_id: str
    effective_cutoff_utc: str
    status: str

    @property
    def forecast_run_id(self) -> str:
        return self.run_id


@dataclass
class ForecastSnapshotPayload:
    run_id: Optional[str] = None
    forecast_run_id: Optional[str] = None
    predicted_day_type: Optional[str] = None
    predicted_bias: Optional[str] = None
    prob_r1: Optional[float] = None
    prob_r2: Optional[float] = None
    prob_dnp: Optional[float] = None
    prob_dwp: Optional[float] = None
    prob_rotational_chop: Optional[float] = None
    abstain_flag: bool = False
    abstain_reason: Optional[str] = None
    distribution_entropy: Optional[float] = None
    forecast_mode: str = "LIVE_PRODUCTION"
    git_hash: str = "git:current_commit"
    config_hash: str = "sha256:config_hash"
    p12_vector_direction: Optional[str] = None
    p12_equilibrium_level: Optional[float] = None
    candle_science_target_high: Optional[float] = None
    candle_science_target_low: Optional[float] = None
    expected_move_high: Optional[float] = None
    expected_move_low: Optional[float] = None

    def get_run_id(self, fallback_id: Optional[str] = None) -> str:
        r_id = self.forecast_run_id or self.run_id or fallback_id
        if not r_id:
            raise ValueError("ForecastSnapshotPayload must have run_id or forecast_run_id set.")
        return r_id


class ForecastCommitResult(dict):
    def __init__(self, forecast_id: str, forecast_mode: str, session_date: str = "", ticker: str = ""):
        super().__init__(forecast_id=forecast_id, forecast_mode=forecast_mode, session_date=session_date, ticker=ticker)
        self.forecast_id = forecast_id
        self.forecast_mode = forecast_mode
        self.session_date = session_date
        self.ticker = ticker

    def __str__(self):
        return self.forecast_id


class ForecastRegistrar:
    """Service class for two-phase sealed quantitative forecast registration."""

    @classmethod
    def create_forecast_run(
        cls,
        session_date: str,
        ticker: str,
        model_version_id: str,
        input_manifest: List[Dict[str, Any]],
        cutoff_time_et_str: str = "08:45:00",
        commit_grace_period_sec: int = 300,
        db_path: Optional[Union[str, Path]] = None
    ) -> ForecastRunContext:
        if not input_manifest:
            raise ForecastInputValidationError("Input manifest cannot be empty. At least 1 provider input is required.")
            
        effective_cutoff = get_session_cutoff_utc(session_date, cutoff_time_et_str)
        effective_cutoff_iso = to_iso_utc(effective_cutoff)
        
        for item in input_manifest:
            avail_str = item.get("source_available_at_utc") or item.get("max_timestamp_utc")
            if not avail_str or "content_hash" not in item:
                raise ForecastInputValidationError(f"Input manifest item missing timestamp or content_hash: {item}")
            avail_ts = parse_iso_utc(avail_str)
            if avail_ts > effective_cutoff:
                raise ForecastInputValidationError(
                    f"Provider input timestamp {avail_str} is after session cutoff {effective_cutoff_iso}"
                )
                
        run_id = str(uuid.uuid4())
        now_iso = now_iso_utc()
        
        with get_db_connection(db_path) as conn:
            conn.execute(
                """
                INSERT INTO forecast_runs (
                    forecast_run_id, session_date, ticker, model_version_id,
                    effective_cutoff_utc, commit_grace_period_sec, status,
                    started_at_utc, inputs_sealed_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, 'INPUTS_SEALED', ?, ?);
                """,
                (run_id, session_date, ticker, model_version_id, effective_cutoff_iso, commit_grace_period_sec, now_iso, now_iso)
            )
            
            for item in input_manifest:
                input_id = str(uuid.uuid4())
                avail_str = item.get("source_available_at_utc") or item.get("max_timestamp_utc")
                conn.execute(
                    """
                    INSERT INTO forecast_run_inputs (
                        input_id, forecast_run_id, provider_name, data_type,
                        max_timestamp_utc, content_hash
                    ) VALUES (?, ?, ?, ?, ?, ?);
                    """,
                    (
                        input_id, run_id, item.get("provider_name", "UNKNOWN"),
                        item.get("data_type", "FEATURE_FEED"), to_iso_utc(avail_str),
                        item["content_hash"]
                    )
                )
                
        return ForecastRunContext(
            run_id=run_id,
            session_date=session_date,
            ticker=ticker,
            model_version_id=model_version_id,
            effective_cutoff_utc=effective_cutoff_iso,
            status="INPUTS_SEALED"
        )

    @classmethod
    def commit_forecast_run(
        cls,
        first_arg: Union[str, ForecastSnapshotPayload],
        second_arg: Optional[ForecastSnapshotPayload] = None,
        grace_period_seconds: int = 300,
        db_path: Optional[Union[str, Path]] = None
    ) -> ForecastCommitResult:
        if isinstance(first_arg, str):
            run_id_param = first_arg
            payload = second_arg
        else:
            payload = first_arg
            run_id_param = None
            
        if payload is None:
            raise ValueError("ForecastSnapshotPayload must be provided.")
            
        if payload.abstain_flag:
            if not payload.abstain_reason:
                raise ForecastInputValidationError("Abstaining forecast MUST provide a non-empty abstain_reason.")
            if any(p is not None for p in (payload.prob_r1, payload.prob_r2, payload.prob_dnp, payload.prob_dwp, payload.prob_rotational_chop)):
                raise ForecastInputValidationError("Abstaining forecast MUST have NULL probabilities across all day types.")
        else:
            probs = [
                payload.prob_r1, payload.prob_r2, payload.prob_dnp,
                payload.prob_dwp, payload.prob_rotational_chop
            ]
            if any(p is None for p in probs):
                raise ForecastInputValidationError("Non-abstaining forecast must supply all 5 day-type probabilities.")
            prob_sum = sum(probs)
            if abs(prob_sum - 1.0) > 1e-4:
                raise ForecastInputValidationError(f"5 MECE probabilities must sum to 1.0 +- 1e-4, got sum={prob_sum:.6f}")

        forecast_id = str(uuid.uuid4())
        target_run_id = payload.get_run_id(run_id_param)
        
        with get_db_connection(db_path) as conn:
            cur = conn.execute("SELECT * FROM forecast_runs WHERE forecast_run_id = ?;", (target_run_id,))
            run_row = cur.fetchone()
            if not run_row:
                raise ValueError(f"Forecast run {target_run_id} not found.")
            if run_row["status"] == "COMMITTED":
                raise ValueError(f"Forecast run {target_run_id} has already been committed.")
                
            # Capture the commit-authority clock AFTER connection acquisition and state reads.
            # Capturing earlier would let lock contention backdate the persisted receipt time
            # (a blocked commit that wrote after cutoff would have carried a pre-cutoff timestamp).
            now_iso = now_iso_utc()
            now_dt = datetime.now(timezone.utc)
            
            cutoff_dt = parse_iso_utc(run_row["effective_cutoff_utc"])
            grace_dt = cutoff_dt + timedelta(seconds=grace_period_seconds)
            
            if payload.forecast_mode == "LIVE_PRODUCTION":
                if now_dt <= cutoff_dt:
                    assigned_mode = "LIVE_PRODUCTION"
                elif now_dt <= grace_dt:
                    assigned_mode = "FORECAST_LATE_RECEIVED"
                else:
                    with get_db_connection(db_path) as expire_conn:
                        expire_conn.execute("UPDATE forecast_runs SET status = 'EXPIRED' WHERE forecast_run_id = ?;", (target_run_id,))
                    raise ForecastCutoffExpiredError(f"Forecast submitted late at {now_iso}")
            else:
                assigned_mode = payload.forecast_mode
                
            conn.execute(
                """
                INSERT INTO forecast_snapshots (
                    forecast_id, forecast_run_id, session_date, ticker, model_version_id,
                    forecast_mode, effective_cutoff_utc, predicted_day_type, predicted_bias,
                    prob_r1, prob_r2, prob_dnp, prob_dwp, prob_rotational_chop,
                    git_hash, config_hash, abstain_flag, abstain_reason, received_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    forecast_id, target_run_id, run_row["session_date"], run_row["ticker"],
                    run_row["model_version_id"], assigned_mode, run_row["effective_cutoff_utc"],
                    payload.predicted_day_type, payload.predicted_bias,
                    payload.prob_r1, payload.prob_r2, payload.prob_dnp, payload.prob_dwp,
                    payload.prob_rotational_chop, payload.git_hash, payload.config_hash,
                    1 if payload.abstain_flag else 0, payload.abstain_reason, now_iso
                )
            )
            
            conn.execute("UPDATE forecast_runs SET status = 'COMMITTED', committed_at_utc = ? WHERE forecast_run_id = ?;", (now_iso, target_run_id))
            
        return ForecastCommitResult(forecast_id=forecast_id, forecast_mode=assigned_mode, session_date=run_row['session_date'], ticker=run_row['ticker'])
