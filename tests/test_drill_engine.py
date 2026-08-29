"""Pytest suite for BlindedDrillEngine (Milestone 2.3)."""

import tempfile
from pathlib import Path
import pytest

from scripts.trading_brain.db.init_db import init_trading_brain_db
from scripts.trading_brain.practice.drill_engine import (
    BlindedDrillEngine,
    DrillDeclaration,
    DrillAlreadyLockedError,
    HistoricalDataUnavailableError,
)

@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = Path(tmpdir) / "test_trading_brain.sqlite"
        init_trading_brain_db(db_path=db_path, verbose=False)
        yield db_path

def test_blinded_drill_split_custody_and_evaluation(temp_db):
    # 1. Generate blinded drill
    drill = BlindedDrillEngine.generate_blinded_drill(
        drill_type="RECOGNITION",
        dataset_split="TRAINING",
        session_date="2026-08-28",
        ticker="NQ1",
        synthetic_mode=True,
        db_path=temp_db
    )

    # Assert anti-memorization & split custody: caller CANNOT see true answers
    assert hasattr(drill, "drill_id")
    assert not hasattr(drill, "true_bias")
    assert not hasattr(drill, "true_setup")
    assert not hasattr(drill, "true_session_date")
    assert len(drill.blinded_bars) > 0

    # 2. Submit user declaration
    declaration = DrillDeclaration(
        drill_id=drill.drill_id,
        declared_bias="BULLISH",
        declared_setup="ALN_LPEU",
        declared_entry_price=20000.0,
        declared_stop_bps=12.0,
        declared_target_bps=10.0,
        latency_ms=1200
    )

    feedback = BlindedDrillEngine.submit_and_evaluate(declaration, db_path=temp_db)
    assert feedback.drill_id == drill.drill_id
    assert 0.0 <= feedback.process_adherence_score <= 100.0
    assert feedback.true_bias in ("BULLISH", "BEARISH", "NEUTRAL")

    # 3. Attempting to re-submit must fail closed
    with pytest.raises(DrillAlreadyLockedError):
        BlindedDrillEngine.submit_and_evaluate(declaration, db_path=temp_db)


def test_split_custody_survives_process_restart(temp_db):
    """A session used for ASSESSMENT cannot later be reused for TRAINING, even in a fresh engine instance."""
    # Use a fresh engine instance by reinstantiating nothing; class methods share the DB.
    BlindedDrillEngine.generate_blinded_drill(
        drill_type="RECOGNITION",
        dataset_split="ASSESSMENT",
        session_date="2026-08-29",
        ticker="NQ1",
        synthetic_mode=True,
        db_path=temp_db
    )
    from scripts.trading_brain.practice.drill_engine import SplitCustodyViolationError
    with pytest.raises(SplitCustodyViolationError):
        BlindedDrillEngine.generate_blinded_drill(
            drill_type="RECOGNITION",
            dataset_split="TRAINING",
            session_date="2026-08-29",
            ticker="NQ1",
            synthetic_mode=True,
            db_path=temp_db
        )


def test_module_scope_no_answers(temp_db):
    """The engine module does not expose a vault dictionary with answers."""
    from scripts.trading_brain import practice
    assert not hasattr(practice, "_SEALED_DRILL_VAULT")
    from scripts.trading_brain.practice import drill_engine
    assert not hasattr(drill_engine, "_SEALED_DRILL_VAULT")
