"""Multiclass Proper-Score Loss Engine & Probability Calibration Analyzer (Milestone 3.1).

Computes:
1. Multiclass Brier Score across 5 MECE day types: sum_{i=1}^5 (p_i - o_i)^2
2. Multiclass Log Loss: -ln(max(p_realized, 1e-6))
3. Skill Scores vs 3 Baselines:
   - Base Rate Prior (unconditional empirical historical frequency)
   - Rolling 50-Session Frequency
   - Incumbent Champion Model (evaluated over identical sample series)
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
    def compute_unconditional_prior(cls, realized_outcomes: List[str]) -> Dict[str, float]:
        """Derives empirical unconditional base rate frequencies from historical outcome series."""
        n = len(realized_outcomes)
        if n == 0:
            return {dt: 1.0 / len(DAY_TYPES) for dt in DAY_TYPES}
        counts = {dt: 0 for dt in DAY_TYPES}
        for r in realized_outcomes:
            if r in counts:
                counts[r] += 1
        return {dt: (counts[dt] / n) for dt in DAY_TYPES}

    @staticmethod
    def validate_forecast_probs(probs: Dict[str, float], index: Optional[int] = None) -> None:
        """Validates one forecast probability vector: all 5 classes present, in [0,1], sums to 1.

        Fails closed on malformed probability vectors so calibration metrics cannot be
        silently computed over degenerate distributions.
        """
        idx_label = f" at index {index}" if index is not None else ""
        missing = [dt for dt in DAY_TYPES if dt not in probs]
        if missing:
            raise ValueError(f"Forecast{idx_label} missing day types: {missing}")
        for dt in DAY_TYPES:
            p = probs[dt]
            if not isinstance(p, (int, float)) or not math.isfinite(float(p)) or not (0.0 <= float(p) <= 1.0):
                raise ValueError(f"Forecast{idx_label} probability for {dt} is out of [0,1] or non-finite: {p}")
        total = sum(float(probs[dt]) for dt in DAY_TYPES)
        if abs(total - 1.0) > 1e-4:
            raise ValueError(f"Forecast{idx_label} probabilities must sum to 1.0, got {total:.6f}")

    @classmethod
    def compute_rolling_frequency_baseline(
        cls,
        realized_outcomes: List[str],
        window: int = 50,
        min_history: int = 5
    ) -> List[Dict[str, float]]:
        """Computes the declared rolling-N recency-weighted-equivalent frequency baseline.

        For each session index i, returns the empirical class frequencies observed over the
        trailing `window` sessions strictly BEFORE i — never any row at or after i, and
        never the full-series frequency (the full series includes future outcomes, which
        would leak during warm-up). The first min_history sessions use a UNIFORM prior
        (1/5 each): with no usable history, the honest prior is uniform, not a
        full-series frequency computed from data the baseline row must not see.
        """
        n = len(realized_outcomes)
        if n == 0:
            raise ValueError("Cannot compute rolling baseline over an empty outcome series.")
        uniform_prior = {dt: 1.0 / len(DAY_TYPES) for dt in DAY_TYPES}
        baseline: List[Dict[str, float]] = []
        for i in range(n):
            window_outcomes = realized_outcomes[max(0, i - window):i]
            if len(window_outcomes) < min_history:
                baseline.append(dict(uniform_prior))
                continue
            counts = {dt: 0 for dt in DAY_TYPES}
            for r in window_outcomes:
                if r in counts:
                    counts[r] += 1
            total = len(window_outcomes)
            baseline.append({dt: counts[dt] / total for dt in DAY_TYPES})
        return baseline

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
            
        if champion_forecasts is not None and len(champion_forecasts) != n:
            raise ValueError(f"Champion series length ({len(champion_forecasts)}) must match model series length ({n})")

        # Default prior: uniform. Deriving it from the FULL outcome series would hand the
        # baseline knowledge of future class frequencies (leakage); a caller with a
        # genuinely ex-ante prior (e.g. pre-registered base rates) may pass prior_probs.
        default_prior = prior_probs or {dt: 1.0 / len(DAY_TYPES) for dt in DAY_TYPES}
        
        model_briers = []
        model_logs = []
        prior_briers = []
        champ_briers = []
        
        for i in range(n):
            f = forecasts[i]
            r = realized_outcomes[i]
            
            cls.validate_forecast_probs(f, index=i)
            if r not in DAY_TYPES:
                raise ValueError(f"Realized outcome {r!r} at index {i} is not a valid day type")
            
            model_briers.append(cls.compute_single_brier_score(f, r))
            model_logs.append(cls.compute_single_log_loss(f, r))
            prior_briers.append(cls.compute_single_brier_score(default_prior, r))
            
            if champion_forecasts:
                champ_briers.append(cls.compute_single_brier_score(champion_forecasts[i], r))
                
        mean_brier = sum(model_briers) / n
        mean_log = sum(model_logs) / n
        mean_prior_brier = sum(prior_briers) / n
        
        bss_prior = 1.0 - (mean_brier / mean_prior_brier) if mean_prior_brier > 0 else 0.0
        
        bss_champ = None
        if champ_briers:
            mean_champ_brier = sum(champ_briers) / n
            bss_champ = 1.0 - (mean_brier / mean_champ_brier) if mean_champ_brier > 0 else 0.0
            
        ece = cls.compute_expected_calibration_error(forecasts, realized_outcomes)
        
        if ece <= 0.08:
            status = "CALIBRATED"
        elif mean_brier > 0.60:
            status = "OVERCONFIDENT"
        else:
            status = "UNDERCONFIDENT"
            
        return CalibrationMetrics(
            sample_size=n,
            mean_brier_score=round(mean_brier, 4),
            mean_log_loss=round(mean_log, 4),
            brier_skill_score_vs_prior=round(bss_prior, 4),
            brier_skill_score_vs_champion=round(bss_champ, 4) if bss_champ is not None else None,
            expected_calibration_error=round(ece, 4),
            calibration_status=status
        )

    @staticmethod
    def compute_expected_calibration_error(
        forecasts: List[Dict[str, float]],
        realized_outcomes: List[str],
        n_bins: int = 10
    ) -> float:
        """Calculates Expected Calibration Error (ECE) across reliability probability bins."""
        bin_sums = [0.0] * n_bins
        bin_true = [0.0] * n_bins
        bin_counts = [0] * n_bins
        
        for f, r in zip(forecasts, realized_outcomes):
            for dt in DAY_TYPES:
                conf = f.get(dt, 0.0)
                actual = 1.0 if dt == r else 0.0
                bin_idx = min(int(conf * n_bins), n_bins - 1)
                bin_sums[bin_idx] += conf
                bin_true[bin_idx] += actual
                bin_counts[bin_idx] += 1
                
        total_evals = len(forecasts) * len(DAY_TYPES)
        if total_evals == 0:
            return 0.0
            
        ece = 0.0
        for i in range(n_bins):
            if bin_counts[i] > 0:
                acc = bin_true[i] / bin_counts[i]
                conf = bin_sums[i] / bin_counts[i]
                weight = bin_counts[i] / total_evals
                ece += weight * abs(acc - conf)
                
        return ece
