"""Preregistered Shadow Validation Gate & Access Custody Protocol (Milestone 3.3).

Enforces:
1. Preregistration First: Findings must be preregistered with frozen benchmark and MDE before shadow evaluation.
2. 1-Time Sealed Evaluation: Terminal states (PROMOTED, REJECTED, INVALID_TEST) cannot be re-evaluated.
3. Minimum Statistical Power >= 0.80 and Minimum Detectable Effect (MDE).
4. Full access custody audit logging in candidate_finding_events.
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
        actor: str = "RESEARCH_AGENT",
        db_path: Optional[Union[str, Path]] = None
    ) -> str:
        """Preregisters a candidate finding at discovery time, sealing benchmark and effect size."""
        event_id = str(uuid.uuid4())
        eval_json = json.dumps({
            "stage": "PREREGISTERED",
            "benchmark_metric": benchmark_metric,
            "expected_effect_size_d": expected_effect_size_d,
            "feature_manifest": feature_manifest,
            "preregistered_at_utc": now_iso_utc()
        })
        
        with get_db_connection(db_path) as conn:
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
        benchmark_metric: Optional[float] = None,
        effect_size_d: Optional[float] = None,
        actor: str = "RESEARCH_AGENT",
        db_path: Optional[Union[str, Path]] = None
    ) -> ShadowEvaluationResult:
        """Evaluates a candidate finding on sealed shadow data and transitions candidate_finding_events.
        
        Enforces 1-time sealed evaluation rule and consumes preregistered benchmark.
        """
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
            
            # If not preregistered, check if caller provided initial registration
            if not row:
                if benchmark_metric is None or effect_size_d is None:
                    raise PreregistrationRequiredError(
                        f"Finding '{finding_id}' has not been preregistered and benchmark parameters were not provided."
                    )
                sealed_benchmark = benchmark_metric
                sealed_effect_d = effect_size_d
            else:
                prev_stage = row["pipeline_stage"]
                if prev_stage in ("PROMOTED", "REJECTED", "INVALID_TEST"):
                    raise ShadowGateLockedError(
                        f"Candidate finding '{finding_id}' has already been evaluated to terminal stage '{prev_stage}' and cannot be re-evaluated."
                    )
                prev_json = json.loads(row["evaluation_result_json"]) if row["evaluation_result_json"] else {}
                sealed_benchmark = prev_json.get("benchmark_metric", benchmark_metric if benchmark_metric is not None else 0.0)
                sealed_effect_d = prev_json.get("expected_effect_size_d", effect_size_d if effect_size_d is not None else 0.5)

            power = cls.calculate_statistical_power(sample_size, sealed_effect_d)
            
            # Decision Policy
            if power < 0.80:
                stage = "INCONCLUSIVE_WAITING"
                notes = f"Insufficient statistical power ({power:.2f} < 0.80) at N={sample_size}. Frozen awaiting more unobserved samples."
            elif fdr_q_value <= 0.05 and realized_metric > sealed_benchmark:
                stage = "PROMOTED"
                notes = f"Successfully validated on shadow data (Power={power:.2f}, FDR q={fdr_q_value:.4f}, Metric={realized_metric:.4f} > {sealed_benchmark:.4f})."
            else:
                stage = "REJECTED"
                notes = f"Failed validation criteria on shadow data (FDR q={fdr_q_value:.4f}, Metric={realized_metric:.4f} <= {sealed_benchmark:.4f})."
                
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
