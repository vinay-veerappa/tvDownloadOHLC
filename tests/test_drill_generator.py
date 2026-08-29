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
        # 4 independent incident sessions for the same rule
        for i, sdate in enumerate(["2026-08-24", "2026-08-25", "2026-08-26", "2026-08-27"]):
            conn.execute(
                """
                INSERT INTO intervention_events (
                    intervention_id, session_date, ticker, account_id,
                    producer, producer_version, authority_class, action_mode,
                    rule_id, rule_version, enforced, idempotency_key, event_timestamp_utc
                ) VALUES (?, ?, 'NQ1', 'ACC1', 'NT8', '1.0', 'HARD_LOCKOUT_ENFORCED', 'ACTING', 'DAILY_MAX_LOSS_LIMIT', '1.0', 1, ?, '2026-08-28T10:00:00Z');
                """,
                (f"inv-rec-{i}", sdate, f"idemp-rec-{i}")
            )
        # 3 events from the SAME session on another rule: counts as ONE independent incident
        for i in range(3):
            conn.execute(
                """
                INSERT INTO intervention_events (
                    intervention_id, session_date, ticker, account_id,
                    producer, producer_version, authority_class, action_mode,
                    rule_id, rule_version, enforced, idempotency_key, event_timestamp_utc
                ) VALUES (?, '2026-08-28', 'NQ1', 'ACC1', 'NT8', '1.0', 'SOFT_FRICTION_PROMPTED', 'ACTING', 'SINGLE_INCIDENT_RULE', '1.0', 1, ?, '2026-08-28T11:00:00Z');
                """,
                (f"inv-single-{i}", f"idemp-single-{i}")
            )

    curricula = TargetedDrillGenerator.analyze_weaknesses_and_generate(min_recurrence=3, db_path=temp_db)
    by_rule = {c.weakness_rule_id: c for c in curricula}
    # 4 distinct sessions
    assert by_rule["DAILY_MAX_LOSS_LIMIT"].recurrence_count == 4
    assert len(by_rule["DAILY_MAX_LOSS_LIMIT"].recommended_drills) == 3
    # 3 raw events collapsing to 1 independent incident session -> below threshold, no curriculum
    assert "SINGLE_INCIDENT_RULE" not in by_rule


def test_drill_split_custody_violation_rejected(temp_db):
    """Verifies a session used in ASSESSMENT can never be regenerated for TRAINING custody."""
    from scripts.trading_brain.practice.drill_engine import (
        BlindedDrillEngine,
        SplitCustodyViolationError,
    )

    BlindedDrillEngine.generate_blinded_drill(
        dataset_split="ASSESSMENT", session_date="2026-07-15", ticker="NQ1", synthetic_mode=True
    )
    with pytest.raises(SplitCustodyViolationError):
        BlindedDrillEngine.generate_blinded_drill(
            dataset_split="TRAINING", session_date="2026-07-15", ticker="NQ1", synthetic_mode=True
        )


def test_calibration_rolling_baseline_and_validation(temp_db):
    """Verifies the rolling-50 recency baseline and fail-closed probability validation."""
    from scripts.trading_brain.research.calibration_engine import CalibrationEngine

    outcomes = ["R1"] * 10 + ["DWP"] * 10 + ["R2"] * 5
    baseline = CalibrationEngine.compute_rolling_frequency_baseline(outcomes, window=50, min_history=5)
    assert len(baseline) == len(outcomes)
    # First sessions fall back to unconditional prior
    assert baseline[0]["R1"] == pytest.approx(10 / 25)
    # Session 15 has 10 R1 + 5 DWP trailing history
    assert baseline[15]["R1"] == pytest.approx(10 / 15)
    assert baseline[15]["DWP"] == pytest.approx(5 / 15)

    with pytest.raises(ValueError):
        # Probabilities do not sum to 1 -> fail closed
        CalibrationEngine.validate_forecast_probs({dt: 0.2 for dt in ["R1", "R2", "DNP", "DWP"]})
        CalibrationEngine.validate_forecast_probs({dt: 0.2 for dt in ["R1", "R2", "DNP", "DWP", "ROTATIONAL_CHOP"]} | {"R1": 0.5})
