"""Pytest suite for OutboxProjector (Milestone 0.3b)."""

import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

from scripts.trading_brain.db.connection import get_db_connection
from scripts.trading_brain.db.init_db import init_trading_brain_db
from scripts.trading_brain.migrations.outbox_projector import DatabasePausedError, OutboxProjector


@pytest.fixture
def outbox_env():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        tmp_path = Path(tmpdir)
        canon_db = tmp_path / "trading_brain.sqlite"
        init_trading_brain_db(db_path=canon_db, verbose=False)
        
        sys_db = tmp_path / "system_wargames.sqlite"
        mkt_db = tmp_path / "market_actuals.sqlite"
        
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
    
    with get_db_connection(env["canon_db"]) as conn:
        OutboxProjector.enqueue_outbox_item(
            conn=conn,
            destination_db="system_wargames",
            canonical_table="forecast_snapshots",
            canonical_id="fc-test-1",
            payload={"prediction_id": "pred-100", "session_date": "2026-08-28", "ticker": "NQ1", "spot_price": 20050.0}
        )
        
    projector = OutboxProjector(
        canonical_db_path=env["canon_db"],
        system_wargames_path=env["sys_db"],
        market_actuals_path=env["mkt_db"]
    )
    res = projector.project_pending()
    assert res["projected"] == 1
    assert res["failed"] == 0
    
    with sqlite3.connect(str(env["sys_db"])) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM system_wargames WHERE prediction_id = 'pred-100';").fetchone()
        assert row is not None
        assert row["spot_price"] == 20050.0


def test_outbox_paused_target_mode(outbox_env):
    """Tests that WARGAME_DB_TARGET=PAUSED blocks enqueuing with DatabasePausedError."""
    env = outbox_env
    os.environ["WARGAME_DB_TARGET"] = "PAUSED"
    try:
        with get_db_connection(env["canon_db"]) as conn:
            with pytest.raises(DatabasePausedError):
                OutboxProjector.enqueue_outbox_item(
                    conn=conn,
                    destination_db="system_wargames",
                    canonical_table="forecast_snapshots",
                    canonical_id="fc-pause",
                    payload={}
                )
    finally:
        os.environ["WARGAME_DB_TARGET"] = "DUAL_OUTBOX"
