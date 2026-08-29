"""Pytest suite for WalkForwardGate (Milestone 3.2)."""

import pytest
from scripts.trading_brain.research.walk_forward_gate import WalkForwardGate


def test_multiple_testing_adjustments_fdr_and_fwer():
    """Tests BH FDR, BY FDR, and Holm-Bonferroni p-value corrections."""
    raw_p = [0.001, 0.01, 0.04, 0.10, 0.50]
    
    results = WalkForwardGate.adjust_p_values(raw_p, alpha=0.05)
    assert len(results) == 5
    
    # Lowest p-value must be significant under both FDR and FWER
    assert results[0].significant_fdr_05 is True
    assert results[0].bh_q_value <= 0.01
    assert results[0].holm_p_value <= 0.01


def test_evaluate_walk_forward_folds():
    """Tests purged walk-forward fold evaluation."""
    scores = [12.5, 14.0, 11.0, 15.2, 13.8]
    p_values = [0.001, 0.002, 0.004, 0.001, 0.002]
    
    eval_res = WalkForwardGate.evaluate_walk_forward_folds(scores, p_values, min_score_threshold=5.0)
    assert eval_res.n_folds == 5
    assert eval_res.mean_out_of_sample_score > 10.0
    assert eval_res.passed_gate is True
