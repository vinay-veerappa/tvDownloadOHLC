"""Pytest suite for BlindedDrillEngine (Milestone 2.3)."""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from scripts.trading_brain.db.init_db import init_trading_brain_db
from scripts.trading_brain.practice.drill_engine import BlindedDrillEngine, DrillDeclaration


@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = Path(tmpdir) / "test_trading_brain.sqlite"
        init_trading_brain_db(db_path=db_path, verbose=False)
        yield db_path


def test_blinded_drill_generation_and_evaluation(temp_db):
    """Tests generating blinded drill, locking declaration, and scoring process adherence."""
    drill_ctx = BlindedDrillEngine.generate_blinded_drill(
        drill_type="RECOGNITION",
        dataset_split="TRAINING",
        session_date="2026-08-28",
        ticker="NQ1"
    )
    
    assert len(drill_ctx.blinded_bars) == 30
    assert drill_ctx.true_bias == "BULLISH"
    assert drill_ctx.true_setup == "ALN_LPEU"
    
    # Perfect Declaration
    declaration = DrillDeclaration(
        drill_id=drill_ctx.drill_id,
        declared_bias="BULLISH",
        declared_setup="ALN_LPEU",
        declared_entry_price=10060.0,
        declared_stop_bps=12.0,
        declared_target_bps=10.0,
        latency_ms=1200
    )
    
    feedback = BlindedDrillEngine.submit_and_evaluate(drill_ctx, declaration, db_path=temp_db)
    assert feedback.process_adherence_score == 100.0
    assert feedback.rule_match_flag is True
    
    # Verify recorded in drill_attempts
    with sqlite3.connect(str(temp_db)) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT * FROM drill_attempts WHERE drill_id = ?;", (drill_ctx.drill_id,))
        row = cur.fetchone()
        assert row is not None
        assert row["process_adherence_score"] == 100.0
        assert row["declared_bias"] == "BULLISH"
