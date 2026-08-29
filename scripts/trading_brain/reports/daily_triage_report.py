"""Interactive Daily Triage & Process Delta Report Generator (Milestone 1.2).

Produces:
1. Concise, event-first Markdown Daily Process Delta Report (< 5 min read), persisted to data/wargaming/reports/.
2. JSON structured delta report for programmatic consumption.
3. Review Queue action handlers for unmatched link resolution and information item curation.
"""

import argparse
import json
import sys
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from scripts.trading_brain.db.connection import REPO_ROOT, get_db_connection, resolve_db_path
from scripts.trading_brain.evaluation.daily_process_delta import DailyProcessDeltaReconciler, ProcessDeltaSummary
from scripts.utils.market_calendar import now_iso_utc

REPORTS_DIR = REPO_ROOT / "data" / "wargaming" / "reports"


class DailyTriageReportGenerator:
    """Generates daily process delta triage reports and handles interactive review triage."""

    @classmethod
    def generate_report(
        cls,
        session_date: str,
        ticker: str = "NQ1",
        output_dir: Optional[Union[str, Path]] = None,
        db_path: Optional[Union[str, Path]] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """Generates Markdown and JSON reports and persists markdown to data/wargaming/reports/."""
        summary = DailyProcessDeltaReconciler.reconcile_session(session_date, ticker, db_path=db_path)
        summary_dict = asdict(summary)
        
        md = cls.render_markdown(summary)
        
        # Persist markdown to disk
        target_dir = Path(output_dir) if output_dir else REPORTS_DIR
        if not target_dir.is_absolute():
            target_dir = REPO_ROOT / target_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        
        report_file = target_dir / f"daily_process_delta_{session_date}_{ticker}.md"
        report_file.write_text(md, encoding="utf-8")
        
        return md, summary_dict

    @classmethod
    def render_markdown(cls, summary: ProcessDeltaSummary) -> str:
        """Renders the concise, event-first Markdown report."""
        s = summary
        
        plan_badge = f"`{s.plan.primary_bias}` ({s.plan.provenance_class or 'NO_PLAN'})" if s.plan.plan_found else "`NO_PLAN_DECLARED`"
        fc_badge = f"`{s.forecast.forecast_mode}` (Pred: `{s.forecast.predicted_day_type or 'NONE'}`)" if s.forecast.forecast_found else "`NO_FORECAST`"
        tape_badge = f"`{s.tape.realized_day_type}` (`{s.tape.quality_state}`)" if s.tape.tape_found else "`TAPE_PENDING`"
        
        lines = [
            f"# Daily Process Delta & Triage Report: {s.session_date} ({s.ticker})",
            f"**Reconciled at**: `{s.reconciliation_timestamp_utc}` | **Plan**: {plan_badge} | **Forecast**: {fc_badge} | **Tape**: {tape_badge}",
            "",
            "---",
            "",
            "## 1. 4-Way Reconciliation Quadrant",
            "",
            "| Quadrant Pillar | Declared / Predicted | Measured Tape / Actual | Deviation / Delta |",
            "|---|---|---|---|"
        ]
        
        plan_dec = f"Bias: {s.plan.primary_bias}, Max Risk: {s.plan.max_intended_risk_bps} bps" if s.plan.plan_found else "No plan declared"
        tape_act = f"Realized: {s.tape.realized_day_type}, Range: {s.tape.session_range_bps:.1f} bps" if s.tape.tape_found else "Pending tape"
        plan_delta = "Permitted strats respected" if s.permitted_strategies_respected else "⚠️ UNPERMITTED STRATEGY EXECUTED"
        if not s.risk_budget_respected:
            plan_delta += " | ⚠️ RISK BUDGET EXCEEDED"
        lines.append(f"| **1. Pre-Market Plan** | {plan_dec} | {tape_act} | {plan_delta} |")
        
        fc_pred = f"{s.forecast.predicted_day_type} ({s.forecast.predicted_bias})" if s.forecast.forecast_found else "N/A"
        brier = f"Brier: {s.forecast.session_brier_loss:.4f}, LogLoss: {s.forecast.session_log_loss:.4f}" if s.forecast.session_brier_loss is not None else "N/A"
        lines.append(f"| **2. Day Type Forecast** | Pred: {fc_pred} | Tape: {s.tape.realized_day_type or 'N/A'} | {brier} |")
        
        opp_str = f"Total: {s.opportunities.total_opportunities} (Exec: {s.opportunities.executed_count}, Passed: {s.opportunities.passed_count}, Missed: {s.opportunities.missed_count})"
        exec_str = f"Fills: {s.execution.total_executions}, Net Pos: {s.execution.net_position}"
        slip_str = f"Avg Slippage: {s.execution.avg_slippage_bps} bps" if s.execution.avg_slippage_bps is not None else "0.0 bps"
        lines.append(f"| **3. Signals & Executions** | {opp_str} | {exec_str} | {slip_str} |")
        
        inv_str = f"Hard Locks: {s.interventions.hard_lockouts}, Frictions: {s.interventions.soft_frictions}"
        ovr_str = f"Overrides: Req={s.interventions.overrides_requested}, Acc={s.interventions.overrides_accepted}"
        lines.append(f"| **4. Risk Interventions** | Total: {s.interventions.total_interventions} | {inv_str} | {ovr_str} |")
        
        lines.extend([
            "",
            "---",
            "",
            "## 2. Signal Opportunities & Execution Realization",
            ""
        ])
        
        if s.opportunities.opportunities:
            lines.extend([
                "| Opportunity ID | Strategy | Dir | Trigger | Stop (bps) | Target 1 (bps) | Disposition | Matched Fill | Latency |",
                "|---|---|:---:|---:|---:|---:|:---:|:---:|---:|"
            ])
            for o in s.opportunities.opportunities:
                disp = o.get("disposition_state", "UNRESOLVED")
                fill_id = o.get("matched_execution_id") or "-"
                lat = f"{o['latency_seconds']:.1f}s" if o.get("latency_seconds") is not None else "-"
                lines.append(
                    f"| `{o['opportunity_id'][:12]}...` | `{o['strategy_version_id']}` | {o.get('signal_direction', 'LONG')} | {o['trigger_price']:.2f} | {o['stop_distance_bps']:.1f} | {o['target_1_bps']:.1f} | **{disp}** | `{fill_id}` | {lat} |"
                )
        else:
            lines.append("*No eligible mechanical opportunities triggered during this session.*")
            
        lines.extend([
            "",
            "---",
            "",
            "## 3. Measured Tape Actuals",
            ""
        ])
        
        if s.tape.tape_found:
            lines.extend([
                f"- **Session Open (09:30 ET)**: `{s.tape.session_open:.2f}`",
                f"- **Session High**: `{s.tape.session_high:.2f}` | **Session Low**: `{s.tape.session_low:.2f}`",
                f"- **RTH Close (16:00 ET)**: `{s.tape.rth_close:.2f}` | **Session Close (16:15 ET)**: `{s.tape.session_close:.2f}`",
                f"- **Session Range**: `{s.tape.session_range_bps:.1f} bps`",
                f"- **Realized Day Type**: **`{s.tape.realized_day_type}`**",
                f"- **Data Quality**: `{s.tape.quality_state}`"
            ])
        else:
            lines.append("*Tape actuals have not yet been extracted for this session.*")
            
        lines.extend([
            "",
            "---",
            "",
            "## 4. Open Triage & Review Queue Items",
            ""
        ])
        
        if s.unmatched_execution_count > 0:
            lines.append(f"⚠️ **{s.unmatched_execution_count} unmatched executions require operator linkage in `v_unmatched_links_open`**.")
        else:
            lines.append("✅ **Zero open unmatched links in review queue.**")
            
        return "\n".join(lines)

    @classmethod
    def resolve_unmatched_link(
        cls,
        link_event_id: str,
        resolution_status: str,
        resolved_opportunity_id: Optional[str] = None,
        resolution_notes: Optional[str] = None,
        resolved_by: str = "OPERATOR",
        db_path: Optional[Union[str, Path]] = None
    ) -> str:
        """Appends a resolution event to unmatched_link_events."""
        with get_db_connection(db_path) as conn:
            cur = conn.execute("SELECT execution_id, candidate_opportunity_ids_json FROM unmatched_link_events WHERE link_event_id = ?;", (link_event_id,))
            row = cur.fetchone()
            if not row:
                raise ValueError(f"Unmatched link event {link_event_id} not found.")
                
            new_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO unmatched_link_events (
                    link_event_id, execution_id, candidate_opportunity_ids_json,
                    resolution_status, resolved_opportunity_id, resolution_notes,
                    resolved_by, event_timestamp_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    new_id,
                    row["execution_id"],
                    row["candidate_opportunity_ids_json"],
                    resolution_status,
                    resolved_opportunity_id,
                    resolution_notes,
                    resolved_by,
                    now_iso_utc()
                )
            )
            return new_id

    @classmethod
    def review_information_item(
        cls,
        information_id: str,
        review_state: str,
        reviewer: str = "OPERATOR",
        review_notes: Optional[str] = None,
        db_path: Optional[Union[str, Path]] = None
    ) -> str:
        """Appends a review transition event to information_item_review_events."""
        with get_db_connection(db_path) as conn:
            event_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO information_item_review_events (
                    review_event_id, information_id, review_state, reviewer,
                    review_notes, event_timestamp_utc
                ) VALUES (?, ?, ?, ?, ?, ?);
                """,
                (event_id, information_id, review_state.upper(), reviewer, review_notes, now_iso_utc())
            )
            return event_id


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    parser = argparse.ArgumentParser(description="Generate Daily Process Delta Report")
    parser.add_argument("--date", type=str, required=True, help="Session date (YYYY-MM-DD)")
    parser.add_argument("--ticker", type=str, default="NQ1", help="Ticker symbol (default: NQ1)")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of Markdown")
    args = parser.parse_args()
    
    md_report, json_report = DailyTriageReportGenerator.generate_report(args.date, args.ticker)
    if args.json:
        print(json.dumps(json_report, indent=2))
    else:
        print(md_report)
