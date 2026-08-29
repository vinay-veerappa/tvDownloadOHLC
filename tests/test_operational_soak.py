"""Pytest suite for Operational Soak Gate (Milestone 0.8)."""

import tempfile
from pathlib import Path
import pytest

from scripts.trading_brain.db.init_db import init_trading_brain_db
from scripts.trading_brain.testing.operational_soak_gate import OperationalSoakGate


@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = Path(tmpdir) / "test_trading_brain.sqlite"
        init_trading_brain_db(db_path=db_path, verbose=False)
        yield db_path


def test_operational_soak_all_scenarios(temp_db):
    """Executes the 5 measured integration scenarios and certifies OPERATIONALLY_ACCEPTED_CAPTURE_V1."""
    res = OperationalSoakGate.run_all_scenarios(db_path=temp_db, verbose=False)
    assert res.status == "OPERATIONALLY_ACCEPTED_CAPTURE_V1"
    assert res.scenarios_passed == 5
    assert res.data_loss_count == 0
    assert res.duplicate_event_count == 0
    assert res.idempotency_violations == 0
    assert res.replay_drift_count == 0
