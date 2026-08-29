"""Pytest suite for WS-2.2 Prisma TradePlan -> plan_snapshots sync bridge."""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from scripts.trading_brain.db.init_db import init_trading_brain_db
from scripts.trading_brain.bridges.prisma_plan_bridge import (
    _detect_bias,
    _parse_risk_bps,
    sync_tradplans,
)


@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = Path(tmpdir) / "test_trading_brain.sqlite"
        init_trading_brain_db(db_path=db_path, verbose=False)
        yield db_path


@pytest.fixture
def prisma_db(tmp_path):
    """Creates a synthetic Prisma SQLite with the TradePlan schema and 3 rows."""
    p = tmp_path / "dev.db"
    con = sqlite3.connect(str(p))
    con.execute("""
        CREATE TABLE TradePlan (
            id TEXT PRIMARY KEY,
            date TEXT,
            instrument TEXT,
            setup TEXT,
            entryPlan TEXT,
            exitPlan TEXT,
            riskPlan TEXT,
            linkedTradeId TEXT,
            createdAt TEXT,
            updatedAt TEXT
        );
    """)
    con.execute("""
        INSERT INTO TradePlan (id, date, instrument, setup, entryPlan, exitPlan, riskPlan, createdAt, updatedAt)
        VALUES
        ('tp-1', '2026-08-20T05:00:00Z', 'NQ1', 'ALN_LPEU', 'Long on pullback to P12 mid', 'Cover the queen +10 bps', 'Max 12 bps stop', '2026-08-20T04:00:00Z', '2026-08-20T04:30:00Z'),
        ('tp-2', '2026-08-21T05:00:00Z', 'ES1', 'GOALPOST_BB', 'Short after 09:45 sweep', 'Trail runner', 'Risk 8 bps', '2026-08-21T04:00:00Z', '2026-08-21T04:30:00Z'),
        ('tp-3', '2026-08-22T05:00:00Z', 'NQ1', NULL, 'Wait for elimination', 'Flat by 15:30', NULL, '2026-08-22T04:00:00Z', '2026-08-22T04:30:00Z');
    """)
    con.commit()
    con.close()
    return p


def test_bias_detection_conservative():
    assert _detect_bias("Long on pullback") == "BULLISH"
    assert _detect_bias("Short after sweep") == "BEARISH"
    assert _detect_bias("Long the sweep, ready to short failure") == "NEUTRAL"
    assert _detect_bias("No directional language here") == "NEUTRAL"
    assert _detect_bias(None, None) == "NEUTRAL"


def test_risk_bps_parsing():
    assert _parse_risk_bps("Max 12 bps stop") == 12.0
    assert _parse_risk_bps("Risk 8.5 basis points") == 8.5
    assert _parse_risk_bps("No bps mentioned") == 15.0
    assert _parse_risk_bps(None) == 15.0


def test_sync_mirrors_all_and_is_idempotent(temp_db, prisma_db):
    # First sync: 3 plans mirrored
    report1 = sync_tradplans(prisma_db_path=prisma_db, canonical_db_path=temp_db)
    assert report1["found"] == 3
    assert report1["mirrored"] == 3

    with sqlite3.connect(str(temp_db)) as conn:
        rows = conn.execute(
            "SELECT source_system, source_plan_id, primary_bias FROM plan_snapshots WHERE source_system = 'PRISMA_WEB'"
        ).fetchall()
        assert len(rows) == 3
        for i, src_id in enumerate(["tp-1", "tp-2", "tp-3"]):
            assert any(r[1] == src_id for r in rows)

    # Second sync: zero new (idempotent)
    report2 = sync_tradplans(prisma_db_path=prisma_db, canonical_db_path=temp_db)
    assert report2["found"] == 0
    assert report2["mirrored"] == 0


def test_mirrored_plan_verbatim_text(temp_db, prisma_db):
    sync_tradplans(prisma_db_path=prisma_db, canonical_db_path=temp_db)
    with sqlite3.connect(str(temp_db)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT verbatim_plan_text, max_intended_risk_bps FROM plan_snapshots WHERE source_plan_id = 'tp-1'").fetchone()
        assert "Long on pullback to P12 mid" in row["verbatim_plan_text"]
        assert "Mirrored verbatim from Prisma TradePlan tp-1" in row["verbatim_plan_text"]
        assert row["max_intended_risk_bps"] == 12.0