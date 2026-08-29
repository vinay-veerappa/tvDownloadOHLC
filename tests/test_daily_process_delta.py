"""Pytest suite for Daily Process Delta & 4-Way Institutional Reconciliation (Milestone 1.1)."""

import sqlite3
import tempfile
from pathlib import Path
import pytest

from scripts.trading_brain.db.init_db import init_trading_brain_db
from scripts.trading_brain.evaluation.daily_process_delta import DailyProcessDeltaReconciler
from scripts.trading_brain.plans.plan_adapter import PlanAdapter, PlanContext

@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = Path(tmpdir) / "test_trading_brain.sqlite"
        init_trading_brain_db(db_path=db_path, verbose=False)
        yield db_path

def test_4way_reconciler_live_production_and_replay_scoring(temp_db):
    session_date = "2026-08-28"
    ticker = "NQ1"
    
    PlanAdapter.save_plan_snapshot(
        PlanContext(
            session_date=session_date, ticker=ticker, preparation_cutoff_utc="2026-08-28T12:45:00Z",
            verbatim_plan_text="Bullish plan", primary_bias="BULLISH", wargamed_scenarios={},
            invalidation_levels={}, max_intended_risk_bps=10.0, permitted_strategies=["STRAT_ALN_LPEU_V0_1"]
        ),
        db_path=temp_db,
        received_at_utc="2026-08-28T12:30:00Z",
        override_reason="test-fixture historical migration",
        override_actor="TEST_FIXTURE",
    )
    
    with sqlite3.connect(str(temp_db)) as conn:
        conn.execute(
            """
            INSERT INTO session_tape_actuals (
                actual_id, session_date, ticker, revision_seq, source_system,
                session_open, session_high, session_low, session_close, rth_close,
                session_range_bps, day_type_classification, expected_bar_count,
                actual_bar_count, content_hash, quality_state
            ) VALUES ('tape-1', '2026-08-28', 'NQ1', 1, 'PARQUET', 20000.0, 20100.0, 19950.0, 20080.0, 20080.0, 75.0, 'R1', 390, 390, 'hash', 'CLEAN');
            """
        )
        conn.execute(
            """
            INSERT INTO forecast_snapshots (
                forecast_id, forecast_run_id, session_date, ticker, model_version_id,
                forecast_mode, effective_cutoff_utc, predicted_day_type, predicted_bias,
                prob_r1, prob_r2, prob_dnp, prob_dwp, prob_rotational_chop,
                git_hash, config_hash, abstain_flag
            ) VALUES ('f-1', 'r-1', '2026-08-28', 'NQ1', 'MOD_V1', 'LIVE_PRODUCTION', '2026-08-28T12:45:00Z', 'R1', 'BULLISH', 0.60, 0.10, 0.10, 0.10, 0.10, 'git', 'cfg', 0);
            """
        )
        
    scorecard = DailyProcessDeltaReconciler.reconcile_session(session_date, ticker, db_path=temp_db)
    assert scorecard.plan.plan_found is True
    assert scorecard.forecast.forecast_found is True
    assert scorecard.forecast.scored_for_calibration is True
    assert scorecard.forecast.session_brier_loss is not None
    assert scorecard.forecast.session_brier_loss < 0.50
    assert scorecard.process_outcome_quadrant == "GOOD_PROCESS_GOOD_OUTCOME"

def test_replay_forecast_not_scored_for_calibration(temp_db):
    session_date = "2026-08-27"
    ticker = "NQ1"
    
    with sqlite3.connect(str(temp_db)) as conn:
        conn.execute(
            """
            INSERT INTO session_tape_actuals (
                actual_id, session_date, ticker, revision_seq, source_system,
                session_open, session_high, session_low, session_close, rth_close,
                session_range_bps, day_type_classification, expected_bar_count,
                actual_bar_count, content_hash, quality_state
            ) VALUES ('tape-2', '2026-08-27', 'NQ1', 1, 'PARQUET', 20000.0, 20100.0, 19950.0, 20080.0, 20080.0, 75.0, 'R1', 390, 390, 'hash', 'CLEAN');
            """
        )
        conn.execute(
            """
            INSERT INTO forecast_snapshots (
                forecast_id, forecast_run_id, session_date, ticker, model_version_id,
                forecast_mode, effective_cutoff_utc, predicted_day_type, predicted_bias,
                prob_r1, prob_r2, prob_dnp, prob_dwp, prob_rotational_chop,
                git_hash, config_hash, abstain_flag
            ) VALUES ('f-2', 'r-2', '2026-08-27', 'NQ1', 'MOD_V1', 'REPLAY_AUDIT', '2026-08-27T12:45:00Z', 'R1', 'BULLISH', 0.90, 0.025, 0.025, 0.025, 0.025, 'git', 'cfg', 0);
            """
        )
        
    scorecard = DailyProcessDeltaReconciler.reconcile_session(session_date, ticker, db_path=temp_db)
    assert scorecard.forecast.scored_for_calibration is False
    assert scorecard.forecast.session_brier_loss is None
    assert scorecard.forecast.session_log_loss is None

def test_no_plan_executions_flagged_non_compliant(temp_db):
    session_date = "2026-08-26"
    ticker = "NQ1"
    
    with sqlite3.connect(str(temp_db)) as conn:
        conn.execute(
            """
            INSERT INTO execution_events (
                execution_id, session_date, ticker, account_id, broker_execution_id,
                broker_order_id, order_action, order_type, quantity, fill_price,
                idempotency_key, event_timestamp_utc
            ) VALUES ('exec-np', '2026-08-26', 'NQ1', 'ACC1', 'b-np', 'b-ord', 'BUY', 'LIMIT', 1, 20000.0, 'idemp-np', '2026-08-26T13:35:10Z');
            """
        )
        
    scorecard = DailyProcessDeltaReconciler.reconcile_session(session_date, ticker, db_path=temp_db)
    assert scorecard.plan.plan_found is False
    assert scorecard.plan_compliant is False

