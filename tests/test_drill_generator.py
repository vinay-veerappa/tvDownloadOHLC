"""Pytest suite for TargetedDrillGenerator (Milestone 2.4)."""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from scripts.trading_brain.db.init_db import init_trading_brain_db
from scripts.trading_brain.practice.drill_generator import TargetedDrillGenerator


@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = Path(tmpdir) / "test_trading_brain.sqlite"
        init_trading_brain_db(db_path=db_path, verbose=False)
        yield db_path


def test_targeted_drill_generator_recurrence_mining(temp_db):
    """Tests mining recurring intervention rules and generating targeted curricula."""
    with sqlite3.connect(str(temp_db)) as conn:
        for i in range(4):
            conn.execute(
                """
                INSERT INTO intervention_events (
                    intervention_id, session_date, ticker, account_id,
                    producer, producer_version, authority_class, action_mode,
                    rule_id, rule_version, enforced, idempotency_key, event_timestamp_utc
                ) VALUES (?, '2026-08-28', 'NQ1', 'ACC1', 'NT8', '1.0', 'HARD_LOCKOUT_ENFORCED', 'ACTING', 'DAILY_MAX_LOSS_LIMIT', '1.0', 1, ?, '2026-08-28T10:00:00Z');
                """,
                (f"inv-rec-{i}", f"idemp-rec-{i}")
            )
            
    curricula = TargetedDrillGenerator.analyze_weaknesses_and_generate(min_recurrence=3, db_path=temp_db)
    assert len(curricula) == 1
    assert curricula[0].weakness_rule_id == "DAILY_MAX_LOSS_LIMIT"
    assert curricula[0].recurrence_count == 4
    assert len(curricula[0].recommended_drills) == 3
