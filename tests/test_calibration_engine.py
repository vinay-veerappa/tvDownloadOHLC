"""Pytest suite for CalibrationEngine (Milestone 3.1)."""

import pytest
from scripts.trading_brain.research.calibration_engine import CalibrationEngine


def test_brier_and_log_loss_calculation():
    """Tests multi-class Brier score and log-loss calculation on synthetic probabilities."""
    probs = {"R1": 0.70, "R2": 0.10, "DNP": 0.10, "DWP": 0.05, "ROTATIONAL_CHOP": 0.05}
    
    # 1. Realized R1 (True hit)
    brier_r1 = CalibrationEngine.compute_single_brier_score(probs, "R1")
    # (0.7 - 1)^2 + 0.1^2 + 0.1^2 + 0.05^2 + 0.05^2 = 0.09 + 0.01 + 0.01 + 0.0025 + 0.0025 = 0.115
    assert abs(brier_r1 - 0.115) < 1e-4
    
    log_loss_r1 = CalibrationEngine.compute_single_log_loss(probs, "R1")
    # -ln(0.70) = ~0.3567
    assert abs(log_loss_r1 - 0.3567) < 1e-3


def test_evaluate_forecast_series_and_ece():
    """Tests evaluating a series of forecasts against realized outcomes and computing skill scores."""
    forecasts = [
        {"R1": 0.8, "R2": 0.05, "DNP": 0.05, "DWP": 0.05, "ROTATIONAL_CHOP": 0.05},
        {"R1": 0.1, "R2": 0.70, "DNP": 0.10, "DWP": 0.05, "ROTATIONAL_CHOP": 0.05},
        {"R1": 0.1, "R2": 0.10, "DNP": 0.70, "DWP": 0.05, "ROTATIONAL_CHOP": 0.05}
    ]
    outcomes = ["R1", "R2", "DNP"]
    
    metrics = CalibrationEngine.evaluate_forecast_series(forecasts, outcomes)
    assert metrics.sample_size == 3
    assert metrics.mean_brier_score < 0.20
    assert metrics.brier_skill_score_vs_prior > 0.0
    assert metrics.expected_calibration_error <= 0.15
