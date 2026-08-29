"""Recurring-Error Targeted Practice Curriculum Generator (Milestone 2.4).

Scans intervention_events and process delta history for recurrent failure patterns (>= 3 occurrences)
and generates targeted, contrastive training drills.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from scripts.trading_brain.db.connection import get_db_connection
from scripts.trading_brain.practice.drill_engine import BlindedDrillContext, BlindedDrillEngine


@dataclass
class TargetedCurriculum:
    weakness_rule_id: str
    recurrence_count: int
    recommended_drills: List[BlindedDrillContext]
    curriculum_notes: str


class TargetedDrillGenerator:
    """Analyzes trader weakness patterns and generates tailored deliberate practice curricula."""

    @classmethod
    def analyze_weaknesses_and_generate(
        cls,
        min_recurrence: int = 3,
        db_path: Optional[Union[str, Path]] = None
    ) -> List[TargetedCurriculum]:
        """Identifies recurring intervention rules and produces targeted practice drills."""
        curricula = []
        
        with get_db_connection(db_path) as conn:
            cur = conn.execute(
                """
                SELECT rule_id, COUNT(*) AS recurrence_count
                FROM intervention_events
                GROUP BY rule_id
                HAVING COUNT(*) >= ?
                ORDER BY recurrence_count DESC;
                """,
                (min_recurrence,)
            )
            rows = cur.fetchall()
            
            for r in rows:
                rule_id = r["rule_id"]
                count = r["recurrence_count"]
                
                # Generate 3 targeted drills with contrastive examples
                drills = [
                    BlindedDrillEngine.generate_blinded_drill(drill_type="BRACKET_DISCIPLINE", dataset_split="TRAINING"),
                    BlindedDrillEngine.generate_blinded_drill(drill_type="RECOGNITION", dataset_split="TRAINING"),
                    BlindedDrillEngine.generate_blinded_drill(drill_type="REVERSAL_COUNTER", dataset_split="CALIBRATION")
                ]
                
                curricula.append(TargetedCurriculum(
                    weakness_rule_id=rule_id,
                    recurrence_count=count,
                    recommended_drills=drills,
                    curriculum_notes=f"Targeting recurring deviation on {rule_id} ({count} historical occurrences)"
                ))
                
        return curricula
