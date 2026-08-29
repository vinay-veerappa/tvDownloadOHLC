"""Pytest suite for Trading Second Brain Schema, Immutability & WAL Integrity (Milestone 0.1)."""

import sqlite3
import tempfile
from pathlib import Path
import pytest
from scripts.trading_brain.db.init_db import EXPECTED_TABLES, init_trading_brain_db

PROTECTED_APPEND_ONLY_TABLES = [
    "information_items", "information_item_review_events", "plan_snapshots",
    "plan_lifecycle_events", "plan_amendments", "forecast_run_inputs",
    "forecast_snapshots", "signal_opportunities", "signal_disposition_events",
    "signal_outcomes", "session_tape_actuals", "execution_events",
    "intervention_events", "drill_attempts", "behavioral_declarations",
    "unmatched_link_events", "candidate_finding_events", "strategy_versions",
    "model_versions"
]

@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = Path(tmpdir) / "test_trading_brain.sqlite"
        init_trading_brain_db(db_path=db_path, verbose=False)
        yield db_path

def test_schema_initialization(temp_db):
    assert temp_db.exists()
    with sqlite3.connect(str(temp_db)) as conn:
        cur = conn.execute("PRAGMA journal_mode;")
        assert cur.fetchone()[0].lower() == "wal"
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = {row[0] for row in cur.fetchall()}
        for t in EXPECTED_TABLES:
            assert t in tables, f"Missing table: {t}"

def test_immutability_triggers_all_tables(temp_db):
    with sqlite3.connect(str(temp_db)) as conn:
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='trigger';")
        triggers = {row[0] for row in cur.fetchall()}
        for table in PROTECTED_APPEND_ONLY_TABLES:
            assert (f"trg_prevent_update_{table}" in triggers or f"trg_immutable_{table}_update" in triggers)
            assert (f"trg_prevent_delete_{table}" in triggers or f"trg_immutable_{table}_delete" in triggers)

def test_session_tape_actuals_revisions_and_view(temp_db):
    with sqlite3.connect(str(temp_db)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("INSERT INTO session_tape_actuals (actual_id, session_date, ticker, revision_seq, source_system, session_open, session_high, session_low, session_close, rth_close, session_range_bps, day_type_classification, expected_bar_count, actual_bar_count, content_hash, quality_state) VALUES ('act-1', '2026-08-28', 'NQ1', 1, 'PARQUET', 20000.0, 20100.0, 19950.0, 20050.0, 20050.0, 75.0, 'R1', 390, 390, 'hash1', 'CLEAN');")
        conn.execute("INSERT INTO session_tape_actuals (actual_id, session_date, ticker, revision_seq, source_system, session_open, session_high, session_low, session_close, rth_close, session_range_bps, day_type_classification, expected_bar_count, actual_bar_count, content_hash, quality_state, supersedes_actual_id) VALUES ('act-2', '2026-08-28', 'NQ1', 2, 'PARQUET_REVISION', 20000.0, 20120.0, 19950.0, 20070.0, 20070.0, 85.0, 'DWP', 390, 390, 'hash2', 'CLEAN', 'act-1');")
        cur = conn.execute("SELECT * FROM v_session_tape_actuals_current WHERE session_date = '2026-08-28' AND ticker = 'NQ1';")
        row = cur.fetchone()
        assert row is not None
        assert row["actual_id"] == "act-2"
        assert row["revision_seq"] == 2

def test_information_item_review_events_and_view(temp_db):
    with sqlite3.connect(str(temp_db)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("INSERT INTO information_items (information_id, evidence_class, time_orientation, source_type, title, verbatim_text, available_at_utc) VALUES ('item-1', 'DOCTRINE', 'EX_ANTE', 'TRANSCRIPT', 'Rule 1', 'Rule text', '2026-08-28T08:00:00Z');")
        conn.execute("INSERT INTO information_item_review_events (review_event_id, information_id, review_state, reviewer, event_timestamp_utc) VALUES ('rev-1', 'item-1', 'ACCEPTED', 'USER', '2026-08-28T08:10:00Z');")
        cur = conn.execute("SELECT * FROM v_information_items_active WHERE information_id = 'item-1';")
        row = cur.fetchone()
        assert row is not None
        assert row["active_review_state"] == "ACCEPTED"


def test_schema_version_stamped_and_refuses_downgrade(temp_db):
    """SCHEMA_VERSION must be stamped into PRAGMA user_version; newer DBs refuse downgrade."""
    from scripts.trading_brain.db.connection import get_db_connection
    from scripts.trading_brain.db import init_db as init_db_mod

    with get_db_connection(temp_db) as conn:
        stamped = int(conn.execute("PRAGMA user_version;").fetchone()[0])
    assert stamped == init_db_mod.SCHEMA_VERSION >= 2

    # Simulate a database migrated by NEWER code: init must refuse with a clear error
    with get_db_connection(temp_db) as conn:
        conn.execute(f"PRAGMA user_version = {init_db_mod.SCHEMA_VERSION + 1};")
    with pytest.raises(ValueError, match="newer than this code expects"):
        init_trading_brain_db(db_path=temp_db, verbose=False)
