"""Post-Submission Deviation Annotator & Compliance Engine (Milestone 2.1).

Consumes execution fills post-submission, evaluates them against get_plan_as_of, and logs
OBSERVED_DEVIATION_ANNOTATION events in intervention_events when execution deviates from plan.
"""

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from scripts.trading_brain.db.connection import get_db_connection
from scripts.trading_brain.plans.plan_adapter import PlanAdapter
from scripts.utils.market_calendar import now_iso_utc, parse_iso_utc, to_iso_utc


@dataclass
class DeviationFinding:
    rule_id: str
    authority_class: str                      # 'OBSERVED_DEVIATION_ANNOTATION'
    action_mode: str                          # 'ACTING'
    observed_value: float
    threshold_value: float
    description: str


class DeviationAnnotator:
    """Evaluates broker executions against pre-market plan contracts and records deviations."""

    @classmethod
    def evaluate_execution(
        cls,
        execution: Dict[str, Any],
        db_path: Optional[Union[str, Path]] = None
    ) -> List[str]:
        """Evaluates a single execution event and persists any detected deviation annotations."""
        session_date = execution["session_date"]
        ticker = execution["ticker"]
        event_ts = execution["event_timestamp_utc"]
        action = execution["order_action"].upper()
        fill_price = float(execution["fill_price"])
        strat_id = execution.get("strategy_version_id")
        account_id = execution.get("account_id", "PRIMARY")
        exec_id = execution.get("execution_id") or str(uuid.uuid4())
        
        plan_ctx = PlanAdapter.get_plan_as_of(session_date, ticker, event_ts, db_path=db_path)
        if not plan_ctx:
            # Fallback to query post-hoc plan
            with get_db_connection(db_path) as conn:
                cur = conn.execute(
                    "SELECT * FROM plan_snapshots WHERE session_date = ? AND ticker = ? ORDER BY revision_seq DESC LIMIT 1;",
                    (session_date, ticker)
                )
                row = cur.fetchone()
                if row:
                    strats = json.loads(row["permitted_strategies_json"]) if row["permitted_strategies_json"] else []
                    plan_bias = row["primary_bias"]
                    max_risk = row["max_intended_risk_bps"]
                    snapshot_id = row["plan_snapshot_id"]
                else:
                    plan_bias = "NEUTRAL"
                    max_risk = 15.0
                    strats = []
                    snapshot_id = None
        else:
            plan_bias = plan_ctx.primary_bias
            max_risk = plan_ctx.max_intended_risk_bps
            strats = plan_ctx.permitted_strategies
            snapshot_id = plan_ctx.plan_snapshot_id

        findings: List[DeviationFinding] = []
        
        # 1. Plan Bias Violation (e.g. Buying when plan is strictly BEARISH)
        if plan_bias == "BEARISH" and action in ("BUY", "LONG"):
            findings.append(DeviationFinding(
                rule_id="PLAN_BIAS_DIRECTION_DEVIATION",
                authority_class="OBSERVED_DEVIATION_ANNOTATION",
                action_mode="ACTING",
                observed_value=1.0,
                threshold_value=0.0,
                description=f"Long order executed contrary to declared BEARISH plan bias"
            ))
        elif plan_bias == "BULLISH" and action in ("SELL", "SELL_SHORT", "SHORT"):
            findings.append(DeviationFinding(
                rule_id="PLAN_BIAS_DIRECTION_DEVIATION",
                authority_class="OBSERVED_DEVIATION_ANNOTATION",
                action_mode="ACTING",
                observed_value=1.0,
                threshold_value=0.0,
                description=f"Short order executed contrary to declared BULLISH plan bias"
            ))
            
        # 2. Unpermitted Strategy Violation
        if strats and strat_id and strat_id not in strats:
            findings.append(DeviationFinding(
                rule_id="UNPERMITTED_STRATEGY_DEVIATION",
                authority_class="OBSERVED_DEVIATION_ANNOTATION",
                action_mode="ACTING",
                observed_value=1.0,
                threshold_value=0.0,
                description=f"Strategy '{strat_id}' executed but not in permitted strategies list {strats}"
            ))
            
        # Record findings into intervention_events
        annotation_ids = []
        with get_db_connection(db_path) as conn:
            for f in findings:
                ann_id = str(uuid.uuid4())
                idemp_key = f"dev_{exec_id}_{f.rule_id}"
                
                # Check for existing
                cur = conn.execute(
                    "SELECT intervention_id FROM intervention_events WHERE producer = 'PYTHON_DEVIATION_ANNOTATOR' AND idempotency_key = ?;",
                    (idemp_key,)
                )
                if cur.fetchone():
                    continue
                    
                conn.execute(
                    """
                    INSERT INTO intervention_events (
                        intervention_id, session_date, ticker, account_id,
                        source_event_id, plan_snapshot_id, strategy_version_id,
                        producer, producer_version, authority_class, action_mode,
                        rule_id, rule_version, observed_value, threshold_value,
                        enforced, idempotency_key, event_timestamp_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'PYTHON_DEVIATION_ANNOTATOR', '1.0.0', ?, ?, ?, '1.0.0', ?, ?, 0, ?, ?);
                    """,
                    (
                        ann_id, session_date, ticker, account_id,
                        exec_id, snapshot_id, strat_id,
                        f.authority_class, f.action_mode, f.rule_id,
                        f.observed_value, f.threshold_value,
                        idemp_key, to_iso_utc(event_ts)
                    )
                )
                annotation_ids.append(ann_id)
                
        return annotation_ids
