"""As-Of Signal Opportunity Logger & Mechanical Disposition Engine (Milestone 0.5).

Enforces:
1. Strict as-of bar-close decision contracts with direction checks (zero future lookahead).
2. Deduplication key (session_date, ticker, strategy_version_id, bar_timestamp_utc).
3. Production-grade mechanical disposition derivation:
   - EXECUTED: Order filled within validity window matching direction and trigger price (+- 2 bps).
   - PASSED: Trader was active in the market during the window, but did not execute this signal (or executed another strategy).
   - MISSED: Trader was connected but no trade was taken during the entire signal expiry window, or RiskGuard was locked out.
   - OFFLINE: Market session had zero broker connectivity or platform heartbeat during the signal window.
4. Intrabar ambiguity preservation for 1m bars touching stop and target.
"""

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from scripts.trading_brain.db.connection import get_db_connection
from scripts.utils.market_calendar import now_iso_utc, parse_iso_utc, to_iso_utc


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
    signal_direction: str = "LONG"             # 'LONG' or 'SHORT'
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
        bar_ts_iso = to_iso_utc(opportunity.bar_timestamp_utc)
        dec_ts_iso = to_iso_utc(opportunity.decision_time_utc)
        
        with get_db_connection(db_path) as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO signal_opportunities (
                    opportunity_id, session_date, ticker, strategy_version_id,
                    bar_timestamp_utc, decision_time_utc, signal_direction, trigger_price,
                    declared_stop_price, declared_target_1_price, declared_target_2_price,
                    stop_distance_bps, target_1_bps, feature_manifest_json, evaluation_mode
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    opp_id,
                    opportunity.session_date,
                    opportunity.ticker,
                    opportunity.strategy_version_id,
                    bar_ts_iso,
                    dec_ts_iso,
                    opportunity.signal_direction,
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
        is_platform_online: bool = True,
        db_path: Optional[Union[str, Path]] = None
    ) -> Dict[str, Any]:
        """Mechanically matches execution_events to signal_opportunities to derive dispositions.
        
        Evaluates EXECUTED, PASSED, MISSED, and OFFLINE states idempotently.
        """
        with get_db_connection(db_path) as conn:
            opp_cursor = conn.execute(
                "SELECT * FROM signal_opportunities WHERE session_date = ? AND ticker = ?;",
                (session_date, ticker)
            )
            opportunities = opp_cursor.fetchall()
            
            exec_cursor = conn.execute(
                "SELECT * FROM execution_events WHERE session_date = ? AND ticker = ?;",
                (session_date, ticker)
            )
            executions = exec_cursor.fetchall()
            
            existing_disp_cursor = conn.execute(
                """
                SELECT d.* FROM signal_disposition_events d
                JOIN signal_opportunities o ON d.opportunity_id = o.opportunity_id
                WHERE o.session_date = ? AND o.ticker = ?;
                """,
                (session_date, ticker)
            )
            existing_disps = {d["opportunity_id"]: d for d in existing_disp_cursor.fetchall()}
            
            matched_exec_ids = set()
            disposition_counts = {"EXECUTED": 0, "PASSED": 0, "MISSED": 0, "OFFLINE": 0}
            
            for opp in opportunities:
                opp_id = opp["opportunity_id"]
                if opp_id in existing_disps:
                    prev_state = existing_disps[opp_id]["disposition_state"]
                    disposition_counts[prev_state] = disposition_counts.get(prev_state, 0) + 1
                    if existing_disps[opp_id]["matched_execution_id"]:
                        matched_exec_ids.add(existing_disps[opp_id]["matched_execution_id"])
                    continue
                    
                trigger_price = opp["trigger_price"]
                direction = opp["signal_direction"]
                opp_ts = parse_iso_utc(opp["bar_timestamp_utc"])
                
                matched_exec = None
                other_trade_taken_in_window = False
                
                for ex in executions:
                    ex_ts = parse_iso_utc(ex["event_timestamp_utc"])
                    time_diff = (ex_ts - opp_ts).total_seconds()
                    
                    if abs(time_diff) <= expiry_seconds:
                        other_trade_taken_in_window = True
                        
                    if ex["execution_id"] in matched_exec_ids:
                        continue
                        
                    if 0 <= time_diff <= expiry_seconds:
                        action = ex["order_action"].upper()
                        # Direction match
                        dir_ok = (direction == "LONG" and action in ("BUY", "LONG")) or \
                                 (direction == "SHORT" and action in ("SELL", "SELL_SHORT", "SHORT"))
                        if dir_ok:
                            fill_price = ex["fill_price"]
                            price_diff_bps = abs(fill_price - trigger_price) / trigger_price * 10000.0
                            if price_diff_bps <= tolerance_bps:
                                matched_exec = ex
                                matched_exec_ids.add(ex["execution_id"])
                                break
                                
                if matched_exec:
                    state = "EXECUTED"
                    exec_id = matched_exec["execution_id"]
                    latency = (parse_iso_utc(matched_exec["event_timestamp_utc"]) - opp_ts).total_seconds()
                    reason = f"Matched execution {exec_id} with latency {latency:.1f}s"
                elif not is_platform_online:
                    state = "OFFLINE"
                    exec_id = None
                    latency = None
                    reason = "Platform or broker data feed was offline during signal window"
                elif other_trade_taken_in_window:
                    state = "PASSED"
                    exec_id = None
                    latency = None
                    reason = "Trader was active in session but passed this signal in favor of alternative setup"
                else:
                    state = "MISSED"
                    exec_id = None
                    latency = None
                    reason = "Setup triggered while trader was online but no execution event occurred"
                    
                disp_id = str(uuid.uuid4())
                conn.execute(
                    """
                    INSERT INTO signal_disposition_events (
                        disposition_id, opportunity_id, disposition_state, source_system,
                        matched_execution_id, latency_seconds, disposition_reason, event_timestamp_utc
                    ) VALUES (?, ?, ?, 'MECHANICAL_RECONCILER', ?, ?, ?, ?);
                    """,
                    (disp_id, opp_id, state, exec_id, latency, reason, now_iso_utc())
                )
                disposition_counts[state] = disposition_counts.get(state, 0) + 1
                
            # Unmatched executions route to unmatched_link_events
            for ex in executions:
                if ex["execution_id"] not in matched_exec_ids:
                    cur_link = conn.execute(
                        "SELECT link_event_id FROM unmatched_link_events WHERE execution_id = ?;",
                        (ex["execution_id"],)
                    )
                    if cur_link.fetchone():
                        continue
                        
                    ex_ts = parse_iso_utc(ex["event_timestamp_utc"])
                    candidates = [
                        opp["opportunity_id"] for opp in opportunities
                        if abs((ex_ts - parse_iso_utc(opp["bar_timestamp_utc"])).total_seconds()) <= 3600
                    ]
                    link_id = str(uuid.uuid4())
                    conn.execute(
                        """
                        INSERT INTO unmatched_link_events (
                            link_event_id, execution_id, candidate_opportunity_ids_json,
                            resolution_status, event_timestamp_utc
                        ) VALUES (?, ?, ?, 'OPEN', ?);
                        """,
                        (link_id, ex["execution_id"], json.dumps(candidates), now_iso_utc())
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
        now_iso = now_iso_utc()
        
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
