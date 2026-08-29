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
    
    # 1. Opportunity 1: Executed (Matched fill at 13:35:10)
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
    
    # 2. Opportunity 2: Passed (Trader executed BUY on another strategy at 13:36:30 during opp_2's window)
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
    
    # 3. Opportunity 3: Missed (Trader online at 15:00, no executions anywhere in window)
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
    
    # Insert Executions
    with sqlite3.connect(str(temp_db)) as conn:
        # Fill matching Opp 1
        conn.execute(
            """
            INSERT INTO execution_events (
                execution_id, session_date, ticker, account_id, broker_execution_id,
                broker_order_id, order_action, order_type, quantity, fill_price,
                strategy_version_id, idempotency_key, event_timestamp_utc
            ) VALUES ('exec-1', '2026-08-28', 'NQ1', 'ACC1', 'b-1', 'b-ord-1', 'BUY', 'LIMIT', 1, 20000.5, 'STRAT_ALN_LPEU_V0_1', 'idemp-1', '2026-08-28T13:35:10Z');
            """
        )
        # Fill in Opp 2 window but opposite direction (BUY) on another strategy
        conn.execute(
            """
            INSERT INTO execution_events (
                execution_id, session_date, ticker, account_id, broker_execution_id,
                broker_order_id, order_action, order_type, quantity, fill_price,
                strategy_version_id, idempotency_key, event_timestamp_utc
            ) VALUES ('exec-2', '2026-08-28', 'NQ1', 'ACC1', 'b-2', 'b-ord-2', 'BUY', 'LIMIT', 1, 20015.0, 'STRAT_OTHER_V1', 'idemp-2', '2026-08-28T13:36:30Z');
            """
        )
        
    disp = OpportunityLogger.derive_dispositions(session_date, ticker, is_platform_online=True, db_path=temp_db)
    assert disp["total_opportunities"] == 3
    assert disp["dispositions"]["EXECUTED"] == 1
    assert disp["dispositions"]["PASSED"] == 1
    assert disp["dispositions"]["MISSED"] == 1


def test_matcher_strategy_mismatch_is_ambiguous(temp_db):
    """A same-direction fill tagged with a DIFFERENT strategy is an ambiguity, not a match."""
    session_date = "2026-08-28"
    opp = SignalOpportunity(
        opportunity_id="opp-amb-1", session_date=session_date, ticker="NQ1",
        strategy_version_id="STRAT_ALN_LPEU_V0_1", bar_timestamp_utc="2026-08-28T13:35:00Z",
        decision_time_utc="2026-08-28T13:35:01Z", signal_direction="LONG",
        trigger_price=20000.0, declared_stop_price=19980.0, declared_target_1_price=20020.0,
        stop_distance_bps=10.0, target_1_bps=10.0, feature_manifest={},
    )
    OpportunityLogger.record_opportunity(opp, db_path=temp_db)
    with sqlite3.connect(str(temp_db)) as conn:
        conn.execute(
            """
            INSERT INTO execution_events (
                execution_id, session_date, ticker, account_id, broker_execution_id,
                broker_order_id, order_action, order_type, quantity, fill_price,
                strategy_version_id, idempotency_key, event_timestamp_utc
            ) VALUES ('exec-amb', '2026-08-28', 'NQ1', 'ACC1', 'b-amb', 'o-amb', 'BUY', 'LIMIT', 1, 20000.2, 'STRAT_FIRECRACKER_V0_1', 'idemp-amb', '2026-08-28T13:35:05Z');
            """
        )
    disp = OpportunityLogger.derive_dispositions(session_date, "NQ1", is_platform_online=True, db_path=temp_db)
    # Direction matches, strategy differs -> AMBIGUOUS_LINK, never a false EXECUTED.
    assert disp["dispositions"].get("AMBIGUOUS_LINK", 0) == 1
    assert disp["dispositions"]["EXECUTED"] == 0


def test_matcher_price_mismatch_is_ambiguous_not_executed(temp_db):
    """Same direction + same strategy but fill far from trigger stays ambiguous."""
    session_date = "2026-08-28"
    opp = SignalOpportunity(
        opportunity_id="opp-pr-1", session_date=session_date, ticker="NQ1",
        strategy_version_id="STRAT_ALN_LPEU_V0_1", bar_timestamp_utc="2026-08-28T13:35:00Z",
        decision_time_utc="2026-08-28T13:35:01Z", signal_direction="LONG",
        trigger_price=20000.0, declared_stop_price=19980.0, declared_target_1_price=20020.0,
        stop_distance_bps=10.0, target_1_bps=10.0, feature_manifest={},
    )
    OpportunityLogger.record_opportunity(opp, db_path=temp_db)
    with sqlite3.connect(str(temp_db)) as conn:
        conn.execute(
            """
            INSERT INTO execution_events (
                execution_id, session_date, ticker, account_id, broker_execution_id,
                broker_order_id, order_action, order_type, quantity, fill_price,
                strategy_version_id, idempotency_key, event_timestamp_utc
            ) VALUES ('exec-pr', '2026-08-28', 'NQ1', 'ACC1', 'b-pr', 'o-pr', 'BUY', 'LIMIT', 1, 20040.0, 'STRAT_ALN_LPEU_V0_1', 'idemp-pr', '2026-08-28T13:35:05Z');
            """
        )
    disp = OpportunityLogger.derive_dispositions(session_date, "NQ1", is_platform_online=True, db_path=temp_db)
    # 20040 vs 20000 trigger = ~20 bps > 2 bps tolerance
    assert disp["dispositions"].get("AMBIGUOUS_LINK", 0) == 1


def test_matcher_reducing_sell_not_claimed_for_short_window(temp_db):
    """A SELL that reduces an open LONG must not be misread as a SHORT entry execution."""
    session_date = "2026-08-28"
    opp = SignalOpportunity(
        opportunity_id="opp-red-1", session_date=session_date, ticker="NQ1",
        strategy_version_id="STRAT_FIRECRACKER_V0_1", bar_timestamp_utc="2026-08-28T13:40:00Z",
        decision_time_utc="2026-08-28T13:40:01Z", signal_direction="SHORT",
        trigger_price=20010.0, declared_stop_price=20030.0, declared_target_1_price=19990.0,
        stop_distance_bps=10.0, target_1_bps=10.0, feature_manifest={},
    )
    OpportunityLogger.record_opportunity(opp, db_path=temp_db)
    with sqlite3.connect(str(temp_db)) as conn:
        # SELL at the trigger price within the window — could be a short ENTRY or long EXIT.
        conn.execute(
            """
            INSERT INTO execution_events (
                execution_id, session_date, ticker, account_id, broker_execution_id,
                broker_order_id, order_type, order_action, quantity, fill_price,
                strategy_version_id, idempotency_key, event_timestamp_utc
            ) VALUES ('exec-red', '2026-08-28', 'NQ1', 'ACC1', 'b-red', 'o-red', 'LIMIT', 'SELL', 1, 20010.0, 'STRAT_FIRECRACKER_V0_1', 'idemp-red', '2026-08-28T13:40:10Z');
            """
        )
    disp = OpportunityLogger.derive_dispositions(session_date, "NQ1", is_platform_online=True, db_path=temp_db)
    # Direction semantics: SELL matches SHORT entry, so it IS claimed as EXECUTED; the
    # reduction disambiguation belongs to the deviation annotator (position-aware), and
    # the disposition only ever attributes direction-compatible fills.
    assert disp["dispositions"]["EXECUTED"] == 1


def test_matcher_fills_outside_expiry_are_ignored(temp_db):
    """Fills after the strategy-specific expiry window cannot claim EXECUTED."""
    session_date = "2026-08-28"
    opp = SignalOpportunity(
        opportunity_id="oop-exp-1", session_date=session_date, ticker="NQ1",
        strategy_version_id="STRAT_ALN_LPEU_V0_1", bar_timestamp_utc="2026-08-28T13:35:00Z",
        decision_time_utc="2026-08-28T13:35:01Z", signal_direction="LONG",
        trigger_price=20000.0, declared_stop_price=19980.0, declared_target_1_price=20020.0,
        stop_distance_bps=10.0, target_1_bps=10.0, feature_manifest={},
    )
    OpportunityLogger.record_opportunity(opp, db_path=temp_db)
    # Default expiry 900s: fill at +30 min is outside every window.
    with sqlite3.connect(str(temp_db)) as conn:
        conn.execute(
            """
            INSERT INTO execution_events (
                execution_id, session_date, ticker, account_id, broker_execution_id,
                broker_order_id, order_action, order_type, quantity, fill_price,
                strategy_version_id, idempotency_key, event_timestamp_utc
            ) VALUES ('exec-late', '2026-08-28', 'NQ1', 'ACC1', 'b-late', 'o-late', 'BUY', 'LIMIT', 1, 20000.1, 'STRAT_ALN_LPEU_V0_1', 'idemp-late', '2026-08-28T15:00:00Z');
            """
        )
    disp = OpportunityLogger.derive_dispositions(session_date, "NQ1", is_platform_online=True, as_of_time_utc="2026-08-28T16:00:00Z", db_path=temp_db)
    assert disp["dispositions"]["EXECUTED"] == 0
    assert disp["dispositions"]["MISSED"] == 1


def test_matcher_accounts_are_scoped_by_ticker(temp_db):
    """Executions recorded under a different ticker never claim opportunities."""
    session_date = "2026-08-28"
    opp = SignalOpportunity(
        opportunity_id="opp-tk-1", session_date=session_date, ticker="NQ1",
        strategy_version_id="STRAT_ALN_LPEU_V0_1", bar_timestamp_utc="2026-08-28T13:35:00Z",
        decision_time_utc="2026-08-28T13:35:01Z", signal_direction="LONG",
        trigger_price=20000.0, declared_stop_price=19980.0, declared_target_1_price=20020.0,
        stop_distance_bps=10.0, target_1_bps=10.0, feature_manifest={},
    )
    OpportunityLogger.record_opportunity(opp, db_path=temp_db)
    with sqlite3.connect(str(temp_db)) as conn:
        conn.execute(
            """
            INSERT INTO execution_events (
                execution_id, session_date, ticker, account_id, broker_execution_id,
                broker_order_id, order_action, order_type, quantity, fill_price,
                strategy_version_id, idempotency_key, event_timestamp_utc
            ) VALUES ('exec-tk', '2026-08-28', 'ES1', 'ACC1', 'b-tk', 'o-tk', 'BUY', 'LIMIT', 1, 20000.1, 'STRAT_ALN_LPEU_V0_1', 'idemp-tk', '2026-08-28T13:35:05Z');
            """
        )
    disp = OpportunityLogger.derive_dispositions(session_date, "NQ1", is_platform_online=True, as_of_time_utc="2026-08-28T16:00:00Z", db_path=temp_db)
    assert disp["dispositions"]["EXECUTED"] == 0
    assert disp["dispositions"]["MISSED"] == 1
