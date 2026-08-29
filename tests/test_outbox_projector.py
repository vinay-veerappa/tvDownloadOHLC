"""Pytest suite for OutboxProjector (Milestone 0.3b)."""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from scripts.trading_brain.db.connection import get_db_connection
from scripts.trading_brain.db.init_db import init_trading_brain_db
from scripts.trading_brain.migrations.outbox_projector import OutboxProjector


@pytest.fixture
def outbox_env():
    """Sets up an isolated test database and legacy destination databases."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        tmp_path = Path(tmpdir)
        canon_db = tmp_path / "trading_brain.sqlite"
        init_trading_brain_db(db_path=canon_db, verbose=False)
        
        sys_db = tmp_path / "system_wargames.sqlite"
        mkt_db = tmp_path / "market_actuals.sqlite"
        
        # Initialize legacy tables
        with sqlite3.connect(str(sys_db)) as conn:
            conn.execute(
                """
                CREATE TABLE system_wargames (
                    prediction_id TEXT PRIMARY KEY,
                    session_date DATE,
                    ticker TEXT,
                    spot_price REAL
                );
                """
            )
            
        with sqlite3.connect(str(mkt_db)) as conn:
            conn.execute(
                """
                CREATE TABLE market_actuals (
                    session_id TEXT PRIMARY KEY,
                    session_date DATE,
                    ticker TEXT,
                    rth_close REAL
                );
                """
            )
            
        yield {
            "canon_db": canon_db,
            "sys_db": sys_db,
            "mkt_db": mkt_db
        }


def test_outbox_enqueue_and_project(outbox_env):
    """Tests atomic canonical insert + outbox enqueue, followed by successful asynchronous projection."""
    env = outbox_env
    
    # 1. Enqueue item into canonical outbox
    with get_db_connection(env["canon_db"]) as conn:
        OutboxProjector.enqueue_outbox_item(
            conn=conn,
            destination_db="system_wargames",
            canonical_table="forecast_snapshots",
            canonical_id="fc-test-1",
            payload={"prediction_id": "pred-100", "session_date": "2026-08-28", "ticker": "NQ1", "spot_price": 20050.0}
        )
        
    # 2. Project pending
    projector = OutboxProjector(
        canonical_db_path=env["canon_db"],
        system_wargames_path=env["sys_db"],
        market_actuals_path=env["mkt_db"]
    )
    res = projector.project_pending()
    assert res["projected"] == 1
    assert res["failed"] == 0
    
    # 3. Verify destination legacy SQLite table has the row
    with sqlite3.connect(str(env["sys_db"])) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM system_wargames WHERE prediction_id = 'pred-100';").fetchone()
        assert row is not None
        assert row["spot_price"] == 20050.0
        
    # 4. Verify outbox record is marked PROJECTED
    with get_db_connection(env["canon_db"]) as conn:
        out = conn.execute("SELECT * FROM legacy_projection_outbox WHERE canonical_id = 'fc-test-1';").fetchone()
        assert out["status"] == "PROJECTED"
        assert out["projected_at_utc"] is not None


def test_outbox_retry_and_dead_letter(outbox_env):
    """Tests that errors during legacy projection increment retry counter and transition to DEAD_LETTER."""
    env = outbox_env
    
    # Enqueue item targeting non-existent column in legacy table (triggers sqlite error)
    with get_db_connection(env["canon_db"]) as conn:
        OutboxProjector.enqueue_outbox_item(
            conn=conn,
            destination_db="system_wargames",
            canonical_table="forecast_snapshots",
            canonical_id="fc-bad",
            payload={"prediction_id": "pred-bad", "non_existent_column": 123}
        )
        
    projector = OutboxProjector(
        canonical_db_path=env["canon_db"],
        system_wargames_path=env["sys_db"],
        market_actuals_path=env["mkt_db"],
        max_retries=2
    )
    
    # Attempt 1 -> fails and stays PENDING (attempt_count = 1)
    res1 = projector.project_pending()
    assert res1["failed"] == 1
    
    with get_db_connection(env["canon_db"]) as conn:
        out = conn.execute("SELECT * FROM legacy_projection_outbox WHERE canonical_id = 'fc-bad';").fetchone()
        assert out["status"] == "PENDING"
        assert out["attempt_count"] == 1
        
    # Attempt 2 -> fails and reaches max_retries=2 -> DEAD_LETTER
    res2 = projector.project_pending()
    assert res2["dead_letter"] == 1
    
    with get_db_connection(env["canon_db"]) as conn:
        out = conn.execute("SELECT * FROM legacy_projection_outbox WHERE canonical_id = 'fc-bad';").fetchone()
        assert out["status"] == "DEAD_LETTER"
        assert out["attempt_count"] == 2
