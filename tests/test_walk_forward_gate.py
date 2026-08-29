"""Pytest suite for WalkForwardGate (Milestone 3.2)."""

import pytest
from scripts.trading_brain.research.walk_forward_gate import (
    FoldResult,
    WalkForwardEvaluation,
    WalkForwardGate,
)


class _DummyClassifier:
    """A minimal model that always predicts the majority class seen during fit."""

    def __init__(self):
        self._majority = 0

    def fit(self, X_train, y_train):
        if not y_train:
            self._majority = 0
            return
        self._majority = max(set(y_train), key=y_train.count)

    def predict(self, X_test):
        return [self._majority] * len(X_test)


def test_multiple_testing_adjustments_fdr_and_fwer():
    """Tests BH FDR, BY FDR, and Holm-Bonferroni p-value corrections."""
    raw_p = [0.001, 0.01, 0.04, 0.10, 0.50]

    results = WalkForwardGate.adjust_p_values(raw_p, alpha=0.05)
    assert len(results) == 5

    # Lowest p-value must be significant under both FDR and FWER
    assert results[0].significant_fdr_05 is True
    assert results[0].bh_q_value <= 0.01
    assert results[0].holm_p_value <= 0.01


def test_evaluate_walk_forward_folds_aggregates_precomputed_scores():
    """Tests purged walk-forward fold evaluation from precomputed scores."""
    scores = [12.5, 14.0, 11.0, 15.2, 13.8]
    p_values = [0.001, 0.002, 0.004, 0.001, 0.002]

    eval_res = WalkForwardGate.evaluate_walk_forward_folds(scores, p_values, min_score_threshold=5.0)
    assert eval_res.n_folds == 5
    assert eval_res.mean_out_of_sample_score > 10.0
    assert eval_res.passed_gate is True


def test_evaluate_walk_forward_fits_model_per_fold():
    """Tests that the gate actually constructs folds, fits models, and scores on embargoed tests."""
    # 50 samples, alternating labels 0/1. Majority label is 1 for even indices if we start at 0,
    # but the dummy majority classifier will simply predict the majority from the training fold.
    features = [[i] for i in range(50)]
    labels = [i % 2 for i in range(50)]

    def make_model():
        return _DummyClassifier()

    res = WalkForwardGate.evaluate_walk_forward(
        features,
        labels,
        model_factory=make_model,
        scorer=WalkForwardGate.accuracy_scorer,
        n_folds=3,
        min_train_size=15,
        embargo_size=2,
        min_score_threshold=0.45,
    )

    assert isinstance(res, WalkForwardEvaluation)
    assert res.n_folds == 3
    assert len(res.fold_results) == 3
    for fold in res.fold_results:
        assert isinstance(fold, FoldResult)
        assert fold.train_size >= 15
        assert fold.test_size >= 1
    assert 0.0 <= res.mean_out_of_sample_score <= 1.0
    assert res.passed_gate is True
    assert res.multiple_testing_summary is not None
    assert len(res.multiple_testing_summary) == res.n_folds


def test_construct_purged_folds_respects_embargo():
    """Every fold must have test_start >= train_end + embargo_size."""
    n_samples = 80
    folds = WalkForwardGate.construct_purged_folds(n_samples, n_folds=4, min_train_size=20, embargo_size=3)
    for f in folds:
        assert f.train_end + f.purge_buffer_size <= f.test_start
        assert f.test_start < f.test_end <= n_samples


def test_empty_input_returns_failed_evaluation():
    """An empty series must fail gracefully with a recorded reason."""
    res = WalkForwardGate.evaluate_walk_forward([], [], model_factory=lambda: _DummyClassifier())
    assert res.passed_gate is False
    assert res.failure_reasons
    assert "empty" in " ".join(res.failure_reasons).lower()