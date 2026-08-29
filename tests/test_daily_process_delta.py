"""Pytest suite for DailyProcessDeltaReconciler (Milestone 1.1)."""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from scripts.trading_brain.db.init_db import init_trading_brain_db
from scripts.trading_brain.evaluation.daily_process_delta import DailyProcessDeltaReconciler
from scripts.trading_brain.forecast.forecast_registrar import ForecastRegistrar, ForecastSnapshotPayload
from scripts.trading_brain.ingest.nt8_broker_adapter import NT8BrokerAdapter
from scripts.trading_brain.plans.plan_adapter import PlanAdapter, PlanContext
from scripts.trading_brain.signals.opportunity_logger import OpportunityLogger, SignalOpportunity
from scripts.trading_brain.strategies.registry_v0 import register_all_v0_strategies


@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = Path(tmpdir) / "test_trading_brain.sqlite"
        init_trading_brain_db(db_path=db_path, verbose=False)
        yield db_path


def test_4way_reconciler_quadrant(temp_db):
    """Tests complete 4-way reconciliation and proper-score session forecast loss calculation."""
    session_date = "2026-08-28"
    ticker = "NQ1"
    
    # 1. Strategies
    register_all_v0_strategies(db_path=temp_db)
    
    # 2. Plan
    PlanAdapter.save_plan_snapshot(
        PlanContext(
            session_date=session_date,
            ticker=ticker,
            preparation_cutoff_utc="2026-08-28T12:45:00Z",
            verbatim_plan_text="Bullish morning trend",
            primary_bias="BULLISH",
            wargamed_scenarios={"A": "Trend continuation"},
            invalidation_levels={"inv": 19950.0},
            max_intended_risk_bps=12.0,
            permitted_strategies=["STRAT_ALN_LPEU_V0_1"]
        ),
        db_path=temp_db
    )
    
    # 3. Forecast
    ForecastRegistrar.register_replay_forecast(
        session_date=session_date,
        ticker=ticker,
        model_version_id="MOD_V1",
        payload=ForecastSnapshotPayload(
            git_hash="git1",
            config_hash="cfg1",
            prob_r1=0.60,
            prob_r2=0.10,
            prob_dnp=0.10,
            prob_dwp=0.10,
            prob_rotational_chop=0.10,
            predicted_day_type="R1",
            predicted_bias="BULLISH"
        ),
        db_path=temp_db
    )
    
    # 4. Opportunity & Execution
    OpportunityLogger.record_opportunity(
        SignalOpportunity(
            opportunity_id="opp-1",
            session_date=session_date,
            ticker=ticker,
            strategy_version_id="STRAT_ALN_LPEU_V0_1",
            bar_timestamp_utc="2026-08-28T09:35:00Z",
            decision_time_utc="2026-08-28T09:35:00Z",
            signal_direction="LONG",
            trigger_price=20000.0,
            declared_stop_price=19976.0,
            declared_target_1_price=20020.0,
            stop_distance_bps=12.0,
            target_1_bps=10.0,
            feature_manifest={}
        ),
        db_path=temp_db
    )
    NT8BrokerAdapter.ingest_fills(
        fills=[{
            "session_date": session_date,
            "ticker": ticker,
            "broker_execution_id": "fill-1",
            "broker_order_id": "ord-1",
            "order_action": "BUY",
            "quantity": 1,
            "fill_price": 20000.0,
            "event_timestamp_utc": "2026-08-28T09:35:02Z",
            "strategy_version_id": "STRAT_ALN_LPEU_V0_1"
        }],
        account_id="Sim101",
        db_path=temp_db
    )
    
    # 5. Tape Actuals (Realized R1 Day Type)
    with sqlite3.connect(str(temp_db)) as conn:
        conn.execute(
            """
            INSERT INTO session_tape_actuals (
                actual_id, session_date, ticker, revision_seq, source_system,
                session_open, session_high, session_low, session_close, rth_close,
                session_range_bps, day_type_classification, quality_state, content_hash
            ) VALUES ('act-1', ?, ?, 1, 'STORAGE', 20000.0, 20150.0, 19980.0, 20140.0, 20140.0, 85.0, 'R1', 'CLEAN', 'h1');
            """,
            (session_date, ticker)
        )
        
    # Reconcile session
    summary = DailyProcessDeltaReconciler.reconcile_session(session_date, ticker, db_path=temp_db)
    
    assert summary.plan.plan_found is True
    assert summary.plan.primary_bias == "BULLISH"
    assert summary.forecast.forecast_found is True
    assert summary.forecast.session_brier_loss is not None
    assert summary.forecast.session_log_loss is not None
    assert summary.opportunities.executed_count == 1
    assert summary.executions.total_executions == 1
    assert summary.tape.realized_day_type == "R1"
    assert summary.permitted_strategies_respected is True
