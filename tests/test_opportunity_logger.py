"""Pytest suite for OpportunityLogger and Strategy Registry V0 (Milestone 0.5)."""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from scripts.trading_brain.db.init_db import init_trading_brain_db
from scripts.trading_brain.signals.opportunity_logger import OpportunityLogger, SignalOpportunity
from scripts.trading_brain.strategies.registry_v0 import register_all_v0_strategies


@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = Path(tmpdir) / "test_trading_brain.sqlite"
        init_trading_brain_db(db_path=db_path, verbose=False)
        yield db_path


def test_register_v0_strategies(temp_db):
    """Tests loading and registering frozen V0 strategy JSON definitions."""
    registered = register_all_v0_strategies(db_path=temp_db)
    assert len(registered) >= 4
    assert "STRAT_ALN_LPEU_V0_1" in registered
    assert "STRAT_FIRECRACKER_V0_1" in registered
    assert "STRAT_GOALPOST_BB_V0_1" in registered
    assert "STRAT_P12_MID_RETEST_V0_1" in registered
    
    with sqlite3.connect(str(temp_db)) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT * FROM strategy_versions WHERE strategy_version_id = 'STRAT_ALN_LPEU_V0_1';")
        row = cur.fetchone()
        assert row is not None
        assert row["strategy_family"] == "ALN_LPEU"
        assert row["status"] == "EXPERIMENTAL_CAPTURE_ONLY"


def test_record_opportunity_and_derive_dispositions(temp_db):
    """Tests opportunity recording, mechanical disposition matching, and unmatched execution routing."""
    register_all_v0_strategies(db_path=temp_db)
    
    opp = SignalOpportunity(
        opportunity_id="opp-123",
        session_date="2026-08-28",
        ticker="NQ1",
        strategy_version_id="STRAT_ALN_LPEU_V0_1",
        bar_timestamp_utc="2026-08-28T09:35:00Z",
        decision_time_utc="2026-08-28T09:35:00Z",
        trigger_price=20000.0,
        declared_stop_price=19976.0,
        declared_target_1_price=20020.0,
        stop_distance_bps=12.0,
        target_1_bps=10.0,
        feature_manifest={"poc": 20000.0, "london_high": 20050.0}
    )
    
    opp_id = OpportunityLogger.record_opportunity(opp, db_path=temp_db)
    assert opp_id == "opp-123"
    
    # 1. Insert a matching execution (within 5 seconds, fill price 20001.0 -> 0.5 bps diff)
    with sqlite3.connect(str(temp_db)) as conn:
        conn.execute(
            """
            INSERT INTO execution_events (
                execution_id, session_date, ticker, account_id, broker_execution_id,
                broker_order_id, order_action, order_type, quantity, fill_price,
                idempotency_key, event_timestamp_utc
            ) VALUES ('exec-match', '2026-08-28', 'NQ1', 'ACC1', 'b-ex-1', 'b-ord-1', 'BUY', 'MARKET', 1, 20001.0, 'id-1', '2026-08-28T09:35:05Z');
            """
        )
        
        # Insert a second discretionary execution (no matching opportunity)
        conn.execute(
            """
            INSERT INTO execution_events (
                execution_id, session_date, ticker, account_id, broker_execution_id,
                broker_order_id, order_action, order_type, quantity, fill_price,
                idempotency_key, event_timestamp_utc
            ) VALUES ('exec-disc', '2026-08-28', 'NQ1', 'ACC1', 'b-ex-2', 'b-ord-2', 'BUY', 'MARKET', 1, 20200.0, 'id-2', '2026-08-28T14:00:00Z');
            """
        )
        
    # Derive mechanical dispositions
    res = OpportunityLogger.derive_dispositions(session_date="2026-08-28", ticker="NQ1", db_path=temp_db)
    assert res["total_opportunities"] == 1
    assert res["dispositions"]["EXECUTED"] == 1
    assert res["dispositions"]["PASSED"] == 0
    assert res["unmatched_executions"] == 1
    
    # Verify unmatched link event was created
    with sqlite3.connect(str(temp_db)) as conn:
        conn.row_factory = sqlite3.Row
        link = conn.execute("SELECT * FROM unmatched_link_events WHERE execution_id = 'exec-disc';").fetchone()
        assert link is not None
        assert link["resolution_status"] == "OPEN"


def test_intrabar_ambiguity_outcome_bounds(temp_db):
    """Tests recording an ambiguous 1m bar outcome with preserved dual bounds."""
    register_all_v0_strategies(db_path=temp_db)
    
    opp = SignalOpportunity(
        opportunity_id="opp-ambig",
        session_date="2026-08-28",
        ticker="NQ1",
        strategy_version_id="STRAT_FIRECRACKER_V0_1",
        bar_timestamp_utc="2026-08-28T09:30:00Z",
        decision_time_utc="2026-08-28T09:30:00Z",
        trigger_price=20000.0,
        declared_stop_price=19980.0,
        declared_target_1_price=20020.0,
        stop_distance_bps=10.0,
        target_1_bps=10.0,
        feature_manifest={}
    )
    OpportunityLogger.record_opportunity(opp, db_path=temp_db)
    
    outcome_id = OpportunityLogger.record_signal_outcome(
        opportunity_id="opp-ambig",
        observed_outcome="AMBIGUOUS_INTRABAR_ORDER",
        pessimistic_bound="STOP_HIT",
        optimistic_bound="TARGET_REACHED",
        realized_mfe_bps=12.0,
        realized_mae_bps=10.0,
        bars_held=1,
        db_path=temp_db
    )
    assert outcome_id is not None
    
    with sqlite3.connect(str(temp_db)) as conn:
        conn.row_factory = sqlite3.Row
        out = conn.execute("SELECT * FROM signal_outcomes WHERE opportunity_id = 'opp-ambig';").fetchone()
        assert out is not None
        assert out["observed_outcome"] == "AMBIGUOUS_INTRABAR_ORDER"
        assert out["pessimistic_bound"] == "STOP_HIT"
        assert out["optimistic_bound"] == "TARGET_REACHED"
