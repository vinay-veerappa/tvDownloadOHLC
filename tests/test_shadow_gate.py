"""Pytest suite for ShadowGate (Milestone 3.3).

The gate enforces sealed-holdout custody: the model predictions are generated from the
registered holdout features, and the realized metric is computed by the gate against the
registered labels.  Callers cannot submit favorable numbers directly.

Anti-oracle custody: the executed predictor must be the one BOUND at preregistration
(module + qualname + source hash). A swapped-in callback that returns the sealed labels
is refused with ModelBindingMismatchError.

Design power is frozen from the PREREGISTERED effect (Cohen's h at the sealed
benchmark); the observed effect is reported but never retroactively powers the design.
"""

import tempfile
from pathlib import Path

import pytest

from scripts.trading_brain.db.init_db import init_trading_brain_db
from scripts.trading_brain.research.sealed_holdout import (
    HoldoutHashMismatchError,
    HoldoutRegistry,
)
from scripts.trading_brain.research.shadow_gate import (
    ModelBindingMismatchError,
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


# Module-level bound predictors: preregistration binds (module, qualname, source hash),
# so the SAME function object identity must be passed at evaluation. Defining the
# predictor here (not as a nested closure) keeps the binding stable and realistic.
LABELS_PROMO = ["LONG"] * 80 + ["SHORT"] * 20


def bound_perfect_predictor(features):
    """Bound predictor for HOLDOUT_PROMO: reproducible rule over the feature index."""
    return [LABELS_PROMO[i] if i < len(LABELS_PROMO) else "LONG" for i in features]


LABELS_UNDER = ["LONG"] * 6 + ["SHORT"] * 4


def bound_mediocre_predictor(features):
    # 3 of 5 correct on any prefix: mirrors 0.60 realized accuracy
    out = []
    for i, _ in enumerate(features):
        lbl = LABELS_UNDER[i] if i < len(LABELS_UNDER) else "LONG"
        out.append(lbl if i % 5 != 4 else ("SHORT" if lbl == "LONG" else "LONG"))
    return out


def test_preregistration_requires_predictor_binding(temp_db):
    """Preregistration without model_predict_fn is refused (anti-oracle custody)."""
    labels = ["LONG"] * 80 + ["SHORT"] * 20
    hash_ = HoldoutRegistry.register_holdout(
        holdout_dataset_id="HOLDOUT_NOFN",
        features=list(range(len(labels))),
        labels=labels,
        benchmark_metric=0.55,
        expected_effect_size_d=0.5,
        db_path=temp_db,
    )
    with pytest.raises(ValueError, match="model_predict_fn"):
        ShadowGate.preregister_candidate_finding(
            finding_id="f-nofn",
            model_version_id="MOD_V0",
            benchmark_metric=0.55,
            expected_effect_size_d=0.5,
            feature_manifest={},
            holdout_dataset_id="HOLDOUT_NOFN",
            holdout_dataset_hash=hash_,
            db_path=temp_db,
        )


def test_preregistration_benchmark_must_match_sealed_registry(temp_db):
    """A weak caller benchmark cannot replace a stricter sealed one (F14)."""
    labels = ["LONG"] * 20
    hash_ = HoldoutRegistry.register_holdout(
        holdout_dataset_id="HOLDOUT_STRICT",
        features=list(range(len(labels))),
        labels=labels,
        benchmark_metric=0.80,
        expected_effect_size_d=0.5,
        db_path=temp_db,
    )
    with pytest.raises(ValueError, match="sealed holdout"):
        ShadowGate.preregister_candidate_finding(
            finding_id="f-strict",
            model_version_id="MOD_VX",
            benchmark_metric=0.55,  # weaker than sealed 0.80
            expected_effect_size_d=0.5,
            feature_manifest={},
            holdout_dataset_id="HOLDOUT_STRICT",
            holdout_dataset_hash=hash_,
            model_predict_fn=bound_perfect_predictor,
            db_path=temp_db,
        )


def test_oracle_style_swap_is_refused(temp_db):
    """A DIFFERENT callable than the bound predictor is refused outright (anti-oracle)."""
    labels = LABELS_PROMO
    hash_ = HoldoutRegistry.register_holdout(
        holdout_dataset_id="HOLDOUT_SWAP",
        features=list(range(len(labels))),
        labels=labels,
        benchmark_metric=0.55,
        expected_effect_size_d=0.5,
        db_path=temp_db,
    )
    ShadowGate.preregister_candidate_finding(
        finding_id="f-bind",
        model_version_id="MOD_BIND",
        benchmark_metric=0.55,
        expected_effect_size_d=0.5,
        feature_manifest={},
        holdout_dataset_id="HOLDOUT_SWAP",
        holdout_dataset_hash=hash_,
        model_predict_fn=bound_perfect_predictor,
        db_path=temp_db,
    )

    def oracle_callback(features):
        return labels[: len(features)]

    with pytest.raises(ModelBindingMismatchError):
        ShadowGate.evaluate_candidate_finding(
            finding_id="f-bind",
            model_version_id="MOD_BIND",
            model_predict_fn=oracle_callback,
            sample_size=100,
            db_path=temp_db,
        )


def test_shadow_evaluation_preregistration_and_terminal_locking(temp_db):
    """Tests preregistration, sealed holdout evaluation, promotion, and terminal locking."""
    finding_id = "f-prereg-1"
    model_id = "MOD_V2"
    labels = LABELS_PROMO
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
        model_predict_fn=bound_perfect_predictor,
        db_path=temp_db
    )

    res_promo = ShadowGate.evaluate_candidate_finding(
        finding_id=finding_id,
        model_version_id=model_id,
        model_predict_fn=bound_perfect_predictor,
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
            model_predict_fn=bound_perfect_predictor,
            sample_size=100,
            db_path=temp_db
        )


def test_shadow_evaluation_underpowered_inconclusive_state(temp_db):
    """Tests underpowered design transitioning to INCONCLUSIVE_WAITING.

    Design power is frozen from the PREREGISTERED effect (h=0.3 at N=10 -> power ~0.2,
    below 0.80) regardless of the realized result - an extreme observation can no
    longer retroactively power the design (F12).
    """
    finding_id = "f-under-1"
    labels = LABELS_UNDER
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
        model_predict_fn=bound_mediocre_predictor,
        db_path=temp_db
    )

    res_under = ShadowGate.evaluate_candidate_finding(
        finding_id=finding_id,
        model_version_id="MOD_V1",
        model_predict_fn=bound_mediocre_predictor,
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

    def bound_short_predictor(features_arg):
        return ["SHORT"] * len(features_arg)

    ShadowGate.preregister_candidate_finding(
        finding_id=finding_id,
        model_version_id=model_id,
        benchmark_metric=0.90,
        expected_effect_size_d=1.0,
        feature_manifest={},
        holdout_dataset_id="HOLDOUT_CHEAT",
        holdout_dataset_hash=hash_,
        model_predict_fn=bound_short_predictor,
        db_path=temp_db
    )

    res = ShadowGate.evaluate_candidate_finding(
        finding_id=finding_id,
        model_version_id=model_id,
        model_predict_fn=bound_short_predictor,
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

    def bound_hash_predictor(features_arg):
        return ["LONG"] * len(features_arg)

    # Preregistration itself verifies the sealed hash and refuses a tampered one -
    # fail-closed EARLIER than before (at bind time, not evaluation time).
    with pytest.raises(HoldoutHashMismatchError):
        ShadowGate.preregister_candidate_finding(
            finding_id=finding_id,
            model_version_id=model_id,
            benchmark_metric=0.50,
            expected_effect_size_d=0.5,
            feature_manifest={},
            holdout_dataset_id="HOLDOUT_HASH",
            holdout_dataset_hash="sha256: tampered",
            model_predict_fn=bound_hash_predictor,
            db_path=temp_db
        )


def test_inconclusive_resume_re_evaluates_without_missing_key(temp_db):
    """F15: resume after INCONCLUSIVE_WAITING reads sealed registry values, not the stale
    event payload, so a second evaluation does not raise a missing-effect-size KeyError.
    Sample-extension custody (F17): the resume must supply a STRICTLY LARGER sample_size;
    re-rolling the same prefix is refused."""
    finding_id = "f-resume"
    labels = LABELS_UNDER
    hash_ = HoldoutRegistry.register_holdout(
        holdout_dataset_id="HOLDOUT_RESUME",
        features=list(range(len(labels))),
        labels=labels,
        benchmark_metric=0.55,
        expected_effect_size_d=0.3,
        db_path=temp_db,
    )
    ShadowGate.preregister_candidate_finding(
        finding_id=finding_id,
        model_version_id="MOD_RESUME",
        benchmark_metric=0.55,
        expected_effect_size_d=0.3,
        feature_manifest={},
        holdout_dataset_id="HOLDOUT_RESUME",
        holdout_dataset_hash=hash_,
        model_predict_fn=bound_mediocre_predictor,
        db_path=temp_db,
    )
    first = ShadowGate.evaluate_candidate_finding(
        finding_id=finding_id,
        model_version_id="MOD_RESUME",
        model_predict_fn=bound_mediocre_predictor,
        sample_size=5,
        db_path=temp_db,
    )
    assert first.pipeline_stage == "INCONCLUSIVE_WAITING"

    # Same-size re-roll refused (no new evidence).
    with pytest.raises(ShadowGateLockedError, match="STRICTLY LARGER"):
        ShadowGate.evaluate_candidate_finding(
            finding_id=finding_id,
            model_version_id="MOD_RESUME",
            model_predict_fn=bound_mediocre_predictor,
            sample_size=5,
            db_path=temp_db,
        )
    # Larger prefix re-evaluates from sealed registry values - no resume KeyError.
    second = ShadowGate.evaluate_candidate_finding(
        finding_id=finding_id,
        model_version_id="MOD_RESUME",
        model_predict_fn=bound_mediocre_predictor,
        sample_size=10,
        db_path=temp_db,
    )
    assert second.pipeline_stage in ("INCONCLUSIVE_WAITING", "PROMOTED", "REJECTED")

def test_binding_detects_closure_mutation(temp_db):
    """F2 hardening: mutating a captured closure variable between preregistration and
    evaluation changes the binding and is refused."""
    labels = LABELS_PROMO[:40]

    def make_predictor(pred_source_labels):
        def predictor(features):
            return pred_source_labels[: len(features)]
        return predictor

    hash_ = HoldoutRegistry.register_holdout(
        holdout_dataset_id="HOLDOUT_CLOSURE",
        features=list(range(len(labels))),
        labels=labels,
        benchmark_metric=0.55,
        expected_effect_size_d=0.5,
        db_path=temp_db,
    )
    predictor = make_predictor(labels)
    ShadowGate.preregister_candidate_finding(
        finding_id="f-closure",
        model_version_id="MOD_CLOSURE",
        benchmark_metric=0.55,
        expected_effect_size_d=0.5,
        feature_manifest={},
        holdout_dataset_id="HOLDOUT_CLOSURE",
        holdout_dataset_hash=hash_,
        model_predict_fn=predictor,
        db_path=temp_db,
    )
    result = ShadowGate.evaluate_candidate_finding(
        finding_id="f-closure",
        model_version_id="MOD_CLOSURE",
        model_predict_fn=predictor,
        sample_size=40,
        db_path=temp_db,
    )
    # Terminal on first evaluation; the binding test resumes by a strictly larger N.
    assert result.pipeline_stage == "PROMOTED"

    # Mutate the captured list in place - same function object, different behavior.
    # The resume is refused on the BINDING change before any sample-extension check.
    labels[0] = "SHORT" if labels[0] == "LONG" else "LONG"
    with pytest.raises(ModelBindingMismatchError):
        ShadowGate.evaluate_candidate_finding(
            finding_id="f-closure",
            model_version_id="MOD_CLOSURE",
            model_predict_fn=predictor,
            sample_size=41,
            db_path=temp_db,
        )
