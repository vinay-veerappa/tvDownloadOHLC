"""Pytest suite for NT8BrokerAdapter (Milestone 0.6)."""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from scripts.trading_brain.db.init_db import init_trading_brain_db
from scripts.trading_brain.ingest.nt8_broker_adapter import NT8BrokerAdapter


@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = Path(tmpdir) / "test_trading_brain.sqlite"
        init_trading_brain_db(db_path=db_path, verbose=False)
        yield db_path


def test_ingest_fills_and_cursor_checkpoint(temp_db):
    """Tests execution fill ingestion, cursor checkpointing, and duplicate skipping."""
    fills = [
        {
            "session_date": "2026-08-28",
            "ticker": "NQ1",
            "broker_execution_id": "exec-101",
            "broker_order_id": "ord-201",
            "order_action": "BUY",
            "order_type": "LIMIT",
            "quantity": 2,
            "fill_price": 20000.0,
            "commission_usd": 4.10,
            "event_timestamp_utc": "2026-08-28T09:35:00Z",
            "cursor": "c-101"
        },
        {
            "session_date": "2026-08-28",
            "ticker": "NQ1",
            "broker_execution_id": "exec-102",
            "broker_order_id": "ord-202",
            "order_action": "SELL",
            "order_type": "LIMIT",
            "quantity": 1,
            "fill_price": 20020.0,
            "commission_usd": 2.05,
            "event_timestamp_utc": "2026-08-28T09:45:00Z",
            "cursor": "c-102"
        }
    ]
    
    # Ingest fills
    res1 = NT8BrokerAdapter.ingest_fills(fills, account_id="Sim101", endpoint_name="nt_fill_events", db_path=temp_db)
    assert res1["ingested_count"] == 2
    assert res1["skipped_count"] == 0
    assert res1["last_cursor"] == "c-102"
    
    # Cursor saved in broker_ingest_state
    cursor = NT8BrokerAdapter.get_last_cursor("nt_fill_events", "Sim101", db_path=temp_db)
    assert cursor == "c-102"
    
    # Re-ingesting same fills skips duplicates
    res2 = NT8BrokerAdapter.ingest_fills(fills, account_id="Sim101", endpoint_name="nt_fill_events", db_path=temp_db)
    assert res2["ingested_count"] == 0
    assert res2["skipped_count"] == 2


def test_reconcile_positions(temp_db):
    """Tests position reconstruction and drift calculation."""
    fills = [
        {"session_date": "2026-08-28", "ticker": "NQ1", "broker_execution_id": "e-1", "order_action": "BUY", "quantity": 3, "fill_price": 20000.0},
        {"session_date": "2026-08-28", "ticker": "NQ1", "broker_execution_id": "e-2", "order_action": "SELL", "quantity": 1, "fill_price": 20010.0}
    ]
    NT8BrokerAdapter.ingest_fills(fills, account_id="Sim101", db_path=temp_db)
    
    # Broker reports 2 contracts long -> reconciled = True
    rec_match = NT8BrokerAdapter.reconcile_positions(account_id="Sim101", broker_position=2, session_date="2026-08-28", db_path=temp_db)
    assert rec_match["reconciled"] is True
    assert rec_match["reconstructed_position"] == 2
    assert rec_match["drift"] == 0
    
    # Broker reports 0 contracts -> drift = -2 -> reconciled = False
    rec_drift = NT8BrokerAdapter.reconcile_positions(account_id="Sim101", broker_position=0, session_date="2026-08-28", db_path=temp_db)
    assert rec_drift["reconciled"] is False
    assert rec_drift["drift"] == -2


def test_ingest_interventions(temp_db):
    """Tests ingesting RiskGuard lockouts and rule interventions."""
    interventions = [
        {
            "session_date": "2026-08-28",
            "ticker": "NQ1",
            "account_id": "Sim101",
            "producer": "NT8_RISKGUARD_CS",
            "producer_version": "1.2.0",
            "authority_class": "HARD_LOCKOUT_ENFORCED",
            "action_mode": "ACTING",
            "rule_id": "DAILY_MAX_LOSS_LIMIT",
            "rule_version": "1.0.0",
            "observed_value": -1520.0,
            "threshold_value": -1500.0,
            "enforced": True,
            "idempotency_key": "lockout-20260828-001",
            "event_timestamp_utc": "2026-08-28T10:15:00Z"
        }
    ]
    
    res = NT8BrokerAdapter.ingest_interventions(interventions, db_path=temp_db)
    assert res["ingested_count"] == 1
    assert res["skipped_count"] == 0
    
    with sqlite3.connect(str(temp_db)) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT * FROM intervention_events WHERE idempotency_key = 'lockout-20260828-001';")
        row = cur.fetchone()
        assert row is not None
        assert row["rule_id"] == "DAILY_MAX_LOSS_LIMIT"
        assert row["observed_value"] == -1520.0
        assert row["enforced"] == 1
