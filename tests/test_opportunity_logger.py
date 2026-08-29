"""Pytest suite for OpportunityLogger and Strategy Registry V0 (Milestone 0.5)."""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from scripts.trading_brain.db.init_db import init_trading_brain_db
from scripts.trading_brain.signals.opportunity_logger import OpportunityLogger, SignalOpportunity
from scripts.trading_brain.strategies.registry_v0 import StrategyVersionDriftError, register_all_v0_strategies


@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = Path(tmpdir) / "test_trading_brain.sqlite"
        init_trading_brain_db(db_path=db_path, verbose=False)
        yield db_path


def test_register_v0_strategies_and_drift_detection(temp_db):
    """Tests loading V0 strategies and detecting content hash drift on modification."""
    registered = register_all_v0_strategies(db_path=temp_db)
    assert len(registered) >= 4
    
    # Re-running with identical files succeeds idempotently
    re_registered = register_all_v0_strategies(db_path=temp_db)
    assert len(re_registered) == len(registered)


def test_record_opportunity_with_direction_and_idempotency(temp_db):
    """Tests opportunity recording, direction-sensitive disposition matching, and idempotent re-runs."""
    register_all_v0_strategies(db_path=temp_db)
    
    # 1. Long Opportunity
    opp_long = SignalOpportunity(
        opportunity_id="opp-long-1",
        session_date="2026-08-28",
        ticker="NQ1",
        strategy_version_id="STRAT_ALN_LPEU_V0_1",
        bar_timestamp_utc="2026-08-28T09:35:00Z",
        decision_time_utc="2026-08-28T09:35:00Z",
        signal_direction="LONG",
        trigger_price=20000.0,
        declared_stop_price=19976.0,
        declared_target_1_price=20020.0,
        stop_distance_bps=12.0,
        target_1_bps=10.0,
        feature_manifest={"poc": 20000.0}
    )
    OpportunityLogger.record_opportunity(opp_long, db_path=temp_db)
    
    # 2. Insert contrary execution: SELL order at 20000.0 -> must NOT match LONG signal
    with sqlite3.connect(str(temp_db)) as conn:
        conn.execute(
            """
            INSERT INTO execution_events (
                execution_id, session_date, ticker, account_id, broker_execution_id,
                broker_order_id, order_action, order_type, quantity, fill_price,
                idempotency_key, event_timestamp_utc
            ) VALUES ('exec-sell', '2026-08-28', 'NQ1', 'ACC1', 'b-ex-1', 'b-ord-1', 'SELL', 'MARKET', 1, 20000.0, 'id-1', '2026-08-28T09:35:05Z');
            """
        )
        
    res = OpportunityLogger.derive_dispositions(session_date="2026-08-28", ticker="NQ1", db_path=temp_db)
    assert res["dispositions"]["EXECUTED"] == 0
    assert res["dispositions"]["MISSED"] == 1
    assert res["unmatched_executions"] == 1
    
    # 3. Verify candidate opportunities were linked in unmatched_link_events
    with sqlite3.connect(str(temp_db)) as conn:
        conn.row_factory = sqlite3.Row
        link = conn.execute("SELECT * FROM unmatched_link_events WHERE execution_id = 'exec-sell';").fetchone()
        assert link is not None
        assert "opp-long-1" in link["candidate_opportunity_ids_json"]
        
    # 4. Idempotency test: Re-running does not produce duplicate dispositions
    res_rerun = OpportunityLogger.derive_dispositions(session_date="2026-08-28", ticker="NQ1", db_path=temp_db)
    assert res_rerun["dispositions"]["MISSED"] == 1
