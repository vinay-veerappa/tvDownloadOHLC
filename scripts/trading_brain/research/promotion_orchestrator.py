"""Decoupled 4-Tier Promotion Orchestrator (Milestone 3.4).

Maintains 4 independent promotion tiers with strict isolation:
- Tier 1: Forecast Model (Calibration Brier <= Baseline, ECE <= 0.08, FDR q <= 0.05)
- Tier 2: Signal Model (Positive Expectancy, Precision, Win Rate)
- Tier 3: Execution Policy (Realized EV in R after slippage & commissions)
- Tier 4: Portfolio Deployment (Max Drawdown, Tail Risk, Prop Risk Limits)
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from scripts.trading_brain.db.connection import get_db_connection
from scripts.utils.market_calendar import now_iso_utc


@dataclass
class TierPromotionResult:
    tier: int                                  # 1, 2, 3, or 4
    tier_name: str
    target_id: str
    promoted: bool
    status: str                                # 'PROMOTED', 'REJECTED', 'PENDING'
    evaluation_metrics: Dict[str, Any]
    reason: str


class PromotionOrchestrator:
    """Orchestrates multi-tier governance and promotion audits."""

    @classmethod
    def evaluate_tier_1_forecast_model(
        cls,
        model_version_id: str,
        brier_skill_score: float,
        ece: float,
        fdr_q_value: float,
        db_path: Optional[Union[str, Path]] = None
    ) -> TierPromotionResult:
        """Tier 1: Forecast Model Promotion (Calibration & Discrimination)."""
        passed = (brier_skill_score > 0.0) and (ece <= 0.08) and (fdr_q_value <= 0.05)
        new_status = "CHAMPION" if passed else "REJECTED"
        reason = "Passed BSS > 0, ECE <= 0.08, FDR q <= 0.05" if passed else "Failed calibration thresholds"
        
        metrics = {
            "brier_skill_score": brier_skill_score,
            "ece": ece,
            "fdr_q_value": fdr_q_value
        }
        
        if passed:
            with get_db_connection(db_path) as conn:
                # Demote existing CHAMPION to RETIRED
                conn.execute("UPDATE model_versions SET status = 'RETIRED' WHERE status = 'CHAMPION';")
                conn.execute(
                    """
                    INSERT INTO model_versions (
                        model_version_id, model_family, version_tag, parameter_hash,
                        feature_manifest_json, calibration_metrics_json, status
                    ) VALUES (?, 'PROFILER_DAY_TYPE', '1.0.0', 'hash', '{}', ?, 'CHAMPION');
                    """,
                    (model_version_id, json.dumps(metrics))
                )
                
        return TierPromotionResult(
            tier=1,
            tier_name="FORECAST_MODEL",
            target_id=model_version_id,
            promoted=passed,
            status=new_status,
            evaluation_metrics=metrics,
            reason=reason
        )

    @classmethod
    def evaluate_tier_2_signal_model(
        cls,
        strategy_version_id: str,
        expectancy_bps: float,
        win_rate: float,
        fdr_q_value: float
    ) -> TierPromotionResult:
        """Tier 2: Signal Model Promotion (Opportunity Expectancy)."""
        passed = (expectancy_bps >= 2.0) and (win_rate >= 0.50) and (fdr_q_value <= 0.05)
        status = "PROMOTED" if passed else "REJECTED"
        metrics = {"expectancy_bps": expectancy_bps, "win_rate": win_rate, "fdr_q_value": fdr_q_value}
        reason = "Expectancy >= 2 bps, Win Rate >= 50%" if passed else "Sub-threshold signal expectancy"
        
        return TierPromotionResult(
            tier=2,
            tier_name="SIGNAL_MODEL",
            target_id=strategy_version_id,
            promoted=passed,
            status=status,
            evaluation_metrics=metrics,
            reason=reason
        )
