"""Multi-Fold Purged Walk-Forward Validator & Multiple Testing Gate (Milestone 3.2).

Enforces:
1. Real Purged Cross-Validation: Constructs K expanding time-series folds with an embargo buffer
   to eliminate lookahead leakage and auto-correlation overlap.
2. Model Fitting Per Fold: caller supplies a `model_factory` that produces a fit/predict object;
   the gate trains on the in-fold training set and scores on the embargo-purged test set.
3. Multiple Hypothesis Testing Corrections across candidate models/hypotheses:
   - Benjamini-Hochberg (BH) False Discovery Rate (FDR q-values)
   - Benjamini-Yekutieli (BY) Arbitrary Dependence Control
   - Holm-Bonferroni Family-Wise Error Rate (FWER)
4. Pass Criteria: mean out-of-sample score exceeds threshold, standard error is bounded,
   and at least one fold-level result survives the FDR correction (when p-values are supplied).
"""

import math
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Protocol, Sequence, Tuple, Union


@dataclass
class MultipleTestingResult:
    test_id: str
    raw_p_value: float
    bh_q_value: float
    by_q_value: float
    holm_p_value: float
    significant_fdr_05: bool
    significant_fwer_05: bool


@dataclass
class FoldSplit:
    fold_idx: int
    train_start: int
    train_end: int
    test_start: int
    test_end: int
    purge_buffer_size: int


@dataclass
class FoldResult:
    fold_idx: int
    train_size: int
    test_size: int
    score: float
    p_value: Optional[float] = None


@dataclass
class WalkForwardEvaluation:
    n_folds: int
    mean_out_of_sample_score: float
    score_standard_error: float
    fold_scores: List[float]
    passed_gate: bool
    fold_results: List[FoldResult]
    multiple_testing_summary: Optional[List[MultipleTestingResult]] = None
    failure_reasons: List[str] = None


class Scorer(Protocol):
    """A scorer receives true labels and predictions and returns a float score."""
    def __call__(self, y_true: Sequence[Any], y_pred: Sequence[Any]) -> float: ...


class Model(Protocol):
    """A model supports fit(train_features, train_labels) and predict(test_features)."""
    def fit(self, X_train: Sequence[Any], y_train: Sequence[Any]) -> None: ...
    def predict(self, X_test: Sequence[Any]) -> Sequence[Any]: ...


ModelFactory = Callable[[], Model]


class WalkForwardGate:
    """Validator that executes purged cross-validation and multiple comparison corrections."""

    @staticmethod
    def accuracy_scorer(y_true: Sequence[Any], y_pred: Sequence[Any]) -> float:
        if not y_true:
            return 0.0
        correct = sum(1 for a, b in zip(y_true, y_pred) if a == b)
        return correct / len(y_true)

    @staticmethod
    def construct_purged_folds(
        n_samples: int,
        n_folds: int = 5,
        min_train_size: int = 20,
        embargo_size: int = 2
    ) -> List[FoldSplit]:
        """Constructs expanding training folds with embargo buffer before out-of-sample test splits."""
        if n_samples < (min_train_size + embargo_size + n_folds):
            raise ValueError(f"Insufficient samples (N={n_samples}) for {n_folds} folds with min_train={min_train_size}")

        usable_test = n_samples - min_train_size - embargo_size
        if usable_test <= 0:
            raise ValueError(f"No usable test samples after reserving train+embargo: N={n_samples}")
        test_size = max(1, usable_test // n_folds)
        splits = []

        for k in range(n_folds):
            train_end = min_train_size + (k * test_size)
            test_start = train_end + embargo_size
            test_end = min(test_start + test_size, n_samples)

            if test_start < n_samples:
                splits.append(FoldSplit(
                    fold_idx=k + 1,
                    train_start=0,
                    train_end=train_end,
                    test_start=test_start,
                    test_end=test_end,
                    purge_buffer_size=embargo_size
                ))
        return splits

    @staticmethod
    def adjust_p_values(p_values: List[float], alpha: float = 0.05) -> List[MultipleTestingResult]:
        """Calculates BH FDR, BY FDR, and Holm-Bonferroni corrected p-values across candidate models."""
        m = len(p_values)
        if m == 0:
            return []

        indexed_p = sorted(enumerate(p_values), key=lambda x: x[1])

        # 1. Benjamini-Hochberg (BH)
        bh_q = [0.0] * m
        min_q = 1.0
        for rank in range(m, 0, -1):
            idx, p = indexed_p[rank - 1]
            q = (p * m) / rank
            min_q = min(min_q, q)
            bh_q[idx] = min(min_q, 1.0)

        # 2. Benjamini-Yekutieli (BY)
        c_m = sum(1.0 / i for i in range(1, m + 1))
        by_q = [0.0] * m
        min_by = 1.0
        for rank in range(m, 0, -1):
            idx, p = indexed_p[rank - 1]
            q = (p * m * c_m) / rank
            min_by = min(min_by, q)
            by_q[idx] = min(min_by, 1.0)

        # 3. Holm-Bonferroni
        holm_p = [0.0] * m
        running_max = 0.0
        for rank in range(1, m + 1):
            idx, p = indexed_p[rank - 1]
            adjusted = p * (m - rank + 1)
            running_max = max(running_max, adjusted)
            holm_p[idx] = min(running_max, 1.0)

        results = []
        for i in range(m):
            p = p_values[i]
            q_bh = bh_q[i]
            q_by = by_q[i]
            p_holm = holm_p[i]
            results.append(MultipleTestingResult(
                test_id=f"hypothesis_{i+1}",
                raw_p_value=round(p, 6),
                bh_q_value=round(q_bh, 6),
                by_q_value=round(q_by, 6),
                holm_p_value=round(p_holm, 6),
                significant_fdr_05=(q_bh <= alpha),
                significant_fwer_05=(p_holm <= alpha)
            ))
        return results

    @classmethod
    def evaluate_walk_forward(
        cls,
        features: Sequence[Any],
        labels: Sequence[Any],
        model_factory: ModelFactory,
        scorer: Optional[Scorer] = None,
        n_folds: int = 5,
        min_train_size: int = 20,
        embargo_size: int = 2,
        min_score_threshold: float = 0.0,
        max_std_err: float = 2.0,
        require_significant_fdr: bool = False,
    ) -> WalkForwardEvaluation:
        """Runs purged walk-forward validation with real model fitting per fold.

        Args:
            features: chronological feature rows.
            labels: chronological labels aligned with features.
            model_factory: callable returning a fresh Model instance per fold.
            scorer: optional scoring function; defaults to accuracy.
            n_folds, min_train_size, embargo_size: fold construction parameters.
            min_score_threshold: minimum acceptable mean out-of-sample score.
            max_std_err: maximum acceptable standard error of the mean score.
            require_significant_fdr: if True, gate also requires at least one fold-level
                raw p-value to survive BH FDR at 0.05 (p-values are computed from a
                binomial test against a 0.5 random baseline).
        """
        if len(features) != len(labels):
            raise ValueError("features and labels must have the same length")
        n = len(labels)
        if n == 0:
            return WalkForwardEvaluation(
                n_folds=0, mean_out_of_sample_score=0.0,
                score_standard_error=1.0, fold_scores=[], fold_results=[],
                passed_gate=False, failure_reasons=["empty input series"]
            )

        scorer = scorer or cls.accuracy_scorer
        folds = cls.construct_purged_folds(n, n_folds, min_train_size, embargo_size)
        if not folds:
            return WalkForwardEvaluation(
                n_folds=0, mean_out_of_sample_score=0.0,
                score_standard_error=1.0, fold_scores=[], fold_results=[],
                passed_gate=False, failure_reasons=["no folds could be constructed"]
            )

        fold_results: List[FoldResult] = []
        for split in folds:
            model = model_factory()
            X_train = features[split.train_start:split.train_end]
            y_train = labels[split.train_start:split.train_end]
            X_test = features[split.test_start:split.test_end]
            y_test = labels[split.test_start:split.test_end]
            if len(X_train) == 0 or len(X_test) == 0:
                continue
            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)
            score = scorer(y_test, y_pred)
            fold_results.append(FoldResult(
                fold_idx=split.fold_idx,
                train_size=len(X_train),
                test_size=len(X_test),
                score=score,
            ))

        fold_scores = [f.score for f in fold_results]
        n_eval = len(fold_scores)
        if n_eval == 0:
            return WalkForwardEvaluation(
                n_folds=0, mean_out_of_sample_score=0.0,
                score_standard_error=1.0, fold_scores=[], fold_results=fold_results,
                passed_gate=False, failure_reasons=["all folds produced empty train/test splits"]
            )

        mean_score = sum(fold_scores) / n_eval
        var = sum((s - mean_score) ** 2 for s in fold_scores) / max(1, n_eval - 1)
        se = math.sqrt(var / n_eval) if n_eval > 1 else 0.0

        # Wald z-test p-value against a 0.5 chance baseline per fold (one-sided).
        # NOTE: this contract assumes `score` is an accuracy-like proportion in [0, 1]
        # where 0.5 is the random baseline. For other scorer kinds, supply fold_p_values
        # explicitly via evaluate_walk_forward_folds instead of relying on this default.
        p_values: List[float] = []
        for f in fold_results:
            if f.test_size > 0:
                se_binom = math.sqrt(0.5 * 0.5 / f.test_size)
                z = (f.score - 0.5) / max(se_binom, 1e-9)
                p_value = 1.0 - 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
                p_value = min(max(p_value, 0.0), 1.0)
            else:
                p_value = 1.0
            f.p_value = p_value
            p_values.append(p_value)

        mt_summary = cls.adjust_p_values(p_values, alpha=0.05) if p_values else None

        failure_reasons: List[str] = []
        passed = True
        if mean_score < min_score_threshold:
            failure_reasons.append(f"mean_score {mean_score:.4f} < threshold {min_score_threshold}")
            passed = False
        if se > max_std_err:
            failure_reasons.append(f"std_err {se:.4f} > max {max_std_err}")
            passed = False
        if require_significant_fdr and mt_summary:
            if not any(r.significant_fdr_05 for r in mt_summary):
                failure_reasons.append("no fold-level result significant under BH FDR 0.05")
                passed = False

        return WalkForwardEvaluation(
            n_folds=n_eval,
            mean_out_of_sample_score=round(mean_score, 4),
            score_standard_error=round(se, 4),
            fold_scores=fold_scores,
            fold_results=fold_results,
            passed_gate=passed,
            multiple_testing_summary=mt_summary,
            failure_reasons=failure_reasons,
        )

    @classmethod
    def evaluate_walk_forward_folds(
        cls,
        fold_scores: List[float],
        fold_p_values: Optional[List[float]] = None,
        min_score_threshold: float = 0.0,
        max_std_err: float = 2.0
    ) -> WalkForwardEvaluation:
        """Legacy entry point: aggregates pre-computed fold scores.

        Deprecated for new code; use `evaluate_walk_forward` to fit models inside the gate.
        """
        n = len(fold_scores)
        if n == 0:
            return WalkForwardEvaluation(
                n_folds=0, mean_out_of_sample_score=0.0,
                score_standard_error=1.0, fold_scores=[], fold_results=[],
                passed_gate=False, failure_reasons=["empty fold_scores"]
            )

        mean_score = sum(fold_scores) / n
        var = sum((s - mean_score) ** 2 for s in fold_scores) / max(1, n - 1)
        se = math.sqrt(var / n) if n > 1 else 0.0
        passed = (mean_score >= min_score_threshold) and (se <= max_std_err)
        mt_summary = cls.adjust_p_values(fold_p_values, alpha=0.05) if fold_p_values else None

        return WalkForwardEvaluation(
            n_folds=n,
            mean_out_of_sample_score=round(mean_score, 4),
            score_standard_error=round(se, 4),
            fold_scores=fold_scores,
            fold_results=[],
            passed_gate=passed,
            multiple_testing_summary=mt_summary,
        )