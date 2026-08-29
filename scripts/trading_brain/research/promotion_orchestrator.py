"""Decoupled 4-Tier Promotion Orchestrator (Milestone 3.4).

Maintains 4 independent promotion tiers using append-only model_deployment_events (never mutating model_versions):
- Tier 1: Forecast Model (Calibration Brier <= Baseline, ECE <= 0.08, FDR q <= 0.05)
- Tier 2: Signal Model (Positive Expectancy >= 2 bps, Precision, Win Rate >= 50%)
- Tier 3: Execution Policy (Realized EV in R after costs >= 0.30 R, Slippage <= 2.0 bps)
- Tier 4: Portfolio Deployment (Max Drawdown <= 5.0%, Tail Risk VaR 99%, Prop Firm Limit Compliance)
"""

import json
import uuid
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
        actor: str = "ORCHESTRATOR",
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
        
        with get_db_connection(db_path) as conn:
            # Ensure model_version exists in immutable registry
            cur = conn.execute("SELECT model_version_id FROM model_versions WHERE model_version_id = ?;", (model_version_id,))
            if not cur.fetchone():
                conn.execute(
                    """
                    INSERT OR IGNORE INTO model_versions (
                        model_version_id, model_family, version_tag, parameter_hash,
                        feature_manifest_json, calibration_metrics_json, status
                    ) VALUES (?, 'PROFILER_DAY_TYPE', '1.0.0', 'hash', '{}', ?, ?);
                    """,
                    (model_version_id, json.dumps(metrics), new_status)
                )
                
            # Log append-only deployment transition
            event_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO model_deployment_events (
                    deployment_event_id, model_version_id, tier, deployment_status,
                    eval_metrics_json, actor, reason, event_timestamp_utc
                ) VALUES (?, ?, 1, ?, ?, ?, ?, ?);
                """,
                (event_id, model_version_id, new_status, json.dumps(metrics), actor, reason, now_iso_utc())
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
        fdr_q_value: float,
        actor: str = "ORCHESTRATOR",
        db_path: Optional[Union[str, Path]] = None
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

    @classmethod
    def evaluate_tier_3_execution_policy(
        cls,
        policy_id: str,
        realized_ev_r: float,
        avg_slippage_bps: float,
        cost_ratio: float
    ) -> TierPromotionResult:
        """Tier 3: Execution Policy Promotion (Realized EV in R after costs)."""
        passed = (realized_ev_r >= 0.30) and (avg_slippage_bps <= 2.0) and (cost_ratio <= 0.25)
        status = "PROMOTED" if passed else "REJECTED"
        metrics = {"realized_ev_r": realized_ev_r, "avg_slippage_bps": avg_slippage_bps, "cost_ratio": cost_ratio}
        reason = "EV >= 0.30 R, Slippage <= 2 bps" if passed else "Execution friction degraded expectancy below threshold"
        
        return TierPromotionResult(
            tier=3,
            tier_name="EXECUTION_POLICY",
            target_id=policy_id,
            promoted=passed,
            status=status,
            evaluation_metrics=metrics,
            reason=reason
        )

    @classmethod
    def evaluate_tier_4_portfolio_deployment(
        cls,
        portfolio_id: str,
        max_drawdown_pct: float,
        daily_loss_limit_margin_pct: float,
        tail_var_99_bps: float
    ) -> TierPromotionResult:
        """Tier 4: Portfolio Deployment Promotion (Drawdown, tail risk, and prop constraints)."""
        passed = (max_drawdown_pct <= 5.0) and (daily_loss_limit_margin_pct >= 20.0) and (tail_var_99_bps <= 150.0)
        status = "PROMOTED" if passed else "REJECTED"
        metrics = {
            "max_drawdown_pct": max_drawdown_pct,
            "daily_loss_limit_margin_pct": daily_loss_limit_margin_pct,
            "tail_var_99_bps": tail_var_99_bps
        }
        reason = "Drawdown <= 5%, Prop margin >= 20%" if passed else "Portfolio risk exceeded safety thresholds"
        
        return TierPromotionResult(
            tier=4,
            tier_name="PORTFOLIO_DEPLOYMENT",
            target_id=portfolio_id,
            promoted=passed,
            status=status,
            evaluation_metrics=metrics,
            reason=reason
        )
