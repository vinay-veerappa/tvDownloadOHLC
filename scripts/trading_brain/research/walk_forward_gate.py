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
    aggregated_p_value: Optional[float] = None
    audit_only: bool = False


class Scorer(Protocol):
    """A scorer receives true labels and predictions and returns a float score."""
    def __call__(self, y_true: Sequence[Any], y_pred: Sequence[Any]) -> float: ...


class Model(Protocol):
    """A model supports fit(train_features, train_labels) and predict(test_features)."""
    def fit(self, X_train: Sequence[Any], y_train: Sequence[Any]) -> None: ...
    def predict(self, X_test: Sequence[Any]) -> Sequence[Any]: ...


ModelFactory = Callable[[], Model]


def _norminv_one_sided(p: float) -> float:
    """Inverse standard normal CDF Phi^{-1}(p) via bisection on the exact erf.

    Bisection on a monotone function is immune to coefficient-transcription errors;
    80 iterations converge below float precision. Cost is negligible (k folds x O(80)).
    """
    p = min(max(p, 1e-15), 1.0 - 1e-15)
    lo, hi = -40.0, 40.0
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        cdf = 0.5 * (1.0 + math.erf(mid / math.sqrt(2.0)))
        if cdf < p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def _upper_tail_z_from_p(p: float) -> float:
    """Converts an UPPER-TAIL p-value to its z-score: z = Phi^{-1}(1 - p).

    Fold p-values are upper-tail (p = 1 - Phi(z)), so small p must map to LARGE
    positive z. Returning Phi^{-1}(p) here (the lower-tail quantile) would invert
    the evidence sign and aggregate strong folds into p ~ 1.0.
    """
    return -_norminv_one_sided(p)


def _labels_for_stream(seq: Sequence[Any]) -> List[Any]:
    """Passes through a label/prediction stream (hook kept for normalization evolution)."""
    return list(seq)


class WalkForwardGate:
    """Validator that executes purged cross-validation and multiple comparison corrections."""

    @staticmethod
    def _block_bootstrap_accuracy_p(
        correct_stream: Sequence[int],
        n_boot: int = 2000,
        block_len: int = None,
        seed: int = 42,
    ) -> float:
        """Dependence-aware one-sided p for OOS accuracy > 0.5 via circular block bootstrap.

        Walk-forward out-of-sample streams are autocorrelated (regimes cluster), so a
        binomial test on each observation understates variance and fabricated fold
        independence overstates evidence. The bootstrap resamples contiguous blocks of
        the FULL chronological stream (preserving local dependence) under the null
        (mean 0.5 centered), returning the fraction of resample means >= observed.
        """
        import random as _random
        n = len(correct_stream)
        if n == 0:
            return 1.0
        obs = sum(correct_stream) / n
        blk = max(2, min(int(block_len or max(2, n // 10)), n))
        rng = _random.Random(seed)
        # Null distribution of the resampled mean (block bootstrap preserves the
        # stream's local dependence while the CENTERING keeps the resampled mean
        # centered at the 0.5 chance baseline - without it, a degenerate stream like
        # all-1s yields a null distribution at 1.0 and inverts the test).
        null_means: List[float] = []
        for _ in range(max(1, int(n_boot))):
            mean_sum = 0.0
            remaining = n
            while remaining > 0:
                start = rng.randrange(n)
                take = min(blk, remaining)
                for k in range(take):
                    mean_sum += correct_stream[(start + k) % n]
                remaining -= take
            null_means.append(mean_sum / n)
        mean_null = sum(null_means) / len(null_means)
        excess = sum(1 for m in null_means if (m - mean_null) >= (obs - 0.5))
        p = excess / len(null_means)
        # exact-style floor: with limited resamples the smallest attainable p is 1/B
        return max(p, 1.0 / max(1, int(n_boot)))

    @classmethod
    def evaluate_candidate_family(
        cls,
        candidate_p_values: Sequence[Tuple[str, float]],
        alpha: float = 0.05,
    ) -> List[Dict[str, Any]]:
        """THE single family-level multiplicity correction stage for a research round.

        Every preregistered candidate's aggregate p-value (from evaluate_walk_forward's
        aggregated_p_value) is submitted ONCE, together, so a raw p=0.02 that is rank-5
        of 5 becomes q=0.10 instead of 'significant as a family of one'. Returns per-
        candidate BH q-values and pass/fail against alpha; callers must gate on the
        corrected q, never the raw p.
        """
        if not candidate_p_values:
            return []
        ids = [c for c, _ in candidate_p_values]
        ps = [p for _, p in candidate_p_values]
        results = cls.adjust_p_values(ps, alpha=alpha)
        return [
            {
                "candidate_id": cid,
                "raw_p_value": round(p, 8),
                "bh_q_value": results[i].bh_q_value,
                "significant_fdr_05": results[i].significant_fdr_05,
            }
            for i, (cid, p) in enumerate(zip(ids, ps))
        ]

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
        family_p_values: Optional[Sequence[float]] = None,
        current_candidate_family_index: Optional[int] = None,
        require_family_declaration: bool = False,
        family_results: Optional[Dict[str, float]] = None,
        current_candidate_id: Optional[str] = None,
        bootstrap_b: int = 2000,
        bootstrap_seed: int = 42,
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
            require_significant_fdr: if True, gate requires the AGGREGATED
                candidate-level p-value to survive BH FDR at 0.05.
            family_p_values: positional family interface (raw p-values, this candidate
                INCLUDED). Only usable together with current_candidate_family_index,
                and only when that index declares THIS candidate's exact aggregate p -
                a mismatched index is refused as identity borrowing (sixth-audit F1).
            current_candidate_family_index: this candidate's zero-based position in
                family_p_values; must satisfy family_p_values[index] == aggregate p.
            require_family_declaration: promotion-capable mode (F9): when True and no
                family is declared, the gate FAILS CLOSED with a FAMILY_UNDECLARED
                reason instead of the family-of-one fallback.
            family_results: PREFERRED ID-keyed family interface: mapping
                {candidate_id: aggregate_p} covering the complete preregistered
                family. Requires current_candidate_id; refused when the declared
                value for the current candidate does not equal this evaluation's
                aggregate p.
            current_candidate_id: this candidate's ID within family_results.
            bootstrap_b: resamples for the dependence-aware block-bootstrap aggregate
                over the chronological out-of-sample stream (0 disables bootstrap and
                falls back to the Stouffer fold aggregate).
            bootstrap_seed: RNG seed for the bootstrap (deterministic gates).
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
        oos_true: List[Any] = []       # full chronological out-of-sample label stream
        oos_pred: List[Any] = []       # matching prediction stream (dependence-aware stats)
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
            oos_true.extend(y_test)
            oos_pred.extend(y_pred)
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

        # Candidate-level aggregation. Expanding walk-forward folds share training
        # history and overlapping test regimes, so plain Stouffer (which assumes fold
        # independence) overstates evidence under positive dependence (F9). The
        # DEPENDENCE-AWARE default computes the candidate p from the full chronological
        # out-of-sample stream via a circular block bootstrap: it preserves the
        # autocorrelation of the prediction stream without treating each observation
        # as independent. Stouffer is retained as the cross-check aggregate.
        aggregated_p_bootstrap: Optional[float] = None
        aggregated_p_stouffer = cls._stouffer_aggregate_p(fold_results) if fold_results else 1.0
        if oos_true and len(oos_true) >= 10:
            correct_stream = [
                1 if str(p).upper() == str(t).upper() else 0
                for t, p in zip(_labels_for_stream(oos_true), _labels_for_stream(oos_pred))
            ]
            aggregated_p_bootstrap = cls._block_bootstrap_accuracy_p(
                correct_stream, n_boot=bootstrap_b, block_len=max(2, len(correct_stream) // 10), seed=bootstrap_seed
            )
            aggregated_p = aggregated_p_bootstrap
        else:
            aggregated_p = aggregated_p_stouffer

        # Family-level multiplicity: BH correction runs across the PREREGISTERED
        # candidate family when the caller declares it. The gate checks THIS
        # candidate's OWN corrected q-value (sixth-audit F1: an UNSUPPORTED index
        # would let this null candidate borrow a significant sibling's identity, so
        # the preferred interface is ID-keyed families - family_results mapping
        # candidate_id -> aggregate p with current_candidate_id naming THIS candidate;
        # the positional interface remains only with a strict value-match check).
        # Omitted family -> explicit family-of-one (suitable for isolated dev tests
        # only; promotion-capable rounds should pass the complete family or use
        # evaluate_candidate_family() as the separate correction stage).
        this_candidate_rank: Optional[int] = None
        if family_results is not None and len(family_results) > 0:
            if current_candidate_id is None:
                raise ValueError(
                    "family_results requires current_candidate_id: the gate evaluates "
                    "the candidate NAMED in the ID-keyed family, not an index a caller "
                    "can point at a sibling."
                )
            if current_candidate_id not in family_results:
                raise ValueError(
                    f"current_candidate_id '{current_candidate_id}' is not a member of the "
                    "declared candidate family."
                )
            if float(family_results[current_candidate_id]) != float(aggregated_p):
                raise ValueError(
                    f"Family record for '{current_candidate_id}' declares aggregate p="
                    f"{family_results[current_candidate_id]}, but this evaluation produced "
                    f"p={aggregated_p}. The family declaration and the evaluated candidate "
                    "disagree - refusing to borrow a sibling's identity."
                )
            # Materialize the BH over the ID-keyed family, preserving ID association.
            mt_summary = cls.adjust_p_values(list(family_results.values()), alpha=0.05)
            this_candidate_rank = list(family_results.keys()).index(current_candidate_id)
        elif family_p_values is not None and len(family_p_values) > 0:
            if current_candidate_family_index is not None:
                if not (0 <= current_candidate_family_index < len(family_p_values)):
                    raise ValueError(
                        f"current_candidate_family_index {current_candidate_family_index} out of "
                        f"range for family of {len(family_p_values)} candidates."
                    )
                # STRICT value binding (sixth-audit F1 minimal fix): the declared index
                # must actually point at THIS candidate's aggregate p. Pointing the
                # index at a significant sibling is an identity theft, not a family
                # membership.
                declared = float(family_p_values[current_candidate_family_index])
                if abs(declared - float(aggregated_p)) > 1e-12:
                    raise ValueError(
                        f"current_candidate_family_index {current_candidate_family_index} declares "
                        f"family p={declared}, but this candidate's aggregate p={aggregated_p}. "
                        "An index that does not match the evaluated candidate is identity "
                        "borrowing, not membership."
                    )
                this_candidate_rank = current_candidate_family_index
            else:
                # Fallback: identify by exact value match; ambiguity (duplicate
                # values) is refused because equal p-values cannot disambiguate
                # which candidate is being certified.
                matches = [i for i, p in enumerate(family_p_values) if abs(float(p) - float(aggregated_p)) <= 1e-12]
                if len(matches) > 1:
                    raise ValueError(
                        "family_p_values contains duplicate values equal to this "
                        "candidate's aggregate p; pass current_candidate_family_index "
                        "(or use ID-keyed family_results)."
                    )
                if not matches:
                    raise ValueError(
                        "family_p_values declared but do not contain this candidate's "
                        "aggregate p; pass current_candidate_family_index explicitly."
                    )
                this_candidate_rank = matches[0]
            mt_summary = cls.adjust_p_values(list(family_p_values), alpha=0.05)
        else:
            mt_summary = cls.adjust_p_values([aggregated_p] * 1, alpha=0.05)

        failure_reasons: List[str] = []
        passed = True
        # F9 promotion-capable strictness: a family of one is a dev convenience, never
        # a certification basis. Strict mode requires the declared family up front.
        if require_family_declaration and not (
            (family_results is not None and len(family_results) > 0)
            or (family_p_values is not None and len(family_p_values) > 0)
        ):
            failure_reasons.append(
                "FAMILY_UNDECLARED: promotion-capable evaluation requires the complete "
                "preregistered candidate family (ID-keyed family_results + "
                "current_candidate_id, or family_p_values + member index); a "
                "family-of-one fallback is not a certification basis."
            )
            passed = False
            mt_summary = None
        else:
            if mean_score < min_score_threshold:
                failure_reasons.append(f"mean_score {mean_score:.4f} < threshold {min_score_threshold}")
                passed = False
            if se > max_std_err:
                failure_reasons.append(f"std_err {se:.4f} > max {max_std_err}")
                passed = False
            # Gate requires THIS candidate's aggregated p to be significant under the
            # family-level BH correction - never 'any member of the family passed', which
            # would approve a null candidate on the strength of a sibling.
            if require_significant_fdr:
                if mt_summary is None:
                    failure_reasons.append("multiple-testing summary unavailable")
                    passed = False
                else:
                    if this_candidate_rank is not None:
                        this_q = mt_summary[this_candidate_rank]
                        candidate_significant = this_q.significant_fdr_05
                        q_desc = f"this candidate's family BH q={this_q.bh_q_value:.4f}"
                    else:
                        candidate_significant = mt_summary[0].significant_fdr_05
                        q_desc = f"family-of-one BH q={mt_summary[0].bh_q_value:.4f}"
                    if not candidate_significant:
                        failure_reasons.append(
                            f"aggregated candidate p={aggregated_p:.4f} not significant "
                            f"({q_desc}; BH FDR 0.05)"
                        )
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
            aggregated_p_value=aggregated_p,
        )

    @staticmethod
    def _stouffer_aggregate_p(fold_results: List["FoldResult"]) -> float:
        """Weighted Stouffer combination of per-fold one-sided p-values.

        Weights are sqrt(test_size), so larger out-of-sample windows contribute more.
        Exact correlation between overlapping expanding-window folds is unknown; the
        aggregated p is therefore a LOWER bound on dependence-corrected significance
        (conservative for gating when combined with the mean/SE thresholds).
        """
        k = len(fold_results)
        if k == 0:
            return 1.0
        z_sum = 0.0
        w_sq_sum = 0.0
        for f in fold_results:
            p = min(max(f.p_value if f.p_value is not None else 1.0, 1e-12), 1.0)
            # Fold p-values are UPPER-tail: small p -> large positive z.
            z = _upper_tail_z_from_p(p)
            w = math.sqrt(max(f.test_size, 1))
            z_sum += w * z
            w_sq_sum += w * w
        z_agg = z_sum / math.sqrt(w_sq_sum) if w_sq_sum > 0 else 0.0
        p_agg = 1.0 - 0.5 * (1.0 + math.erf(z_agg / math.sqrt(2.0)))
        return min(max(p_agg, 0.0), 1.0)

    @classmethod
    def _stouffer_aggregate(cls, fold_results: List["FoldResult"]) -> float:
        return cls._stouffer_aggregate_p(fold_results)

    @classmethod
    def evaluate_walk_forward_folds(
        cls,
        fold_scores: List[float],
        fold_p_values: Optional[List[float]] = None,
        min_score_threshold: float = 0.0,
        max_std_err: float = 2.0
    ) -> WalkForwardEvaluation:
        """AUDIT-ONLY entry point: aggregates pre-computed fold scores for review.

        This path NEVER returns a promotable pass: it cannot verify that the scores came
        from embargoed, purge-corrected folds fit inside the gate, so its `passed_gate`
        is always False with an explicit audit-only reason. Use `evaluate_walk_forward`
        for any promotable decision.
        """
        n = len(fold_scores)
        if n == 0:
            return WalkForwardEvaluation(
                n_folds=0, mean_out_of_sample_score=0.0,
                score_standard_error=1.0, fold_scores=[],
                passed_gate=False,
                failure_reasons=["AUDIT_ONLY: empty fold_scores"],
                audit_only=True,
            )

        mean_score = sum(fold_scores) / n
        var = sum((s - mean_score) ** 2 for s in fold_scores) / max(1, n - 1)
        se = math.sqrt(var / n) if n > 1 else 0.0
        mt_summary = cls.adjust_p_values(fold_p_values, alpha=0.05) if fold_p_values else None

        return WalkForwardEvaluation(
            n_folds=n,
            mean_out_of_sample_score=round(mean_score, 4),
            score_standard_error=round(se, 4),
            fold_scores=fold_scores,
            fold_results=[],
            passed_gate=False,
            multiple_testing_summary=mt_summary,
            failure_reasons=[
                "AUDIT_ONLY: precomputed fold scores cannot verify embargo/purge/fit integrity; "
                "not promotable evidence. Use evaluate_walk_forward()."
            ],
            audit_only=True,
        )