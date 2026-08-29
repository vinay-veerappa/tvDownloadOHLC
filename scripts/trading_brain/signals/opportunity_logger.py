"""As-Of Signal Opportunity Logger & Mechanical Disposition Engine (Milestone 0.5).

Enforces:
1. Strict as-of bar-close decision contracts with direction checks.
2. Deduplication key (session_date, ticker, strategy_version_id, bar_timestamp_utc) returning existing ID on duplicate.
3. Strategy-specific expiry duration: reads expiry from execution policy starting from decision_time_utc.
4. Window-Open Awareness: An opportunity whose window has not elapsed is marked PENDING_WINDOW_OPEN, not MISSED.
5. Production-Grade Dispositions with reconciliation dimensions:
   - EXECUTED: Matched fill within forward validity window matching direction and trigger price (+- 2 bps).
   - PASSED: Trader was active in the market during the window, but did not execute this setup.
   - MISSED: Validity window elapsed while trader was online with zero executions taken.
   - OFFLINE: Platform or broker was disconnected during window.
6. Ambiguity detection: fills matched by direction but not by price or strategy tag are recorded
   as AMBIGUOUS_LINK requiring manual review; multi-matched executions are flagged.
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
        """Records an as-of setup trigger into signal_opportunities and returns the authoritative opportunity_id."""
        opp_id = opportunity.opportunity_id or str(uuid.uuid4())
        bar_ts_iso = to_iso_utc(opportunity.bar_timestamp_utc)
        dec_ts_iso = to_iso_utc(opportunity.decision_time_utc)

        with get_db_connection(db_path) as conn:
            # Check for existing opportunity on deduplication key
            cur = conn.execute(
                """
                SELECT opportunity_id FROM signal_opportunities
                WHERE session_date = ? AND ticker = ? AND strategy_version_id = ? AND bar_timestamp_utc = ?;
                """,
                (opportunity.session_date, opportunity.ticker, opportunity.strategy_version_id, bar_ts_iso)
            )
            existing = cur.fetchone()
            if existing:
                return existing["opportunity_id"]

            conn.execute(
                """
                INSERT INTO signal_opportunities (
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
        default_expiry_seconds: int = 900,
        is_platform_online: bool = True,
        as_of_time_utc: Optional[Union[str, datetime]] = None,
        db_path: Optional[Union[str, Path]] = None
    ) -> Dict[str, Any]:
        """Mechanically matches execution_events to signal_opportunities to derive dispositions.

        Respects strategy-specific expiry, decision timestamps, window-open states, account context,
        strategy correlation/ambiguity, and prevents one execution from being claimed by multiple
        opportunities without an explicit audit flag.
        """
        now_dt = parse_iso_utc(as_of_time_utc) if as_of_time_utc else datetime.now(timezone.utc)

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

            # Load strategy-specific expiries from strategy_versions
            strat_cursor = conn.execute("SELECT strategy_version_id, execution_policy_json FROM strategy_versions;")
            strat_expiries = {}
            for s in strat_cursor.fetchall():
                pol = json.loads(s["execution_policy_json"]) if s["execution_policy_json"] else {}
                strat_expiries[s["strategy_version_id"]] = pol.get("expiry_seconds", default_expiry_seconds)

            matched_exec_ids: set[str] = set()
            exec_to_opps: Dict[str, List[str]] = {}
            disposition_counts = {"EXECUTED": 0, "PASSED": 0, "MISSED": 0, "OFFLINE": 0, "PENDING_WINDOW_OPEN": 0, "AMBIGUOUS_LINK": 0}

            for opp in opportunities:
                opp_id = opp["opportunity_id"]
                strat_id = opp["strategy_version_id"]
                expiry_seconds = strat_expiries.get(strat_id, default_expiry_seconds)

                trigger_price = opp["trigger_price"]
                direction = opp["signal_direction"]
                dec_ts = parse_iso_utc(opp["decision_time_utc"] or opp["bar_timestamp_utc"])
                window_end_dt = dec_ts + timedelta(seconds=expiry_seconds)

                matched_exec = None
                other_trade_taken_in_window = False
                ambiguity_candidates: List[Tuple[Any, str]] = []  # (execution_row, reason)

                for ex in executions:
                    ex_ts = parse_iso_utc(ex["event_timestamp_utc"])
                    time_diff = (ex_ts - dec_ts).total_seconds()

                    if 0 <= time_diff <= expiry_seconds:
                        other_trade_taken_in_window = True

                        if ex["execution_id"] in matched_exec_ids:
                            continue

                        action = ex["order_action"].upper()
                        dir_ok = (direction == "LONG" and action in ("BUY", "LONG")) or \
                                 (direction == "SHORT" and action in ("SELL", "SELL_SHORT", "SHORT"))

                        fill_price = ex["fill_price"]
                        price_diff_bps = abs(fill_price - trigger_price) / trigger_price * 10000.0 if trigger_price else float("inf")

                        # Strategy correlation check if tagged
                        tagged_strat = ex["strategy_version_id"]
                        strat_match = True
                        if tagged_strat and tagged_strat != strat_id:
                            strat_match = False

                        if dir_ok and strat_match and price_diff_bps <= tolerance_bps:
                            matched_exec = ex
                            matched_exec_ids.add(ex["execution_id"])
                            exec_to_opps.setdefault(ex["execution_id"], []).append(opp_id)
                            break

                        # Ambiguity: direction matches but price or strategy does not
                        if dir_ok:
                            if price_diff_bps > tolerance_bps:
                                ambiguity_candidates.append((ex, f"direction_match_price_mismatch_{price_diff_bps:.2f}bps"))
                            elif not strat_match:
                                ambiguity_candidates.append((ex, "direction_match_strategy_mismatch"))

                if matched_exec:
                    state = "EXECUTED"
                    exec_id = matched_exec["execution_id"]
                    latency = (parse_iso_utc(matched_exec["event_timestamp_utc"]) - dec_ts).total_seconds()
                    reason = f"Matched execution {exec_id} with latency {latency:.1f}s"
                elif ambiguity_candidates:
                    # The best single ambiguous candidate is logged; review is required.
                    state = "AMBIGUOUS_LINK"
                    exec_id = ambiguity_candidates[0][0]["execution_id"]
                    latency = None
                    reason = f"Ambiguous fill {exec_id}: " + ", ".join(r for _, r in ambiguity_candidates[:3])
                    matched_exec_ids.add(exec_id)
                    exec_to_opps.setdefault(exec_id, []).append(opp_id)
                elif not is_platform_online:
                    state = "OFFLINE"
                    exec_id = None
                    latency = None
                    reason = "Platform or broker data feed was offline during signal window"
                elif now_dt < window_end_dt and not other_trade_taken_in_window:
                    state = "PENDING_WINDOW_OPEN"
                    exec_id = None
                    latency = None
                    reason = f"Signal window remains open until {to_iso_utc(window_end_dt)}"
                elif other_trade_taken_in_window:
                    state = "PASSED"
                    exec_id = None
                    latency = None
                    reason = "Trader was active in session window but passed this signal in favor of alternative setup"
                else:
                    state = "MISSED"
                    exec_id = None
                    latency = None
                    reason = "Setup validity window elapsed without execution"

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

            # Multi-match audit: one execution claimed by more than one opportunity is a data-quality flag.
            multi_match_execs = {eid: opps for eid, opps in exec_to_opps.items() if len(opps) > 1}
            for eid, opps in multi_match_execs.items():
                audit_id = str(uuid.uuid4())
                conn.execute(
                    """
                    INSERT INTO unmatched_link_events (
                        link_event_id, execution_id, candidate_opportunity_ids_json,
                        resolution_status, resolution_notes, event_timestamp_utc
                    ) VALUES (?, ?, ?, 'OPEN', ?, ?);
                    """,
                    (
                        audit_id, eid, json.dumps(opps),
                        f"MULTI_MATCH_AUDIT: execution matched to {len(opps)} opportunities",
                        now_iso_utc(),
                    )
                )

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
                        if abs((ex_ts - parse_iso_utc(opp["decision_time_utc"] or opp["bar_timestamp_utc"])).total_seconds()) <= 3600
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
                "unmatched_executions": len(executions) - len(matched_exec_ids),
                "multi_match_executions": len(multi_match_execs),
            }