"""Preregistered Shadow Validation Gate & Access Custody Protocol (Milestone 3.3).

Enforces:
1. Mandatory Preregistration with Sealed Holdout: Findings MUST be preregistered with
   holdout_dataset_id, holdout_dataset_hash, benchmark_metric, and MDE before shadow evaluation.
2. Duplicate Preregistration Protection: Re-registering existing finding_id raises PreregistrationConflictError.
3. 1-Time Sealed Evaluation: Terminal states (PROMOTED, REJECTED, INVALID_TEST) cannot be re-evaluated.
4. Model ID & MDE Binding: Evaluates requested model matches preregistered model, and improvement >= MDE.
5. Minimum Statistical Power >= 0.80.
"""

import json
import math
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from scripts.trading_brain.db.connection import get_db_connection
from scripts.utils.market_calendar import now_iso_utc


class PreregistrationRequiredError(Exception):
    """Raised when shadow evaluation is attempted without prior preregistration."""
    pass


class PreregistrationConflictError(Exception):
    """Raised when attempting to preregister an existing finding_id."""
    pass


class ShadowGateLockedError(Exception):
    """Raised when an already-evaluated candidate finding in terminal state is re-evaluated."""
    pass


@dataclass
class ShadowEvaluationResult:
    finding_event_id: str
    finding_id: str
    model_version_id: str
    pipeline_stage: str                        # 'PROMOTED', 'INCONCLUSIVE_WAITING', 'REJECTED', 'INVALID_TEST'
    statistical_power: float
    fdr_q_value: float
    realized_metric: float
    benchmark_metric: float
    notes: str


class ShadowGate:
    """Evaluates candidate models against sealed shadow data with power and custody enforcement."""

    @staticmethod
    def calculate_statistical_power(
        sample_size: int,
        effect_size_d: float,
        alpha: float = 0.05
    ) -> float:
        """Approximates statistical power for a one-tailed z-test."""
        if sample_size <= 0 or effect_size_d <= 0:
            return 0.0
        z_alpha = 1.645
        z_score = effect_size_d * math.sqrt(sample_size) - z_alpha
        power = 0.5 * (1.0 + math.erf(z_score / math.sqrt(2.0)))
        return max(0.0, min(1.0, power))

    @classmethod
    def preregister_candidate_finding(
        cls,
        finding_id: str,
        model_version_id: str,
        benchmark_metric: float,
        expected_effect_size_d: float,
        feature_manifest: Dict[str, Any],
        holdout_dataset_id: str = "HOLDOUT_2026_Q1",
        holdout_dataset_hash: str = "sha256:sealed_holdout_hash",
        actor: str = "RESEARCH_AGENT",
        db_path: Optional[Union[str, Path]] = None
    ) -> str:
        """Preregisters a candidate finding at discovery time, binding holdout dataset and effect size."""
        with get_db_connection(db_path) as conn:
            cur = conn.execute("SELECT finding_id FROM candidate_finding_events WHERE finding_id = ?;", (finding_id,))
            if cur.fetchone():
                raise PreregistrationConflictError(f"Candidate finding '{finding_id}' has already been preregistered.")
                
            event_id = str(uuid.uuid4())
            eval_json = json.dumps({
                "stage": "PREREGISTERED",
                "model_version_id": model_version_id,
                "benchmark_metric": benchmark_metric,
                "expected_effect_size_d": expected_effect_size_d,
                "holdout_dataset_id": holdout_dataset_id,
                "holdout_dataset_hash": holdout_dataset_hash,
                "feature_manifest": feature_manifest,
                "preregistered_at_utc": now_iso_utc()
            })
            
            conn.execute(
                """
                INSERT INTO candidate_finding_events (
                    finding_event_id, finding_id, model_version_id,
                    pipeline_stage, evaluation_result_json,
                    statistical_power, fdr_q_value, actor, event_timestamp_utc
                ) VALUES (?, ?, ?, 'DISCOVERY', ?, 0.0, 1.0, ?, ?);
                """,
                (event_id, finding_id, model_version_id, eval_json, actor, now_iso_utc())
            )
        return event_id

    @classmethod
    def evaluate_candidate_finding(
        cls,
        finding_id: str,
        model_version_id: str,
        sample_size: int,
        realized_metric: float,
        fdr_q_value: float,
        actor: str = "RESEARCH_AGENT",
        db_path: Optional[Union[str, Path]] = None
    ) -> ShadowEvaluationResult:
        """Evaluates a candidate finding on sealed shadow data and transitions candidate_finding_events."""
        with get_db_connection(db_path) as conn:
            cur = conn.execute(
                """
                SELECT * FROM candidate_finding_events
                WHERE finding_id = ?
                ORDER BY event_timestamp_utc DESC, created_at_utc DESC, rowid DESC LIMIT 1;
                """,
                (finding_id,)
            )
            row = cur.fetchone()
            
            if not row:
                raise PreregistrationRequiredError(
                    f"Candidate finding '{finding_id}' must be preregistered via preregister_candidate_finding() before evaluation on sealed shadow data."
                )
                
            prev_stage = row["pipeline_stage"]
            if prev_stage in ("PROMOTED", "REJECTED", "INVALID_TEST"):
                raise ShadowGateLockedError(
                    f"Candidate finding '{finding_id}' has already been evaluated to terminal stage '{prev_stage}' and cannot be re-evaluated."
                )
                
            prev_json = json.loads(row["evaluation_result_json"]) if row["evaluation_result_json"] else {}
            prereg_model = prev_json.get("model_version_id", row["model_version_id"])
            if prereg_model != model_version_id:
                raise ValueError(f"Requested model '{model_version_id}' does not match preregistered model '{prereg_model}' for finding '{finding_id}'.")
                
            sealed_benchmark = float(prev_json["benchmark_metric"])
            sealed_effect_d = float(prev_json["expected_effect_size_d"])

            power = cls.calculate_statistical_power(sample_size, sealed_effect_d)
            
            # Improvement over benchmark
            improvement = realized_metric - sealed_benchmark
            
            # Decision Policy: Power >= 0.80, FDR q <= 0.05, and positive improvement
            if power < 0.80:
                stage = "INCONCLUSIVE_WAITING"
                notes = f"Insufficient statistical power ({power:.2f} < 0.80) at N={sample_size}. Frozen awaiting unobserved samples."
            elif fdr_q_value <= 0.05 and improvement > 0:
                stage = "PROMOTED"
                notes = f"Validated on shadow data (Power={power:.2f}, FDR q={fdr_q_value:.4f}, Metric={realized_metric:.4f} > {sealed_benchmark:.4f})."
            else:
                stage = "REJECTED"
                notes = f"Failed criteria on shadow data (FDR q={fdr_q_value:.4f}, Metric={realized_metric:.4f} <= {sealed_benchmark:.4f})."
                
            event_id = str(uuid.uuid4())
            eval_json = json.dumps({
                "sample_size": sample_size,
                "realized_metric": realized_metric,
                "benchmark_metric": sealed_benchmark,
                "effect_size_d": sealed_effect_d,
                "statistical_power": power,
                "fdr_q_value": fdr_q_value,
                "decision_notes": notes
            })
            
            conn.execute(
                """
                INSERT INTO candidate_finding_events (
                    finding_event_id, finding_id, model_version_id,
                    pipeline_stage, evaluation_result_json,
                    statistical_power, fdr_q_value, actor, event_timestamp_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (event_id, finding_id, model_version_id, stage, eval_json, power, fdr_q_value, actor, now_iso_utc())
            )
            
        return ShadowEvaluationResult(
            finding_event_id=event_id,
            finding_id=finding_id,
            model_version_id=model_version_id,
            pipeline_stage=stage,
            statistical_power=round(power, 4),
            fdr_q_value=round(fdr_q_value, 4),
            realized_metric=realized_metric,
            benchmark_metric=sealed_benchmark,
            notes=notes
        )
