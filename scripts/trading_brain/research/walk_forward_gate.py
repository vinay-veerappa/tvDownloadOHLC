"""Multi-Fold Purged Walk-Forward Validator & Multiple Testing Gate (Milestone 3.2).

Enforces:
1. Real Purged Cross-Validation: Constructs K expanding time-series folds with an embargo buffer
   to eliminate lookahead leakage and auto-correlation overlap.
2. Multiple Hypothesis Testing Corrections across candidate models/hypotheses:
   - Benjamini-Hochberg (BH) False Discovery Rate (FDR q-values)
   - Benjamini-Yekutieli (BY) Arbitrary Dependence Control
   - Holm-Bonferroni Family-Wise Error Rate (FWER)
"""

import math
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple, Union


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
class WalkForwardEvaluation:
    n_folds: int
    mean_out_of_sample_score: float
    score_standard_error: float
    fold_scores: List[float]
    passed_gate: bool
    multiple_testing_summary: Optional[List[MultipleTestingResult]] = None


class WalkForwardGate:
    """Validator that executes purged cross-validation and multiple comparison corrections."""

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
            
        test_size = (n_samples - min_train_size) // n_folds
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
    def evaluate_walk_forward_folds(
        cls,
        fold_scores: List[float],
        fold_p_values: Optional[List[float]] = None,
        min_score_threshold: float = 0.0,
        max_std_err: float = 2.0
    ) -> WalkForwardEvaluation:
        """Evaluates aggregate out-of-sample fold distribution across purged splits."""
        n = len(fold_scores)
        if n == 0:
            return WalkForwardEvaluation(
                n_folds=0, mean_out_of_sample_score=0.0,
                score_standard_error=1.0, fold_scores=[], passed_gate=False
            )
            
        mean_score = sum(fold_scores) / n
        var = sum((s - mean_score) ** 2 for s in fold_scores) / max(1, n - 1)
        se = math.sqrt(var / n) if n > 1 else 0.0
        
        # Candidate passes if mean score exceeds threshold and standard error is bounded
        passed = (mean_score >= min_score_threshold) and (se <= max_std_err)
        
        return WalkForwardEvaluation(
            n_folds=n,
            mean_out_of_sample_score=round(mean_score, 4),
            score_standard_error=round(se, 4),
            fold_scores=fold_scores,
            passed_gate=passed
        )
