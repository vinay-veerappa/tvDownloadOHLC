"""Recurring-Error Targeted Practice Curriculum Generator (Milestone 2.4)."""

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from scripts.trading_brain.db.connection import get_db_connection
from scripts.trading_brain.practice.drill_engine import BlindedDrillContext, BlindedDrillEngine


@dataclass
class CurriculumSummary:
    curriculum_id: str
    weakness_rule_id: str
    recurrence_count: int
    recommended_drills: List[BlindedDrillContext]
    curriculum_notes: str


class TargetedDrillGenerator:
    """Generates targeted deliberate practice drills based on verified recurring weaknesses."""

    @classmethod
    def analyze_weaknesses_and_generate(
        cls,
        min_recurrence: int = 3,
        ticker: str = "NQ1",
        db_path: Optional[Union[str, Path]] = None
    ) -> List[CurriculumSummary]:
        """Identifies recurring intervention rules occurring >= min_recurrence times and creates a drill set."""
        with get_db_connection(db_path) as conn:
            cur = conn.execute(
                """
                SELECT rule_id, COUNT(*) AS recurrence_count
                FROM intervention_events
                GROUP BY rule_id
                HAVING recurrence_count >= ?
                ORDER BY recurrence_count DESC;
                """,
                (min_recurrence,)
            )
            rows = cur.fetchall()
            if not rows:
                return []
                
            curricula = []
            for row in rows:
                rule_id = row["rule_id"]
                count = row["recurrence_count"]
                
                drills = []
                for _ in range(3):
                    drill = BlindedDrillEngine.generate_blinded_drill(
                        drill_type="RECOGNITION",
                        dataset_split="TRAINING",
                        session_date="2026-08-28",
                        ticker=ticker,
                        synthetic_mode=True
                    )
                    drills.append(drill)
                    
                curricula.append(CurriculumSummary(
                    curriculum_id=str(uuid.uuid4()),
                    weakness_rule_id=rule_id,
                    recurrence_count=count,
                    recommended_drills=drills,
                    curriculum_notes=f"Targeted curriculum addressing recurring deviation '{rule_id}' ({count} occurrences)."
                ))
            return curricula
