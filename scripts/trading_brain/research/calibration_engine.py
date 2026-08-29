"""Multiclass Proper-Score Loss Engine & Probability Calibration Analyzer (Milestone 3.1).

Computes:
1. Multiclass Brier Score across 5 MECE day types: sum_{i=1}^5 (p_i - o_i)^2
2. Multiclass Log Loss: -ln(max(p_realized, 1e-6))
3. Skill Scores vs 3 Baselines:
   - Base Rate Prior (unconditional historical frequency)
   - Rolling 50-Session Frequency
   - Incumbent Champion Model
4. Expected Calibration Error (ECE) across reliability bins.
"""

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

DAY_TYPES = ["R1", "R2", "DNP", "DWP", "ROTATIONAL_CHOP"]


@dataclass
class CalibrationMetrics:
    sample_size: int
    mean_brier_score: float
    mean_log_loss: float
    brier_skill_score_vs_prior: float          # 1 - (Brier_model / Brier_prior)
    brier_skill_score_vs_champion: Optional[float]
    expected_calibration_error: float          # ECE
    calibration_status: str                    # 'CALIBRATED', 'OVERCONFIDENT', 'UNDERCONFIDENT', 'DEGENERATE'


class CalibrationEngine:
    """Calculates proper scoring rules and calibration statistics for probabilistic day-type forecasts."""

    @staticmethod
    def compute_single_brier_score(
        probs: Dict[str, float],
        realized_day_type: str
    ) -> float:
        """Computes single-session multi-class Brier score."""
        realized = realized_day_type.upper()
        total_loss = 0.0
        for dt in DAY_TYPES:
            p = probs.get(dt, 0.0)
            o = 1.0 if dt == realized else 0.0
            total_loss += (p - o) ** 2
        return total_loss

    @staticmethod
    def compute_single_log_loss(
        probs: Dict[str, float],
        realized_day_type: str,
        eps: float = 1e-6
    ) -> float:
        """Computes single-session multi-class log loss."""
        realized = realized_day_type.upper()
        p = max(probs.get(realized, 0.0), eps)
        return -math.log(p)

    @classmethod
    def evaluate_forecast_series(
        cls,
        forecasts: List[Dict[str, float]],
        realized_outcomes: List[str],
        prior_probs: Optional[Dict[str, float]] = None,
        champion_forecasts: Optional[List[Dict[str, float]]] = None
    ) -> CalibrationMetrics:
        """Evaluates a series of probabilistic forecasts against realized outcomes."""
        n = len(forecasts)
        if n == 0 or len(realized_outcomes) != n:
            raise ValueError(f"Mismatched or empty series: {n} forecasts, {len(realized_outcomes)} outcomes")
            
        default_prior = prior_probs or {dt: 1.0 / len(DAY_TYPES) for dt in DAY_TYPES}
        
        model_briers = []
        model_logs = []
        prior_briers = []
        champ_briers = []
        
        for i in range(n):
            f = forecasts[i]
            r = realized_outcomes[i]
            
            model_briers.append(cls.compute_single_brier_score(f, r))
            model_logs.append(cls.compute_single_log_loss(f, r))
            prior_briers.append(cls.compute_single_brier_score(default_prior, r))
            
            if champion_forecasts and i < len(champion_forecasts):
                champ_briers.append(cls.compute_single_brier_score(champion_forecasts[i], r))
                
        mean_brier = sum(model_briers) / n
        mean_log = sum(model_logs) / n
        mean_prior_brier = sum(prior_briers) / n
        
        bss_prior = 1.0 - (mean_brier / mean_prior_brier) if mean_prior_brier > 0 else 0.0
        
        bss_champ = None
        if champ_briers:
            mean_champ_brier = sum(champ_briers) / len(champ_briers)
            bss_champ = 1.0 - (mean_brier / mean_champ_brier) if mean_champ_brier > 0 else 0.0
            
        # Compute ECE across 5 bins
        ece = cls.compute_ece(forecasts, realized_outcomes, n_bins=5)
        
        status = "CALIBRATED" if ece <= 0.08 and bss_prior >= 0.0 else ("OVERCONFIDENT" if ece > 0.15 else "UNCALIBRATED")
        
        return CalibrationMetrics(
            sample_size=n,
            mean_brier_score=round(mean_brier, 4),
            mean_log_loss=round(mean_log, 4),
            brier_skill_score_vs_prior=round(bss_prior, 4),
            brier_skill_score_vs_champion=round(bss_champ, 4) if bss_champ is not None else None,
            expected_calibration_error=round(ece, 4),
            calibration_status=status
        )

    @classmethod
    def compute_ece(
        cls,
        forecasts: List[Dict[str, float]],
        realized_outcomes: List[str],
        n_bins: int = 5
    ) -> float:
        """Computes multiclass Expected Calibration Error (ECE) across confidence bins."""
        bin_limits = [i / n_bins for i in range(n_bins + 1)]
        total_samples = 0
        total_weighted_error = 0.0
        
        for b in range(n_bins):
            low, high = bin_limits[b], bin_limits[b + 1]
            bin_confidences = []
            bin_accuracies = []
            
            for i, f in enumerate(forecasts):
                realized = realized_outcomes[i].upper()
                for dt in DAY_TYPES:
                    p = f.get(dt, 0.0)
                    if low <= p < high or (b == n_bins - 1 and p == high):
                        bin_confidences.append(p)
                        bin_accuracies.append(1.0 if dt == realized else 0.0)
                        
            if bin_confidences:
                bin_size = len(bin_confidences)
                avg_conf = sum(bin_confidences) / bin_size
                avg_acc = sum(bin_accuracies) / bin_size
                total_weighted_error += bin_size * abs(avg_acc - avg_conf)
                total_samples += bin_size
                
        return total_weighted_error / total_samples if total_samples > 0 else 0.0
