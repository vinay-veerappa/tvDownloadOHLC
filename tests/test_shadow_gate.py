"""Pytest suite for ShadowGate (Milestone 3.3)."""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from scripts.trading_brain.db.init_db import init_trading_brain_db
from scripts.trading_brain.research.shadow_gate import (
    PreregistrationRequiredError,
    ShadowEvaluationResult,
    ShadowGate,
    ShadowGateLockedError,
)


@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = Path(tmpdir) / "test_trading_brain.sqlite"
        init_trading_brain_db(db_path=db_path, verbose=False)
        yield db_path


def test_shadow_evaluation_preregistration_and_terminal_locking(temp_db):
    """Tests preregistration, statistical power, promotion, and terminal locking."""
    finding_id = "f-prereg-1"
    model_id = "MOD_V2"
    
    # 1. Preregister finding at discovery time
    ShadowGate.preregister_candidate_finding(
        finding_id=finding_id,
        model_version_id=model_id,
        benchmark_metric=0.10,
        expected_effect_size_d=0.5,
        feature_manifest={"feature_set": "ALN_VOL_V1"},
        db_path=temp_db
    )
    
    # 2. Evaluate on sealed shadow data (N=100) -> PROMOTED
    res_promo = ShadowGate.evaluate_candidate_finding(
        finding_id=finding_id,
        model_version_id=model_id,
        sample_size=100,
        realized_metric=0.25,
        fdr_q_value=0.01,
        db_path=temp_db
    )
    assert res_promo.pipeline_stage == "PROMOTED"
    assert res_promo.statistical_power >= 0.80
    assert res_promo.benchmark_metric == 0.10
    
    # 3. Attempting to re-evaluate terminal finding must raise ShadowGateLockedError
    with pytest.raises(ShadowGateLockedError):
        ShadowGate.evaluate_candidate_finding(
            finding_id=finding_id,
            model_version_id=model_id,
            sample_size=100,
            realized_metric=0.30,
            fdr_q_value=0.01,
            db_path=temp_db
        )


def test_shadow_evaluation_underpowered_inconclusive_state(temp_db):
    """Tests underpowered test (N=10) transitioning to INCONCLUSIVE_WAITING."""
    finding_id = "f-under-1"
    
    ShadowGate.preregister_candidate_finding(
        finding_id=finding_id,
        model_version_id="MOD_V1",
        benchmark_metric=0.10,
        expected_effect_size_d=0.3,
        feature_manifest={},
        db_path=temp_db
    )
    
    res_under = ShadowGate.evaluate_candidate_finding(
        finding_id=finding_id,
        model_version_id="MOD_V1",
        sample_size=10,
        realized_metric=0.15,
        fdr_q_value=0.04,
        db_path=temp_db
    )
    assert res_under.pipeline_stage == "INCONCLUSIVE_WAITING"
    assert res_under.statistical_power < 0.80


def test_shadow_evaluation_without_preregistration_fails_closed(temp_db):
    """Tests that evaluating on shadow data without prior preregistration strictly raises PreregistrationRequiredError."""
    with pytest.raises(PreregistrationRequiredError):
        ShadowGate.evaluate_candidate_finding(
            finding_id="unregistered_finding_999",
            model_version_id="MOD_V3",
            sample_size=100,
            realized_metric=0.30,
            fdr_q_value=0.01,
            db_path=temp_db
        )
