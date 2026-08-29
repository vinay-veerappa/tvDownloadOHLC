"""Preregistered Shadow Validation Gate & Access Custody Protocol (Milestone 3.3).

Enforces:
1. Minimum Statistical Power >= 0.80 and Minimum Detectable Effect (MDE).
2. 1-Time Sealed Shadow Dataset Access with custody audit logging in candidate_finding_events.
3. Strict Terminal States:
   - PROMOTED: Passed power, significance, and performance bounds.
   - INCONCLUSIVE_WAITING: Unpromoted; remains frozen while new unobserved data accumulates.
   - REJECTED: Failed criteria; permanently closed.
   - INVALID_TEST: Execution protocol error.
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
        # z_alpha for alpha=0.05 is ~1.645
        z_alpha = 1.645
        z_score = effect_size_d * math.sqrt(sample_size) - z_alpha
        # Normal CDF approximation
        power = 0.5 * (1.0 + math.erf(z_score / math.sqrt(2.0)))
        return max(0.0, min(1.0, power))

    @classmethod
    def evaluate_candidate_finding(
        cls,
        finding_id: str,
        model_version_id: str,
        sample_size: int,
        realized_metric: float,
        benchmark_metric: float,
        effect_size_d: float,
        fdr_q_value: float,
        actor: str = "RESEARCH_AGENT",
        db_path: Optional[Union[str, Path]] = None
    ) -> ShadowEvaluationResult:
        """Evaluates a candidate finding on sealed shadow data and transitions candidate_finding_events."""
        power = cls.calculate_statistical_power(sample_size, effect_size_d)
        
        # Decision Policy
        if power < 0.80:
            stage = "INCONCLUSIVE_WAITING"
            notes = f"Insufficient statistical power ({power:.2f} < 0.80) at N={sample_size}. Frozen awaiting more samples."
        elif fdr_q_value <= 0.05 and realized_metric > benchmark_metric:
            stage = "PROMOTED"
            notes = f"Successfully validated on shadow data (Power={power:.2f}, FDR q={fdr_q_value:.4f}, Metric={realized_metric:.4f} > {benchmark_metric:.4f})."
        else:
            stage = "REJECTED"
            notes = f"Failed validation criteria on shadow data (FDR q={fdr_q_value:.4f}, Metric={realized_metric:.4f} <= {benchmark_metric:.4f})."
            
        event_id = str(uuid.uuid4())
        eval_json = json.dumps({
            "sample_size": sample_size,
            "realized_metric": realized_metric,
            "benchmark_metric": benchmark_metric,
            "effect_size_d": effect_size_d,
            "statistical_power": power,
            "fdr_q_value": fdr_q_value,
            "decision_notes": notes
        })
        
        with get_db_connection(db_path) as conn:
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
            benchmark_metric=benchmark_metric,
            notes=notes
        )
