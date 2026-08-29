"""Pytest suite for ForecastRegistrar (Milestone 0.4)."""

import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts.trading_brain.db.init_db import init_trading_brain_db
from scripts.trading_brain.forecast.forecast_registrar import (
    ForecastCutoffExpiredError,
    ForecastInputValidationError,
    ForecastRegistrar,
    ForecastSnapshotPayload
)
from scripts.utils.market_calendar import get_session_cutoff_utc


@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = Path(tmpdir) / "test_trading_brain.sqlite"
        init_trading_brain_db(db_path=db_path, verbose=False)
        yield db_path


def test_two_phase_live_forecast_success(temp_db):
    """Tests successful pre-cutoff two-phase registration resulting in LIVE_PRODUCTION."""
    # Future session date so now is well before cutoff
    session_date = "2026-09-01"
    cutoff = get_session_cutoff_utc(session_date)
    
    input_manifest = [
        {"provider_name": "ALNSessionsProvider_v1", "data_type": "BARS", "max_timestamp_utc": "2026-09-01T12:00:00Z", "content_hash": "h1"},
        {"provider_name": "P12VectorProvider_v1", "data_type": "LEVELS", "max_timestamp_utc": "2026-09-01T12:00:00Z", "content_hash": "h2"}
    ]
    
    run = ForecastRegistrar.create_forecast_run(
        session_date=session_date,
        ticker="NQ1",
        model_version_id="MOD_PROFILER_5CLASS_V1",
        input_manifest=input_manifest,
        commit_grace_period_sec=120,
        db_path=temp_db
    )
    
    assert run.status == "INPUTS_SEALED"
    assert run.forecast_run_id is not None
    
    payload = ForecastSnapshotPayload(
        prob_r1=0.20,
        prob_r2=0.20,
        prob_dnp=0.10,
        prob_dwp=0.10,
        prob_rotational_chop=0.40,
        predicted_day_type="ROTATIONAL_CHOP",
        predicted_bias="NEUTRAL",
        p12_vector_direction="NEUTRAL",
        p12_equilibrium_level=20000.0,
        candle_science_target_high=20100.0,
        candle_science_target_low=19900.0
    )
    
    res = ForecastRegistrar.commit_forecast_run(run.forecast_run_id, payload, db_path=temp_db)
    assert res["forecast_mode"] == "LIVE_PRODUCTION"
    assert res["session_date"] == "2026-09-01"
    
    # Verify second LIVE_PRODUCTION for same session fails with IntegrityError
    run2 = ForecastRegistrar.create_forecast_run(
        session_date=session_date,
        ticker="NQ1",
        model_version_id="MOD_PROFILER_5CLASS_V1",
        input_manifest=input_manifest,
        commit_grace_period_sec=120,
        db_path=temp_db
    )
    with pytest.raises(sqlite3.IntegrityError):
        ForecastRegistrar.commit_forecast_run(run2.forecast_run_id, payload, db_path=temp_db)


def test_input_timestamp_exceeding_cutoff_rejected(temp_db):
    """Tests that input manifests with bars past cutoff are rejected during run creation."""
    session_date = "2026-09-01"
    cutoff = get_session_cutoff_utc(session_date)
    future_bar = (cutoff + timedelta(minutes=5)).isoformat()
    
    input_manifest = [
        {"provider_name": "ALN", "max_timestamp_utc": future_bar, "content_hash": "h1"}
    ]
    
    with pytest.raises(ForecastInputValidationError):
        ForecastRegistrar.create_forecast_run(
            session_date=session_date,
            ticker="NQ1",
            model_version_id="MOD_V1",
            input_manifest=input_manifest,
            db_path=temp_db
        )


def test_late_run_initiation_rejected(temp_db):
    """Tests that attempting to initiate a forecast run after the session cutoff raises ForecastCutoffExpiredError."""
    # Past session date
    past_session = "2026-01-01"
    
    with pytest.raises(ForecastCutoffExpiredError):
        ForecastRegistrar.create_forecast_run(
            session_date=past_session,
            ticker="NQ1",
            model_version_id="MOD_V1",
            input_manifest=[],
            db_path=temp_db
        )


def test_replay_audit_registration(temp_db):
    """Tests that historical replay forecasts are registered with mode REPLAY_AUDIT."""
    payload = ForecastSnapshotPayload(
        prob_r1=0.5,
        prob_r2=0.1,
        prob_dnp=0.1,
        prob_dwp=0.1,
        prob_rotational_chop=0.2,
        predicted_bias="BULLISH"
    )
    
    res = ForecastRegistrar.register_replay_forecast(
        session_date="2026-08-28",
        ticker="NQ1",
        model_version_id="MOD_REPLAY_V1",
        payload=payload,
        db_path=temp_db
    )
    
    assert res["forecast_mode"] == "REPLAY_AUDIT"
    assert res["forecast_id"] is not None


def test_probability_distribution_sum_validation(temp_db):
    """Tests that invalid probability distributions are rejected with ForecastInputValidationError."""
    session_date = "2026-09-01"
    run = ForecastRegistrar.create_forecast_run(
        session_date=session_date,
        ticker="NQ1",
        model_version_id="MOD_V1",
        input_manifest=[],
        db_path=temp_db
    )
    
    # Probabilities sum to 0.8 instead of 1.0 -> should fail
    invalid_payload = ForecastSnapshotPayload(
        prob_r1=0.20,
        prob_r2=0.20,
        prob_dnp=0.20,
        prob_dwp=0.10,
        prob_rotational_chop=0.10  # sum = 0.8
    )
    
    with pytest.raises(ForecastInputValidationError) as excinfo:
        ForecastRegistrar.commit_forecast_run(run.forecast_run_id, invalid_payload, db_path=temp_db)
    assert "5 MECE probabilities must sum to 1.0" in str(excinfo.value)
