"""Post-Submission Deviation Annotator & Compliance Engine (Milestone 2.1).

Consumes execution fills post-submission, evaluates them against effective get_plan_as_of, and logs
OBSERVED_DEVIATION_ANNOTATION events in intervention_events when execution deviates from plan.

Key Invariants:
1. Position Reduction Awareness: An exit order (e.g. SELL reducing long position) is NEVER a contrary bias violation.
2. Effective Plan Resolution: Assesses against plan after applying active amendments up to execution time.
3. No Hindsight Plans: If no contemporaneous ex-ante plan existed at execution time, records UNASSESSABLE_NO_EX_ANTE_PLAN.
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
        current_net_position_before_fill: int = 0,
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
        qty = int(execution.get("quantity", 1))
        
        # Position reduction check (exits are not directional entries) - QUANTITY-AWARE.
        # A fill larger than the open position FLIPS: only min(qty, |pos|) contracts are
        # a reduction; the excess opens a NEW opposite-direction position and is treated
        # as a directional ENTRY for bias/NO_TRADE purposes. Selling 2 while long 1 is
        # one reduction + one short entry, never a pure exit.
        entry_direction = None          # effective direction of any NEW position opened
        if current_net_position_before_fill == 0:
            is_exit_or_reduction = False
            entry_direction = "LONG" if action in ("BUY", "LONG") else "SHORT"
        elif action in ("SELL", "SELL_SHORT", "SHORT") and current_net_position_before_fill > 0:
            reducing_qty = min(qty, current_net_position_before_fill)
            excess_qty = qty - reducing_qty
            is_exit_or_reduction = excess_qty == 0
            if excess_qty > 0:
                entry_direction = "SHORT"
        elif action in ("BUY", "LONG") and current_net_position_before_fill < 0:
            reducing_qty = min(qty, abs(current_net_position_before_fill))
            excess_qty = qty - reducing_qty
            is_exit_or_reduction = excess_qty == 0
            if excess_qty > 0:
                entry_direction = "LONG"
        else:
            # Same-direction add to an existing position: fully an entry.
            is_exit_or_reduction = False
            entry_direction = "LONG" if action in ("BUY", "LONG") else "SHORT"

        plan_ctx = PlanAdapter.get_plan_as_of(session_date, ticker, event_ts, db_path=db_path)
        findings: List[DeviationFinding] = []
        
        if not plan_ctx:
            # Missing contemporaneous ex-ante plan
            findings.append(DeviationFinding(
                rule_id="UNASSESSABLE_NO_EX_ANTE_PLAN",
                authority_class="OBSERVED_DEVIATION_ANNOTATION",
                action_mode="ACTING",
                observed_value=1.0,
                threshold_value=0.0,
                description="Execution occurred without a valid contemporaneous ex-ante plan"
            ))
            snapshot_id = None
        else:
            plan_bias = plan_ctx.effective_primary_bias
            max_risk = plan_ctx.effective_max_intended_risk_bps
            strats = plan_ctx.effective_permitted_strategies
            snapshot_id = plan_ctx.plan_snapshot_id

            # 1. Plan Bias Violation (Only for directional entry / increasing position)
            # The EXCESS over the reducing quantity is an entry in `entry_direction`.
            if entry_direction == "SHORT":
                if plan_bias == "BULLISH":
                    findings.append(DeviationFinding(
                        rule_id="PLAN_BIAS_DIRECTION_DEVIATION",
                        authority_class="OBSERVED_DEVIATION_ANNOTATION",
                        action_mode="ACTING",
                        observed_value=1.0,
                        threshold_value=0.0,
                        description="Short ENTRY executed contrary to declared BULLISH effective plan bias "
                                    "(position-flip: only the reducing quantity is exempt)"
                    ))
                elif plan_bias == "NO_TRADE":
                    findings.append(DeviationFinding(
                        rule_id="NO_TRADE_PLAN_DEVIATION",
                        authority_class="OBSERVED_DEVIATION_ANNOTATION",
                        action_mode="ACTING",
                        observed_value=1.0,
                        threshold_value=0.0,
                        description="Short ENTRY executed contrary to declared NO_TRADE plan bias "
                                    "(position-flip: only the reducing quantity is exempt)"
                    ))
            elif entry_direction == "LONG":
                if plan_bias == "BEARISH":
                    findings.append(DeviationFinding(
                        rule_id="PLAN_BIAS_DIRECTION_DEVIATION",
                        authority_class="OBSERVED_DEVIATION_ANNOTATION",
                        action_mode="ACTING",
                        observed_value=1.0,
                        threshold_value=0.0,
                        description="Long ENTRY executed contrary to declared BEARISH effective plan bias "
                                    "(position-flip: only the reducing quantity is exempt)"
                    ))
                elif plan_bias == "NO_TRADE":
                    findings.append(DeviationFinding(
                        rule_id="NO_TRADE_PLAN_DEVIATION",
                        authority_class="OBSERVED_DEVIATION_ANNOTATION",
                        action_mode="ACTING",
                        observed_value=1.0,
                        threshold_value=0.0,
                        description="Trade entry executed contrary to declared NO_TRADE plan bias"
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
                idemp_key = f"dev_{exec_id}_{f.rule_id}_{f.observed_value}"
                
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
