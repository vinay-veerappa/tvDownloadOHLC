"""Pytest suite for ForecastRegistrar (Milestone 0.4)."""

import sqlite3
import tempfile
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
    session_date = "2026-09-01"
    
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
        git_hash="git-commit-123",
        config_hash="cfg-hash-456",
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
    
    # Second LIVE_PRODUCTION for same session fails with IntegrityError
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


def test_fail_closed_manifest_validation(temp_db):
    """Tests that missing max_timestamp_utc or content_hash triggers fail-closed validation error."""
    session_date = "2026-09-01"
    
    # Missing max_timestamp_utc
    with pytest.raises(ForecastInputValidationError):
        ForecastRegistrar.create_forecast_run(
            session_date=session_date,
            ticker="NQ1",
            model_version_id="MOD_V1",
            input_manifest=[{"provider_name": "ALN", "content_hash": "h1"}],
            db_path=temp_db
        )
        
    # Missing content_hash
    with pytest.raises(ForecastInputValidationError):
        ForecastRegistrar.create_forecast_run(
            session_date=session_date,
            ticker="NQ1",
            model_version_id="MOD_V1",
            input_manifest=[{"provider_name": "ALN", "max_timestamp_utc": "2026-09-01T12:00:00Z"}],
            db_path=temp_db
        )


def test_probability_distribution_sum_validation(temp_db):
    """Tests that invalid probability distributions are rejected with ForecastInputValidationError."""
    session_date = "2026-09-01"
    run = ForecastRegistrar.create_forecast_run(
        session_date=session_date,
        ticker="NQ1",
        model_version_id="MOD_V1",
        input_manifest=[{"provider_name": "ALN", "max_timestamp_utc": "2026-09-01T12:00:00Z", "content_hash": "h1"}],
        db_path=temp_db
    )
    
    invalid_payload = ForecastSnapshotPayload(
        git_hash="git1",
        config_hash="cfg1",
        prob_r1=0.20,
        prob_r2=0.20,
        prob_dnp=0.20,
        prob_dwp=0.10,
        prob_rotational_chop=0.10  # sum = 0.8
    )
    
    with pytest.raises(ForecastInputValidationError) as excinfo:
        ForecastRegistrar.commit_forecast_run(run.forecast_run_id, invalid_payload, db_path=temp_db)
    assert "5 MECE probabilities must sum to 1.0" in str(excinfo.value)
