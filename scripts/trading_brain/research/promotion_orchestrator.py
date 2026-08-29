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
import math
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
    def _require_model_version_record(
        cls,
        conn,
        model_version_id: str,
        tier: int,
        shadow_finding_id: Optional[str] = None,
        expected_holdout_hash: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fails closed unless the model record pre-exists AND the shadow gate cleared it.

        The orchestrator NEVER fabricates model records: a registry row created by the
        orchestrator itself with placeholder parameters would be an auditable-forgery
        magnet. Any promotion additionally requires a linked PROMOTED candidate_finding_events
        event produced by the shadow gate, with a matching holdout hash when supplied.
        """
        cur = conn.execute("SELECT * FROM model_versions WHERE model_version_id = ?;", (model_version_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError(
                f"model_version '{model_version_id}' does not exist in the immutable registry. "
                "Promotion requires a pre-existing model record; the orchestrator refuses to "
                "create placeholder records (audit-forgery prevention)."
            )

        prereq: Dict[str, Any] = {
            "model_record_exists": True,
            "parameter_hash": row["parameter_hash"],
        }

        if shadow_finding_id:
            ev = conn.execute(
                """
                SELECT * FROM candidate_finding_events
                WHERE finding_id = ? AND model_version_id = ? AND pipeline_stage = 'PROMOTED'
                ORDER BY event_timestamp_utc DESC LIMIT 1;
                """,
                (shadow_finding_id, model_version_id),
            ).fetchone()
            if not ev:
                raise ValueError(
                    f"Tier {tier} promotion requires a completed PROMOTED shadow-gate event for "
                    f"finding '{shadow_finding_id}' on model '{model_version_id}'."
                )
            prereq["shadow_event_id"] = ev["finding_event_id"]
            prereq["shadow_stage"] = "PROMOTED"
            if expected_holdout_hash:
                eval_blob = json.loads(ev["evaluation_result_json"] or "{}")
                holdout_hash = eval_blob.get("holdout_hash")
                if holdout_hash and expected_holdout_hash and holdout_hash != expected_holdout_hash:
                    raise ValueError(
                        "Holdout hash mismatch between preregistration and shadow result: "
                        f"{expected_holdout_hash} != {holdout_hash}"
                    )
                prereq["holdout_hash"] = holdout_hash
        else:
            raise ValueError(
                f"Tier {tier} promotion requires shadow_finding_id linking a completed "
                "shadow-gate PROMOTED event (verified-evidence chain requirement)."
            )

        return prereq

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
        prereq: Optional[Dict[str, Any]] = None,
    ) -> str:
        event_id = str(uuid.uuid4())
        payload = dict(metrics)
        if prereq:
            payload["prerequisite_chain"] = prereq
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
                json.dumps(payload),
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
        shadow_finding_id: str,
        expected_holdout_hash: Optional[str] = None,
        actor: str = "ORCHESTRATOR",
        db_path: Optional[Union[str, Path]] = None
    ) -> TierPromotionResult:
        """Tier 1: Forecast Model Promotion (Calibration & Discrimination).

        Evidence chain required: pre-existing immutable model record + PROMOTED shadow-gate
        event for this model with matching holdout hash. Raw caller metrics alone never
        promote.
        """
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
            reason = "Passed BSS > 0, ECE <= 0.08, FDR q <= 0.05 with verified shadow evidence"
        else:
            status = "REJECTED"
            reason = "Failed calibration thresholds"

        with get_db_connection(db_path) as conn:
            if status == "CHAMPION":
                prereq = cls._require_model_version_record(
                    conn, model_version_id, 1,
                    shadow_finding_id=shadow_finding_id,
                    expected_holdout_hash=expected_holdout_hash,
                )
            else:
                cur = conn.execute("SELECT 1 FROM model_versions WHERE model_version_id = ?;", (model_version_id,))
                if not cur.fetchone():
                    raise ValueError(
                        f"model_version '{model_version_id}' does not exist; the orchestrator "
                        "refuses to create placeholder records."
                    )
                prereq = {"model_record_exists": True}
            cls._log_deployment_event(conn, model_version_id, 1, status, metrics, actor, reason, prereq=prereq)

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
        shadow_finding_id: str,
        expected_holdout_hash: Optional[str] = None,
        actor: str = "ORCHESTRATOR",
        db_path: Optional[Union[str, Path]] = None
    ) -> TierPromotionResult:
        """Tier 2: Signal Model Promotion (Opportunity Expectancy). Verified evidence chain required."""
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
            reason = "Expectancy >= 2 bps, Win Rate >= 50%, FDR q <= 0.05 with verified shadow evidence"
        else:
            status = "REJECTED"
            reason = "Sub-threshold signal expectancy"

        with get_db_connection(db_path) as conn:
            if status == "CHAMPION":
                prereq = cls._require_model_version_record(
                    conn, model_version_id, 2,
                    shadow_finding_id=shadow_finding_id,
                    expected_holdout_hash=expected_holdout_hash,
                )
            else:
                cur = conn.execute("SELECT 1 FROM model_versions WHERE model_version_id = ?;", (model_version_id,))
                if not cur.fetchone():
                    raise ValueError(
                        f"model_version '{model_version_id}' does not exist; the orchestrator "
                        "refuses to create placeholder records."
                    )
                prereq = {"model_record_exists": True}
            cls._log_deployment_event(conn, model_version_id, 2, status, metrics, actor, reason, prereq=prereq)

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
        shadow_finding_id: str,
        expected_holdout_hash: Optional[str] = None,
        actor: str = "ORCHESTRATOR",
        db_path: Optional[Union[str, Path]] = None
    ) -> TierPromotionResult:
        """Tier 3: Execution Policy Promotion (Realized EV in R after costs). Verified evidence chain required."""
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
            reason = "EV >= 0.30 R, Slippage <= 2 bps, Cost ratio <= 25% with verified shadow evidence"
        else:
            status = "REJECTED"
            reason = "Execution friction degraded expectancy below threshold"

        with get_db_connection(db_path) as conn:
            if status == "CHAMPION":
                prereq = cls._require_model_version_record(
                    conn, model_version_id, 3,
                    shadow_finding_id=shadow_finding_id,
                    expected_holdout_hash=expected_holdout_hash,
                )
            else:
                cur = conn.execute("SELECT 1 FROM model_versions WHERE model_version_id = ?;", (model_version_id,))
                if not cur.fetchone():
                    raise ValueError(
                        f"model_version '{model_version_id}' does not exist; the orchestrator "
                        "refuses to create placeholder records."
                    )
                prereq = {"model_record_exists": True}
            cls._log_deployment_event(conn, model_version_id, 3, status, metrics, actor, reason, prereq=prereq)

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
        shadow_finding_id: str,
        expected_holdout_hash: Optional[str] = None,
        actor: str = "ORCHESTRATOR",
        db_path: Optional[Union[str, Path]] = None
    ) -> TierPromotionResult:
        """Tier 4: Portfolio Deployment Promotion (Drawdown, tail risk, and prop constraints). Verified evidence chain required."""
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
            reason = "Drawdown <= 5%, Prop margin >= 20%, Tail VaR 99% <= 150 bps with verified shadow evidence"
        else:
            status = "REJECTED"
            reason = "Portfolio risk exceeded safety thresholds"

        with get_db_connection(db_path) as conn:
            if status == "CHAMPION":
                prereq = cls._require_model_version_record(
                    conn, model_version_id, 4,
                    shadow_finding_id=shadow_finding_id,
                    expected_holdout_hash=expected_holdout_hash,
                )
            else:
                cur = conn.execute("SELECT 1 FROM model_versions WHERE model_version_id = ?;", (model_version_id,))
                if not cur.fetchone():
                    raise ValueError(
                        f"model_version '{model_version_id}' does not exist; the orchestrator "
                        "refuses to create placeholder records."
                    )
                prereq = {"model_record_exists": True}
            cls._log_deployment_event(conn, model_version_id, 4, status, metrics, actor, reason, prereq=prereq)

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
            tier (int), tier-specific metric keys, and shadow_finding_id linking a
            completed PROMOTED shadow-gate event (required for any CHAMPION outcome).
        Example:
            [
                {"tier": 1, "brier_skill_score": 0.05, "ece": 0.04, "fdr_q_value": 0.03,
                 "shadow_finding_id": "SF-1"},
                ...
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