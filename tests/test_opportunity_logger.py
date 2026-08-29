"""Pytest suite for OpportunityLogger & Strategy Registry V0 (Milestone 0.5)."""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from scripts.trading_brain.db.init_db import init_trading_brain_db
from scripts.trading_brain.signals.opportunity_logger import OpportunityLogger, SignalOpportunity
from scripts.trading_brain.strategies.registry_v0 import (
    StrategyRegistryV0,
    register_all_v0_strategies,
    verify_strategy_hash,
)


@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = Path(tmpdir) / "test_trading_brain.sqlite"
        init_trading_brain_db(db_path=db_path, verbose=False)
        yield db_path


def test_register_v0_strategies_and_drift_detection(temp_db):
    """Tests registering all 4 frozen strategy definitions."""
    register_all_v0_strategies(db_path=temp_db)
    
    with sqlite3.connect(str(temp_db)) as conn:
        cur = conn.execute("SELECT COUNT(*) AS c FROM strategy_versions;")
        assert cur.fetchone()[0] == 4
        
    aln_strat = StrategyRegistryV0.get_strategy("STRAT_ALN_LPEU_V0_1")
    assert aln_strat is not None
    assert verify_strategy_hash("STRAT_ALN_LPEU_V0_1", aln_strat["content_hash"]) is True


def test_record_opportunity_and_derive_all_disposition_states(temp_db):
    """Tests recording opportunities and deriving EXECUTED, PASSED, MISSED, and OFFLINE dispositions."""
    session_date = "2026-08-28"
    ticker = "NQ1"
    
    # 1. Opportunity 1: Executed (Matched fill)
    opp_1 = SignalOpportunity(
        opportunity_id="opp-test-1",
        session_date=session_date,
        ticker=ticker,
        strategy_version_id="STRAT_ALN_LPEU_V0_1",
        bar_timestamp_utc="2026-08-28T13:35:00Z",
        decision_time_utc="2026-08-28T13:35:01Z",
        signal_direction="LONG",
        trigger_price=20000.0,
        declared_stop_price=19980.0,
        declared_target_1_price=20020.0,
        stop_distance_bps=10.0,
        target_1_bps=10.0,
        feature_manifest={"aln": "LPEU"}
    )
    OpportunityLogger.record_opportunity(opp_1, db_path=temp_db)
    
    # 2. Opportunity 2: Passed (Trader took another trade in window)
    opp_2 = SignalOpportunity(
        opportunity_id="opp-test-2",
        session_date=session_date,
        ticker=ticker,
        strategy_version_id="STRAT_FIRECRACKER_V0_1",
        bar_timestamp_utc="2026-08-28T13:36:00Z",
        decision_time_utc="2026-08-28T13:36:01Z",
        signal_direction="SHORT",
        trigger_price=20010.0,
        declared_stop_price=20030.0,
        declared_target_1_price=19990.0,
        stop_distance_bps=10.0,
        target_1_bps=10.0,
        feature_manifest={"pattern": "FIRECRACKER"}
    )
    OpportunityLogger.record_opportunity(opp_2, db_path=temp_db)
    
    # 3. Opportunity 3: Missed (Trader online, no executions anywhere in window)
    opp_3 = SignalOpportunity(
        opportunity_id="opp-test-3",
        session_date=session_date,
        ticker=ticker,
        strategy_version_id="STRAT_P12_MID_V0_1",
        bar_timestamp_utc="2026-08-28T15:00:00Z",
        decision_time_utc="2026-08-28T15:00:01Z",
        signal_direction="LONG",
        trigger_price=20050.0,
        declared_stop_price=20030.0,
        declared_target_1_price=20070.0,
        stop_distance_bps=10.0,
        target_1_bps=10.0,
        feature_manifest={}
    )
    OpportunityLogger.record_opportunity(opp_3, db_path=temp_db)
    
    # Insert Execution matching Opp 1
    with sqlite3.connect(str(temp_db)) as conn:
        conn.execute(
            """
            INSERT INTO execution_events (
                execution_id, session_date, ticker, account_id, broker_execution_id,
                broker_order_id, order_action, order_type, quantity, fill_price,
                strategy_version_id, idempotency_key, event_timestamp_utc
            ) VALUES ('exec-1', '2026-08-28', 'NQ1', 'ACC1', 'b-1', 'b-ord-1', 'BUY', 'LIMIT', 1, 20000.5, 'STRAT_ALN_LPEU_V0_1', 'idemp-1', '2026-08-28T13:35:10Z');
            """
        )
        
    disp = OpportunityLogger.derive_dispositions(session_date, ticker, is_platform_online=True, db_path=temp_db)
    assert disp["total_opportunities"] == 3
    assert disp["dispositions"]["EXECUTED"] == 1
    assert disp["dispositions"]["PASSED"] == 1
    assert disp["dispositions"]["MISSED"] == 1
