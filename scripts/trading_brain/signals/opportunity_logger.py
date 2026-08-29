"""As-Of Signal Opportunity Logger & Mechanical Disposition Engine (Milestone 0.5).

Enforces:
1. Strict as-of bar-close decision contracts (zero future lookahead).
2. Deduplication key (session_date, ticker, strategy_version_id, bar_timestamp_utc).
3. Mechanical disposition derivation matching execution_events to signal_opportunities.
4. Intrabar ambiguity preservation for 1m bars touching stop and target.
"""

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from scripts.trading_brain.db.connection import get_db_connection


@dataclass
class SignalOpportunity:
    opportunity_id: str
    session_date: str
    ticker: str
    strategy_version_id: str
    bar_timestamp_utc: str
    decision_time_utc: str
    trigger_price: float
    declared_stop_price: float
    declared_target_1_price: float
    stop_distance_bps: float
    target_1_bps: float
    feature_manifest: Dict[str, Any]
    declared_target_2_price: Optional[float] = None
    evaluation_mode: str = "LIVE_CAPTURE"


class OpportunityLogger:
    """Service class for logging setup opportunities, deriving mechanical dispositions, and computing outcomes."""

    @staticmethod
    def record_opportunity(
        opportunity: SignalOpportunity,
        db_path: Optional[Union[str, Path]] = None
    ) -> str:
        """Records an as-of setup trigger into signal_opportunities."""
        opp_id = opportunity.opportunity_id or str(uuid.uuid4())
        
        with get_db_connection(db_path) as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO signal_opportunities (
                    opportunity_id, session_date, ticker, strategy_version_id,
                    bar_timestamp_utc, decision_time_utc, trigger_price,
                    declared_stop_price, declared_target_1_price, declared_target_2_price,
                    stop_distance_bps, target_1_bps, feature_manifest_json, evaluation_mode
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    opp_id,
                    opportunity.session_date,
                    opportunity.ticker,
                    opportunity.strategy_version_id,
                    opportunity.bar_timestamp_utc,
                    opportunity.decision_time_utc,
                    opportunity.trigger_price,
                    opportunity.declared_stop_price,
                    opportunity.declared_target_1_price,
                    opportunity.declared_target_2_price,
                    opportunity.stop_distance_bps,
                    opportunity.target_1_bps,
                    json.dumps(opportunity.feature_manifest),
                    opportunity.evaluation_mode
                )
            )
        return opp_id

    @staticmethod
    def derive_dispositions(
        session_date: str,
        ticker: str,
        tolerance_bps: float = 2.0,
        expiry_seconds: int = 900,
        db_path: Optional[Union[str, Path]] = None
    ) -> Dict[str, Any]:
        """Mechanically matches execution_events to signal_opportunities to derive dispositions."""
        with get_db_connection(db_path) as conn:
            # Query opportunities for session
            opp_cursor = conn.execute(
                "SELECT * FROM signal_opportunities WHERE session_date = ? AND ticker = ?;",
                (session_date, ticker)
            )
            opportunities = opp_cursor.fetchall()
            
            # Query executions for session
            exec_cursor = conn.execute(
                "SELECT * FROM execution_events WHERE session_date = ? AND ticker = ?;",
                (session_date, ticker)
            )
            executions = exec_cursor.fetchall()
            
            matched_exec_ids = set()
            disposition_counts = {"EXECUTED": 0, "PASSED": 0, "MISSED": 0}
            
            for opp in opportunities:
                opp_id = opp["opportunity_id"]
                trigger_price = opp["trigger_price"]
                opp_ts = datetime.fromisoformat(opp["bar_timestamp_utc"].replace("Z", "+00:00"))
                
                matched_exec = None
                for ex in executions:
                    if ex["execution_id"] in matched_exec_ids:
                        continue
                    ex_ts = datetime.fromisoformat(ex["event_timestamp_utc"].replace("Z", "+00:00"))
                    
                    # Check if execution occurred within validity window
                    time_diff = (ex_ts - opp_ts).total_seconds()
                    if 0 <= time_diff <= expiry_seconds:
                        # Check price tolerance
                        fill_price = ex["fill_price"]
                        price_diff_bps = abs(fill_price - trigger_price) / trigger_price * 10000.0
                        if price_diff_bps <= tolerance_bps:
                            matched_exec = ex
                            matched_exec_ids.add(ex["execution_id"])
                            break
                            
                if matched_exec:
                    state = "EXECUTED"
                    exec_id = matched_exec["execution_id"]
                    latency = (datetime.fromisoformat(matched_exec["event_timestamp_utc"].replace("Z", "+00:00")) - opp_ts).total_seconds()
                    reason = f"Matched execution {exec_id} with latency {latency:.1f}s"
                else:
                    state = "PASSED"
                    exec_id = None
                    latency = None
                    reason = "No matching execution event found during validity window"
                    
                disp_id = str(uuid.uuid4())
                conn.execute(
                    """
                    INSERT INTO signal_disposition_events (
                        disposition_id, opportunity_id, disposition_state, source_system,
                        matched_execution_id, latency_seconds, disposition_reason, event_timestamp_utc
                    ) VALUES (?, ?, ?, 'MECHANICAL_RECONCILER', ?, ?, ?, ?);
                    """,
                    (disp_id, opp_id, state, exec_id, latency, reason, datetime.now(timezone.utc).isoformat())
                )
                disposition_counts[state] += 1
                
            # Unmatched executions route to unmatched_link_events
            for ex in executions:
                if ex["execution_id"] not in matched_exec_ids:
                    link_id = str(uuid.uuid4())
                    conn.execute(
                        """
                        INSERT INTO unmatched_link_events (
                            link_event_id, execution_id, candidate_opportunity_ids_json,
                            resolution_status, event_timestamp_utc
                        ) VALUES (?, ?, '[]', 'OPEN', ?);
                        """,
                        (link_id, ex["execution_id"], datetime.now(timezone.utc).isoformat())
                    )
                    
            return {
                "total_opportunities": len(opportunities),
                "dispositions": disposition_counts,
                "unmatched_executions": len(executions) - len(matched_exec_ids)
            }

    @staticmethod
    def record_signal_outcome(
        opportunity_id: str,
        observed_outcome: str,
        pessimistic_bound: str,
        optimistic_bound: str,
        realized_mfe_bps: float,
        realized_mae_bps: float,
        bars_held: int,
        db_path: Optional[Union[str, Path]] = None
    ) -> str:
        """Records theoretical post-hoc evaluation outcome with preserved ambiguity bounds."""
        outcome_id = str(uuid.uuid4())
        now_iso = datetime.now(timezone.utc).isoformat()
        
        with get_db_connection(db_path) as conn:
            conn.execute(
                """
                INSERT INTO signal_outcomes (
                    outcome_id, opportunity_id, observed_outcome, pessimistic_bound,
                    optimistic_bound, realized_mfe_bps, realized_mae_bps, bars_held, evaluated_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    outcome_id,
                    opportunity_id,
                    observed_outcome,
                    pessimistic_bound,
                    optimistic_bound,
                    realized_mfe_bps,
                    realized_mae_bps,
                    bars_held,
                    now_iso
                )
            )
        return outcome_id
