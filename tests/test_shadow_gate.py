"""Pytest suite for ShadowGate (Milestone 3.3).n
The gate now enforces sealed-holdout custody: the model predictions are generated from the
registered holdout features, and the realized metric is computed by the gate against the
registered labels.  Callers cannot submit favorable numbers directly.
"""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from scripts.trading_brain.db.init_db import init_trading_brain_db
from scripts.trading_brain.research.sealed_holdout import HoldoutRegistry
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


def _directional_model_factory(labels):
    """Returns a predict_fn that returns the sealed labels (perfect oracle)."""
    def predict_fn(features):
        return labels[:len(features)]
    return predict_fn


def test_shadow_evaluation_preregistration_and_terminal_locking(temp_db):
    """Tests preregistration, sealed holdout evaluation, promotion, and terminal locking."""
    finding_id = "f-prereg-1"
    model_id = "MOD_V2"
    labels = ["LONG"] * 80 + ["SHORT"] * 20
    features = list(range(len(labels)))
    hash_ = HoldoutRegistry.register_holdout(
        holdout_dataset_id="HOLDOUT_PROMO",
        features=features,
        labels=labels,
        benchmark_metric=0.55,
        expected_effect_size_d=0.5,
        db_path=temp_db,
    )

    ShadowGate.preregister_candidate_finding(
        finding_id=finding_id,
        model_version_id=model_id,
        benchmark_metric=0.55,
        expected_effect_size_d=0.5,
        feature_manifest={"feature_set": "ALN_VOL_V1"},
        holdout_dataset_id="HOLDOUT_PROMO",
        holdout_dataset_hash=hash_,
        db_path=temp_db
    )

    res_promo = ShadowGate.evaluate_candidate_finding(
        finding_id=finding_id,
        model_version_id=model_id,
        model_predict_fn=_directional_model_factory(labels),
        sample_size=100,
        db_path=temp_db
    )
    assert res_promo.pipeline_stage == "PROMOTED"
    assert res_promo.statistical_power >= 0.80
    assert res_promo.realized_metric == 1.0
    assert res_promo.benchmark_metric == 0.55
    assert res_promo.holdout_hash == hash_

    with pytest.raises(ShadowGateLockedError):
        ShadowGate.evaluate_candidate_finding(
            finding_id=finding_id,
            model_version_id=model_id,
            model_predict_fn=_directional_model_factory(labels),
            sample_size=100,
            db_path=temp_db
        )


def test_shadow_evaluation_underpowered_inconclusive_state(temp_db):
    """Tests underpowered test (N=10) transitioning to INCONCLUSIVE_WAITING."""
    finding_id = "f-under-1"
    labels = ["LONG"] * 8 + ["SHORT"] * 2
    features = list(range(len(labels)))
    hash_ = HoldoutRegistry.register_holdout(
        holdout_dataset_id="HOLDOUT_UNDER",
        features=features,
        labels=labels,
        benchmark_metric=0.55,
        expected_effect_size_d=0.3,
        db_path=temp_db,
    )

    ShadowGate.preregister_candidate_finding(
        finding_id=finding_id,
        model_version_id="MOD_V1",
        benchmark_metric=0.55,
        expected_effect_size_d=0.3,
        feature_manifest={},
        holdout_dataset_id="HOLDOUT_UNDER",
        holdout_dataset_hash=hash_,
        db_path=temp_db
    )

    res_under = ShadowGate.evaluate_candidate_finding(
        finding_id=finding_id,
        model_version_id="MOD_V1",
        model_predict_fn=_directional_model_factory(labels),
        sample_size=10,
        db_path=temp_db
    )
    assert res_under.pipeline_stage == "INCONCLUSIVE_WAITING"
    assert res_under.statistical_power < 0.80


def test_shadow_evaluation_without_preregistration_fails_closed(temp_db):
    """Evaluating without preregistration strictly raises PreregistrationRequiredError."""
    with pytest.raises(PreregistrationRequiredError):
        ShadowGate.evaluate_candidate_finding(
            finding_id="unregistered_finding_999",
            model_version_id="MOD_V3",
            model_predict_fn=lambda x: ["LONG"] * len(x),
            sample_size=100,
            db_path=temp_db
        )


def test_shadow_evaluation_rejects_caller_supplied_numbers(temp_db):
    """The gate computes the metric internally; a caller cannot inject a favorable realized_metric."""
    finding_id = "f-no-cheating"
    model_id = "MOD_CHEAT"
    labels = ["LONG", "SHORT"] * 50
    features = list(range(len(labels)))
    hash_ = HoldoutRegistry.register_holdout(
        holdout_dataset_id="HOLDOUT_CHEAT",
        features=features,
        labels=labels,
        benchmark_metric=0.90,
        expected_effect_size_d=1.0,
        db_path=temp_db,
    )

    ShadowGate.preregister_candidate_finding(
        finding_id=finding_id,
        model_version_id=model_id,
        benchmark_metric=0.90,
        expected_effect_size_d=1.0,
        feature_manifest={},
        holdout_dataset_id="HOLDOUT_CHEAT",
        holdout_dataset_hash=hash_,
        db_path=temp_db
    )

    # A predict function that always returns SHORT will score 0.5 accuracy against alternating labels.
    res = ShadowGate.evaluate_candidate_finding(
        finding_id=finding_id,
        model_version_id=model_id,
        model_predict_fn=lambda x: ["SHORT"] * len(x),
        sample_size=100,
        db_path=temp_db
    )
    assert res.realized_metric == 0.5
    assert res.pipeline_stage == "REJECTED"


def test_shadow_evaluation_hash_mismatch_fails_closed(temp_db):
    """A tampered holdout hash prevents evaluation."""
    finding_id = "f-hash"
    model_id = "MOD_HASH"
    labels = ["LONG"] * 10
    features = list(range(len(labels)))
    HoldoutRegistry.register_holdout(
        holdout_dataset_id="HOLDOUT_HASH",
        features=features,
        labels=labels,
        benchmark_metric=0.50,
        expected_effect_size_d=0.5,
        db_path=temp_db,
    )

    ShadowGate.preregister_candidate_finding(
        finding_id=finding_id,
        model_version_id=model_id,
        benchmark_metric=0.50,
        expected_effect_size_d=0.5,
        feature_manifest={},
        holdout_dataset_id="HOLDOUT_HASH",
        holdout_dataset_hash="sha256: tampered",
        db_path=temp_db
    )

    from scripts.trading_brain.research.sealed_holdout import HoldoutHashMismatchError
    with pytest.raises(HoldoutHashMismatchError):
        ShadowGate.evaluate_candidate_finding(
            finding_id=finding_id,
            model_version_id=model_id,
            model_predict_fn=lambda x: ["LONG"] * len(x),
            sample_size=10,
            db_path=temp_db
        )