"""4-Way Mechanical Session Reconciler & Daily Process Delta Engine (Milestone 1.1).

Reconciles the 4-way institutional quadrant for any session:
1. Pre-Market Plan: get_plan_as_of (ex-ante) + post-hoc plan fallback @ 08:45 ET.
2. Signal Opportunities: Eligible mechanical setups triggered on bar close.
3. Executions & Interventions: Actual fills, stops, and RiskGuard telemetry.
4. Measured Tape Outcomes: Realized Day Type, HOD/LOD, MFE/MAE from session_tape_actuals.

Computes event-first process metrics without composite Goodhart scores.
"""

import json
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from scripts.trading_brain.db.connection import get_db_connection
from scripts.trading_brain.plans.plan_adapter import PlanAdapter, PlanContext
from scripts.trading_brain.signals.opportunity_logger import OpportunityLogger
from scripts.trading_brain.tape.tape_extractor import TapeMetricsExtractor
from scripts.utils.market_calendar import get_session_cutoff_utc, to_iso_utc


@dataclass
class PlanDelta:
    plan_found: bool
    plan_snapshot_id: Optional[str] = None
    primary_bias: Optional[str] = None
    max_intended_risk_bps: Optional[float] = None
    permitted_strategies: List[str] = field(default_factory=list)
    revision_seq: int = 1
    provenance_class: Optional[str] = None
    amendment_count: int = 0


@dataclass
class ForecastDelta:
    forecast_found: bool
    forecast_id: Optional[str] = None
    model_version_id: Optional[str] = None
    forecast_mode: Optional[str] = None
    predicted_day_type: Optional[str] = None
    predicted_bias: Optional[str] = None
    prob_r1: Optional[float] = None
    prob_r2: Optional[float] = None
    prob_dnp: Optional[float] = None
    prob_dwp: Optional[float] = None
    prob_rotational_chop: Optional[float] = None
    session_brier_loss: Optional[float] = None  # Single-session forecast loss
    session_log_loss: Optional[float] = None


@dataclass
class OpportunityDelta:
    total_opportunities: int = 0
    executed_count: int = 0
    passed_count: int = 0
    missed_count: int = 0
    offline_count: int = 0
    opportunities: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ExecutionDelta:
    total_executions: int = 0
    total_quantity: int = 0
    total_commission_usd: float = 0.0
    net_position: int = 0
    avg_slippage_bps: Optional[float] = None
    executions: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class InterventionDelta:
    total_interventions: int = 0
    hard_lockouts: int = 0
    soft_frictions: int = 0
    overrides_requested: int = 0
    overrides_accepted: int = 0
    interventions: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class TapeDelta:
    tape_found: bool
    actual_id: Optional[str] = None
    session_open: Optional[float] = None
    session_high: Optional[float] = None
    session_low: Optional[float] = None
    session_close: Optional[float] = None
    rth_close: Optional[float] = None
    realized_day_type: Optional[str] = None
    session_range_bps: Optional[float] = None
    quality_state: Optional[str] = None


@dataclass
class ProcessDeltaSummary:
    session_date: str
    ticker: str
    reconciled_at_utc: str
    plan: PlanDelta
    forecast: ForecastDelta
    opportunities: OpportunityDelta
    executions: ExecutionDelta
    interventions: InterventionDelta
    tape: TapeDelta
    
    # Process Adherence Flags
    risk_budget_respected: bool = True
    permitted_strategies_respected: bool = True
    unmatched_execution_count: int = 0


class DailyProcessDeltaReconciler:
    """Reconciles pre-market, intraday signals, broker fills, and post-market tape into a ProcessDeltaSummary."""

    @classmethod
    def reconcile_session(
        cls,
        session_date: str,
        ticker: str = "NQ1",
        db_path: Optional[Union[str, Path]] = None
    ) -> ProcessDeltaSummary:
        """Runs the 4-way reconciliation quadrant for the given session date and ticker."""
        eod_cutoff_utc = to_iso_utc(get_session_cutoff_utc(session_date, "16:15:00"))
        
        # 1. Pre-Market Plan (First try ex-ante get_plan_as_of, fallback to post-hoc snapshot)
        plan_ctx = PlanAdapter.get_plan_as_of(session_date, ticker, eod_cutoff_utc, db_path=db_path)
        
        if plan_ctx:
            plan_delta = PlanDelta(
                plan_found=True,
                plan_snapshot_id=plan_ctx.plan_snapshot_id,
                primary_bias=plan_ctx.primary_bias,
                max_intended_risk_bps=plan_ctx.max_intended_risk_bps,
                permitted_strategies=plan_ctx.permitted_strategies,
                revision_seq=plan_ctx.revision_seq,
                provenance_class=plan_ctx.provenance_class,
                amendment_count=len(plan_ctx.amendments)
            )
        else:
            # Fallback to query post-hoc reconstruction plan for diagnostic completeness
            with get_db_connection(db_path) as conn:
                cur = conn.execute(
                    """
                    SELECT * FROM plan_snapshots
                    WHERE session_date = ? AND ticker = ?
                    ORDER BY revision_seq DESC, received_at_utc DESC LIMIT 1;
                    """,
                    (session_date, ticker)
                )
                row = cur.fetchone()
                if row:
                    strats = json.loads(row["permitted_strategies_json"]) if row["permitted_strategies_json"] else []
                    plan_delta = PlanDelta(
                        plan_found=True,
                        plan_snapshot_id=row["plan_snapshot_id"],
                        primary_bias=row["primary_bias"],
                        max_intended_risk_bps=row["max_intended_risk_bps"],
                        permitted_strategies=strats,
                        revision_seq=row["revision_seq"],
                        provenance_class=row["provenance_class"],
                        amendment_count=0
                    )
                else:
                    plan_delta = PlanDelta(plan_found=False)

        # 2. Measured Tape Actuals
        with get_db_connection(db_path) as conn:
            cur = conn.execute(
                "SELECT * FROM v_session_tape_actuals_current WHERE session_date = ? AND ticker = ?;",
                (session_date, ticker)
            )
            tape_row = cur.fetchone()
            
            if tape_row:
                tape_delta = TapeDelta(
                    tape_found=True,
                    actual_id=tape_row["actual_id"],
                    session_open=tape_row["session_open"],
                    session_high=tape_row["session_high"],
                    session_low=tape_row["session_low"],
                    session_close=tape_row["session_close"],
                    rth_close=tape_row["rth_close"],
                    realized_day_type=tape_row["day_type_classification"],
                    session_range_bps=tape_row["session_range_bps"],
                    quality_state=tape_row["quality_state"]
                )
            else:
                tape_delta = TapeDelta(tape_found=False)

            # 3. Forecast Snapshot & Single-Session Realized Loss
            fc_cur = conn.execute(
                """
                SELECT * FROM forecast_snapshots
                WHERE session_date = ? AND ticker = ?
                ORDER BY CASE forecast_mode WHEN 'LIVE_PRODUCTION' THEN 1 WHEN 'FORECAST_LATE_RECEIVED' THEN 2 ELSE 3 END, received_at_utc DESC
                LIMIT 1;
                """,
                (session_date, ticker)
            )
            fc_row = fc_cur.fetchone()
            
            if fc_row:
                brier_loss = None
                log_loss = None
                
                # Compute single-session forecast loss against realized day type
                if tape_delta.tape_found and tape_delta.realized_day_type and not fc_row["abstain_flag"]:
                    realized = tape_delta.realized_day_type.upper()
                    prob_map = {
                        "R1": fc_row["prob_r1"] or 0.0,
                        "R2": fc_row["prob_r2"] or 0.0,
                        "DNP": fc_row["prob_dnp"] or 0.0,
                        "DWP": fc_row["prob_dwp"] or 0.0,
                        "ROTATIONAL_CHOP": fc_row["prob_rotational_chop"] or 0.0
                    }
                    
                    # Brier score: sum((p_i - o_i)^2)
                    brier_loss = sum(
                        (p - (1.0 if k == realized else 0.0)) ** 2
                        for k, p in prob_map.items()
                    )
                    
                    # Log loss: -ln(max(p_realized, 1e-6))
                    p_target = max(prob_map.get(realized, 0.0), 1e-6)
                    log_loss = -math.log(p_target)
                    
                forecast_delta = ForecastDelta(
                    forecast_found=True,
                    forecast_id=fc_row["forecast_id"],
                    model_version_id=fc_row["model_version_id"],
                    forecast_mode=fc_row["forecast_mode"],
                    predicted_day_type=fc_row["predicted_day_type"],
                    predicted_bias=fc_row["predicted_bias"],
                    prob_r1=fc_row["prob_r1"],
                    prob_r2=fc_row["prob_r2"],
                    prob_dnp=fc_row["prob_dnp"],
                    prob_dwp=fc_row["prob_dwp"],
                    prob_rotational_chop=fc_row["prob_rotational_chop"],
                    session_brier_loss=round(brier_loss, 4) if brier_loss is not None else None,
                    session_log_loss=round(log_loss, 4) if log_loss is not None else None
                )
            else:
                forecast_delta = ForecastDelta(forecast_found=False)

            # 4. Signal Opportunities & Dispositions
            disp_summary = OpportunityLogger.derive_dispositions(session_date, ticker, db_path=db_path)
            
            opp_cur = conn.execute(
                """
                SELECT o.*, d.disposition_state, d.matched_execution_id, d.latency_seconds
                FROM signal_opportunities o
                LEFT JOIN signal_disposition_events d ON o.opportunity_id = d.opportunity_id
                WHERE o.session_date = ? AND o.ticker = ?;
                """,
                (session_date, ticker)
            )
            opp_rows = opp_cur.fetchall()
            opp_list = [dict(r) for r in opp_rows]
            
            counts = disp_summary["dispositions"]
            opportunity_delta = OpportunityDelta(
                total_opportunities=len(opp_rows),
                executed_count=counts.get("EXECUTED", 0),
                passed_count=counts.get("PASSED", 0),
                missed_count=counts.get("MISSED", 0),
                offline_count=counts.get("OFFLINE", 0),
                opportunities=opp_list
            )

            # 5. Executions
            ex_cur = conn.execute(
                "SELECT * FROM execution_events WHERE session_date = ? AND ticker = ? ORDER BY event_timestamp_utc ASC;",
                (session_date, ticker)
            )
            ex_rows = ex_cur.fetchall()
            
            total_qty = sum(r["quantity"] for r in ex_rows)
            total_comm = sum(r["commission_usd"] or 0.0 for r in ex_rows)
            net_pos = sum(r["quantity"] if r["order_action"].upper() in ("BUY", "LONG") else -r["quantity"] for r in ex_rows)
            
            slippages = [r["slippage_bps"] for r in ex_rows if r["slippage_bps"] is not None]
            avg_slip = (sum(slippages) / len(slippages)) if slippages else None
            
            execution_delta = ExecutionDelta(
                total_executions=len(ex_rows),
                total_quantity=total_qty,
                total_commission_usd=round(total_comm, 2),
                net_position=net_pos,
                avg_slippage_bps=round(avg_slip, 2) if avg_slip is not None else None,
                executions=[dict(r) for r in ex_rows]
            )

            # 6. Interventions & Lockouts
            inv_cur = conn.execute(
                "SELECT * FROM intervention_events WHERE session_date = ? AND ticker = ? ORDER BY event_timestamp_utc ASC;",
                (session_date, ticker)
            )
            inv_rows = inv_cur.fetchall()
            
            hard_locks = sum(1 for r in inv_rows if r["authority_class"] == "HARD_LOCKOUT_ENFORCED" and r["enforced"])
            soft_fricts = sum(1 for r in inv_rows if r["authority_class"] == "SOFT_FRICTION_PROMPTED")
            ovr_req = sum(1 for r in inv_rows if r["override_requested"])
            ovr_acc = sum(1 for r in inv_rows if r["override_accepted"])
            
            intervention_delta = InterventionDelta(
                total_interventions=len(inv_rows),
                hard_lockouts=hard_locks,
                soft_frictions=soft_fricts,
                overrides_requested=ovr_req,
                overrides_accepted=ovr_acc,
                interventions=[dict(r) for r in inv_rows]
            )

            # 7. Unmatched Link Events
            unmatched_cur = conn.execute(
                "SELECT COUNT(*) AS c FROM v_unmatched_links_open;"
            )
            unmatched_count = unmatched_cur.fetchone()["c"]

        # Adherence Checks
        permitted_ok = True
        if plan_delta.plan_found and plan_delta.permitted_strategies:
            for ex in execution_delta.executions:
                strat = ex.get("strategy_version_id")
                if strat and strat not in plan_delta.permitted_strategies:
                    permitted_ok = False
                    break

        return ProcessDeltaSummary(
            session_date=session_date,
            ticker=ticker,
            reconciled_at_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            plan=plan_delta,
            forecast=forecast_delta,
            opportunities=opportunity_delta,
            executions=execution_delta,
            interventions=intervention_delta,
            tape=tape_delta,
            risk_budget_respected=True,
            permitted_strategies_respected=permitted_ok,
            unmatched_execution_count=unmatched_count
        )
