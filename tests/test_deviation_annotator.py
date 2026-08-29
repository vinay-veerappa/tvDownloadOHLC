"""Pytest suite for DeviationAnnotator (Milestone 2.1)."""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from scripts.trading_brain.db.init_db import init_trading_brain_db
from scripts.trading_brain.guard.deviation_annotator import DeviationAnnotator
from scripts.trading_brain.plans.plan_adapter import PlanAdapter, PlanContext
from scripts.trading_brain.strategies.registry_v0 import register_all_v0_strategies


@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = Path(tmpdir) / "test_trading_brain.sqlite"
        init_trading_brain_db(db_path=db_path, verbose=False)
        yield db_path


def test_deviation_annotator_contrary_bias_and_unpermitted_strat(temp_db):
    """Tests detecting and logging contrary-bias and unpermitted-strategy deviations."""
    session_date = "2026-08-28"
    ticker = "NQ1"
    
    register_all_v0_strategies(db_path=temp_db)
    
    # Declare BEARISH plan with only STRAT_GOALPOST_BB_V0_1 permitted
    PlanAdapter.save_plan_snapshot(
        PlanContext(
            session_date=session_date,
            ticker=ticker,
            preparation_cutoff_utc="2026-08-28T12:45:00Z",
            verbatim_plan_text="Bearish session plan",
            primary_bias="BEARISH",
            wargamed_scenarios={},
            invalidation_levels={},
            max_intended_risk_bps=10.0,
            permitted_strategies=["STRAT_GOALPOST_BB_V0_1"]
        ),
        db_path=temp_db,
        received_at_utc="2026-08-28T12:30:00Z",
    )
    
    # Execution 1: BUY order on STRAT_ALN_LPEU_V0_1 -> BOTH violations (Contrary Bias + Unpermitted Strategy)
    exec_event = {
        "execution_id": "exec-dev-1",
        "session_date": session_date,
        "ticker": ticker,
        "order_action": "BUY",
        "fill_price": 20000.0,
        "strategy_version_id": "STRAT_ALN_LPEU_V0_1",
        "event_timestamp_utc": "2026-08-28T13:35:00Z"
    }
    
    ann_ids = DeviationAnnotator.evaluate_execution(exec_event, db_path=temp_db)
    assert len(ann_ids) == 2
    
    with sqlite3.connect(str(temp_db)) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT * FROM intervention_events WHERE source_event_id = 'exec-dev-1';")
        rows = cur.fetchall()
        assert len(rows) == 2
        rule_ids = {r["rule_id"] for r in rows}
        assert "PLAN_BIAS_DIRECTION_DEVIATION" in rule_ids
        assert "UNPERMITTED_STRATEGY_DEVIATION" in rule_ids
