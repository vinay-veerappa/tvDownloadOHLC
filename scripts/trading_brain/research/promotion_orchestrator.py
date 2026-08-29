"""Decoupled 4-Tier Promotion Orchestrator (Milestone 3.4).

Maintains 4 independent promotion tiers using append-only model_deployment_events (never mutating model_versions):
- Tier 1: Forecast Model (Calibration Brier Skill > 0, ECE <= 0.08, FDR q <= 0.05)
- Tier 2: Signal Model (Expectancy >= 2 bps, Win Rate >= 50%, FDR q <= 0.05)
- Tier 3: Execution Policy (Realized EV in R after costs >= 0.30 R, Slippage <= 2.0 bps, Cost ratio <= 25%)
- Tier 4: Portfolio Deployment (Max Drawdown <= 5.0%, Prop daily loss margin >= 20%, Tail VaR 99% <= 150 bps)

Governance rules:
* Every tier evaluation records a deployment event in the immutable ledger.
* A real model_version record must exist (or be auto-created as a placeholder) before any event is written.
* The immutable `model_versions.status` column is never updated by this orchestrator.
* Each tier can independently be 'PENDING' (insufficient evidence), 'CANDIDATE', 'CHAMPION'/'PROMOTED', or 'REJECTED'.
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
    status: str                                # 'PENDING', 'CANDIDATE', 'CHAMPION', 'PROMOTED', 'REJECTED'
    evaluation_metrics: Dict[str, Any]
    reason: str


class PromotionOrchestrator:
    """Orchestrates multi-tier governance and promotion audits."""

    # ---------------------------------------------------------------------------
    # Immutable ledger helpers
    # ---------------------------------------------------------------------------
    @classmethod
    def _ensure_model_version_record(
        cls,
        conn,
        model_version_id: str,
        model_family: str = "PROFILER_DAY_TYPE",
        version_tag: str = "1.0.0",
        parameter_hash: str = "orchestrator_placeholder",
        feature_manifest_json: str = "{}",
        calibration_metrics_json: str = "{}",
        status: str = "SHADOW",
    ) -> None:
        """Create an immutable model_version row if it does not already exist.

        The caller is responsible for opening a transaction/connection.
        """
        cur = conn.execute("SELECT 1 FROM model_versions WHERE model_version_id = ?;", (model_version_id,))
        if cur.fetchone():
            return
        conn.execute(
            """
            INSERT INTO model_versions (
                model_version_id, model_family, version_tag, parameter_hash,
                feature_manifest_json, calibration_metrics_json, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (
                model_version_id,
                model_family,
                version_tag,
                parameter_hash,
                feature_manifest_json,
                calibration_metrics_json,
                status,
            ),
        )

    @classmethod
    def _log_deployment_event(
        cls,
        conn,
        model_version_id: str,
        tier: int,
        deployment_status: str,
        metrics: Dict[str, Any],
        actor: str,
        reason: str,
    ) -> str:
        event_id = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO model_deployment_events (
                deployment_event_id, model_version_id, tier, deployment_status,
                eval_metrics_json, actor, reason, event_timestamp_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                event_id,
                model_version_id,
                tier,
                deployment_status,
                json.dumps(metrics),
                actor,
                reason,
                now_iso_utc(),
            ),
        )
        return event_id

    @classmethod
    def _latest_deployment_status(
        cls,
        conn,
        model_version_id: str,
        tier: int,
    ) -> Optional[str]:
        cur = conn.execute(
            """
            SELECT deployment_status FROM model_deployment_events
            WHERE model_version_id = ? AND tier = ?
            ORDER BY event_timestamp_utc DESC, deployment_event_id DESC
            LIMIT 1;
            """,
            (model_version_id, tier),
        )
        row = cur.fetchone()
        return row[0] if row else None

    # ---------------------------------------------------------------------------
    # Tier evaluators
    # ---------------------------------------------------------------------------
    @classmethod
    def evaluate_tier_1_forecast_model(
        cls,
        model_version_id: str,
        brier_skill_score: float,
        ece: float,
        fdr_q_value: float,
        model_family: str = "PROFILER_DAY_TYPE",
        actor: str = "ORCHESTRATOR",
        db_path: Optional[Union[str, Path]] = None
    ) -> TierPromotionResult:
        """Tier 1: Forecast Model Promotion (Calibration & Discrimination)."""
        metrics = {
            "brier_skill_score": brier_skill_score,
            "ece": ece,
            "fdr_q_value": fdr_q_value,
        }

        if not math.isfinite(brier_skill_score) or not math.isfinite(ece) or not math.isfinite(fdr_q_value):
            status = "PENDING"
            reason = "One or more tier-1 metrics are non-finite; insufficient evidence for promotion decision"
        elif (brier_skill_score > 0.0) and (ece <= 0.08) and (fdr_q_value <= 0.05):
            status = "CHAMPION"
            reason = "Passed BSS > 0, ECE <= 0.08, FDR q <= 0.05"
        else:
            status = "REJECTED"
            reason = "Failed calibration thresholds"

        with get_db_connection(db_path) as conn:
            cls._ensure_model_version_record(
                conn,
                model_version_id,
                model_family=model_family,
                calibration_metrics_json=json.dumps(metrics),
                status="SHADOW",
            )
            cls._log_deployment_event(conn, model_version_id, 1, status, metrics, actor, reason)

        return TierPromotionResult(
            tier=1,
            tier_name="FORECAST_MODEL",
            target_id=model_version_id,
            promoted=(status == "CHAMPION"),
            status=status,
            evaluation_metrics=metrics,
            reason=reason,
        )

    @classmethod
    def evaluate_tier_2_signal_model(
        cls,
        model_version_id: str,
        expectancy_bps: float,
        win_rate: float,
        fdr_q_value: float,
        model_family: str = "SIGNAL_MODEL",
        actor: str = "ORCHESTRATOR",
        db_path: Optional[Union[str, Path]] = None
    ) -> TierPromotionResult:
        """Tier 2: Signal Model Promotion (Opportunity Expectancy)."""
        metrics = {
            "expectancy_bps": expectancy_bps,
            "win_rate": win_rate,
            "fdr_q_value": fdr_q_value,
        }

        if not math.isfinite(expectancy_bps) or not math.isfinite(win_rate) or not math.isfinite(fdr_q_value):
            status = "PENDING"
            reason = "One or more tier-2 metrics are non-finite; insufficient evidence"
        elif (expectancy_bps >= 2.0) and (win_rate >= 0.50) and (fdr_q_value <= 0.05):
            status = "CHAMPION"
            reason = "Expectancy >= 2 bps, Win Rate >= 50%, FDR q <= 0.05"
        else:
            status = "REJECTED"
            reason = "Sub-threshold signal expectancy"

        with get_db_connection(db_path) as conn:
            cls._ensure_model_version_record(
                conn,
                model_version_id,
                model_family=model_family,
                calibration_metrics_json=json.dumps(metrics),
                status="SHADOW",
            )
            cls._log_deployment_event(conn, model_version_id, 2, status, metrics, actor, reason)

        return TierPromotionResult(
            tier=2,
            tier_name="SIGNAL_MODEL",
            target_id=model_version_id,
            promoted=(status == "CHAMPION"),
            status=status,
            evaluation_metrics=metrics,
            reason=reason,
        )

    @classmethod
    def evaluate_tier_3_execution_policy(
        cls,
        model_version_id: str,
        realized_ev_r: float,
        avg_slippage_bps: float,
        cost_ratio: float,
        model_family: str = "EXECUTION_POLICY",
        actor: str = "ORCHESTRATOR",
        db_path: Optional[Union[str, Path]] = None
    ) -> TierPromotionResult:
        """Tier 3: Execution Policy Promotion (Realized EV in R after costs)."""
        metrics = {
            "realized_ev_r": realized_ev_r,
            "avg_slippage_bps": avg_slippage_bps,
            "cost_ratio": cost_ratio,
        }

        if not math.isfinite(realized_ev_r) or not math.isfinite(avg_slippage_bps) or not math.isfinite(cost_ratio):
            status = "PENDING"
            reason = "One or more tier-3 metrics are non-finite; insufficient evidence"
        elif (realized_ev_r >= 0.30) and (avg_slippage_bps <= 2.0) and (cost_ratio <= 0.25):
            status = "CHAMPION"
            reason = "EV >= 0.30 R, Slippage <= 2 bps, Cost ratio <= 25%"
        else:
            status = "REJECTED"
            reason = "Execution friction degraded expectancy below threshold"

        with get_db_connection(db_path) as conn:
            cls._ensure_model_version_record(
                conn,
                model_version_id,
                model_family=model_family,
                calibration_metrics_json=json.dumps(metrics),
                status="SHADOW",
            )
            cls._log_deployment_event(conn, model_version_id, 3, status, metrics, actor, reason)

        return TierPromotionResult(
            tier=3,
            tier_name="EXECUTION_POLICY",
            target_id=model_version_id,
            promoted=(status == "CHAMPION"),
            status=status,
            evaluation_metrics=metrics,
            reason=reason,
        )

    @classmethod
    def evaluate_tier_4_portfolio_deployment(
        cls,
        model_version_id: str,
        max_drawdown_pct: float,
        daily_loss_limit_margin_pct: float,
        tail_var_99_bps: float,
        model_family: str = "PORTFOLIO_ALLOCATION",
        actor: str = "ORCHESTRATOR",
        db_path: Optional[Union[str, Path]] = None
    ) -> TierPromotionResult:
        """Tier 4: Portfolio Deployment Promotion (Drawdown, tail risk, and prop constraints)."""
        metrics = {
            "max_drawdown_pct": max_drawdown_pct,
            "daily_loss_limit_margin_pct": daily_loss_limit_margin_pct,
            "tail_var_99_bps": tail_var_99_bps,
        }

        if not math.isfinite(max_drawdown_pct) or not math.isfinite(daily_loss_limit_margin_pct) or not math.isfinite(tail_var_99_bps):
            status = "PENDING"
            reason = "One or more tier-4 metrics are non-finite; insufficient evidence"
        elif (max_drawdown_pct <= 5.0) and (daily_loss_limit_margin_pct >= 20.0) and (tail_var_99_bps <= 150.0):
            status = "CHAMPION"
            reason = "Drawdown <= 5%, Prop margin >= 20%, Tail VaR 99% <= 150 bps"
        else:
            status = "REJECTED"
            reason = "Portfolio risk exceeded safety thresholds"

        with get_db_connection(db_path) as conn:
            cls._ensure_model_version_record(
                conn,
                model_version_id,
                model_family=model_family,
                calibration_metrics_json=json.dumps(metrics),
                status="SHADOW",
            )
            cls._log_deployment_event(conn, model_version_id, 4, status, metrics, actor, reason)

        return TierPromotionResult(
            tier=4,
            tier_name="PORTFOLIO_DEPLOYMENT",
            target_id=model_version_id,
            promoted=(status == "CHAMPION"),
            status=status,
            evaluation_metrics=metrics,
            reason=reason,
        )

    # ---------------------------------------------------------------------------
    # Aggregate governance helpers
    # ---------------------------------------------------------------------------
    @classmethod
    def evaluate_all_tiers(
        cls,
        model_version_id: str,
        tier_inputs: List[Dict[str, Any]],
        actor: str = "ORCHESTRATOR",
        db_path: Optional[Union[str, Path]] = None
    ) -> List[TierPromotionResult]:
        """Evaluate a sequence of tier requests for a single model_version_id.

        `tier_inputs` is a list of dicts with keys:
            tier (int), and tier-specific metric keys.
        Example:
            [
                {"tier": 1, "brier_skill_score": 0.05, "ece": 0.04, "fdr_q_value": 0.03},
                {"tier": 2, "expectancy_bps": 3.0, "win_rate": 0.55, "fdr_q_value": 0.04},
                {"tier": 3, "realized_ev_r": 0.35, "avg_slippage_bps": 1.5, "cost_ratio": 0.20},
                {"tier": 4, "max_drawdown_pct": 4.0, "daily_loss_limit_margin_pct": 25.0, "tail_var_99_bps": 120.0},
            ]
        """
        dispatch = {
            1: cls.evaluate_tier_1_forecast_model,
            2: cls.evaluate_tier_2_signal_model,
            3: cls.evaluate_tier_3_execution_policy,
            4: cls.evaluate_tier_4_portfolio_deployment,
        }
        results = []
        for payload in tier_inputs:
            tier = int(payload["tier"])
            func = dispatch[tier]
            kwargs = dict(payload)
            kwargs.pop("tier", None)
            kwargs["model_version_id"] = model_version_id
            kwargs["actor"] = actor
            kwargs["db_path"] = db_path
            results.append(func(**kwargs))
        return results

    @classmethod
    def get_current_tier_status(
        cls,
        model_version_id: str,
        db_path: Optional[Union[str, Path]] = None
    ) -> Dict[int, Optional[str]]:
        """Return the latest deployment_status per tier for a model_version_id."""
        with get_db_connection(db_path) as conn:
            cur = conn.execute(
                """
                SELECT tier, deployment_status FROM (
                    SELECT tier, deployment_status,
                        ROW_NUMBER() OVER (PARTITION BY tier ORDER BY event_timestamp_utc DESC, deployment_event_id DESC) AS rn
                    FROM model_deployment_events
                    WHERE model_version_id = ?
                ) WHERE rn = 1;
                """,
                (model_version_id,),
            )
            return {row[0]: row[1] for row in cur.fetchall()}


import math  # noqa: E402