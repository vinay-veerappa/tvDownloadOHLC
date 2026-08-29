"""Daily Process Delta & 4-Way Institutional Reconciliation Engine (Milestone 1.1).

Reconciles the 4-way institutional quadrant:
1. Pre-Market Plan (Primary Bias, Invalidation, Risk Budget, Permitted Strategies)
2. Day Type Forecast (5-Class Distribution: R1, R2, DNP, DWP, ROTATIONAL_CHOP)
3. Signal Opportunities & Executions (Dispositions, Discretionary Executions, Interventions)
4. Measured Tape Actuals (Session OHLC, Canonical Day Type, Quality State)

Key Invariants:
1. Clean Production Scoring Only: ONLY compute Brier and log loss for LIVE_PRODUCTION forecasts
   on CLEAN / SCHEDULED_SHORT_SESSION tape actuals. REPLAY_AUDIT, LATE, or INCOMPLETE tapes are audit-only (loss=None).
2. Session-Specific Unmatched Links: Filters open unmatched links specifically for session_date and ticker.
3. Strict Compliance Checks: Executions without a plan, or under NO_TRADE / zero risk, are strictly flagged non-compliant.
"""

import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from scripts.trading_brain.db.connection import get_db_connection
from scripts.trading_brain.plans.plan_adapter import PlanAdapter, PlanContext
from scripts.utils.market_calendar import now_iso_utc, to_iso_utc

VALID_DAY_TYPES = ["R1", "R2", "DNP", "DWP", "ROTATIONAL_CHOP"]


@dataclass
class PlanEvaluationSummary:
    plan_found: bool
    plan_snapshot_id: Optional[str]
    provenance_class: Optional[str]
    primary_bias: Optional[str]
    max_intended_risk_bps: Optional[float]
    permitted_strategies: List[str]
    amendment_count: int


@dataclass
class ForecastEvaluationSummary:
    forecast_found: bool
    forecast_id: Optional[str]
    forecast_mode: Optional[str]               # 'LIVE_PRODUCTION', 'FORECAST_LATE_RECEIVED', 'REPLAY_AUDIT'
    predicted_day_type: Optional[str]
    predicted_bias: Optional[str]
    prob_distribution: Dict[str, float]
    abstain_flag: bool
    session_brier_loss: Optional[float]        # Scored ONLY if LIVE_PRODUCTION on clean tape
    session_log_loss: Optional[float]          # Scored ONLY if LIVE_PRODUCTION on clean tape
    scored_for_calibration: bool


@dataclass
class OpportunityReconciliationSummary:
    total_opportunities: int
    executed_count: int
    passed_count: int
    missed_count: int
    offline_count: int
    pending_count: int
    unmatched_execution_count: int
    total_executions: int
    interventions_count: int
    net_position: int = 0
    avg_slippage_bps: Optional[float] = None
    opportunities: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def unmatched_executions_count(self) -> int:
        return self.unmatched_execution_count


@dataclass
class TapeEvaluationSummary:
    tape_found: bool
    actual_id: Optional[str]
    session_open: float
    session_high: float
    session_low: float
    session_close: float
    rth_close: float
    session_range_bps: float
    realized_day_type: str
    quality_state: str


@dataclass
class InterventionSummary:
    total_interventions: int = 0
    hard_lockouts: int = 0
    soft_frictions: int = 0
    overrides_requested: int = 0
    overrides_accepted: int = 0


@dataclass
class DailyProcessDeltaScorecard:
    @property
    def unmatched_execution_count(self) -> int:
        return self.execution.unmatched_execution_count

    @property
    def opportunities(self) -> 'OpportunityReconciliationSummary':
        return self.execution
        
    @property
    def executions(self) -> 'OpportunityReconciliationSummary':
        return self.execution

    @property
    def interventions(self) -> InterventionSummary:
        return InterventionSummary(total_interventions=self.execution.interventions_count)

    session_date: str
    ticker: str
    plan: PlanEvaluationSummary
    forecast: ForecastEvaluationSummary
    execution: OpportunityReconciliationSummary
    tape: TapeEvaluationSummary
    
    # Process Adherence Flags
    plan_compliant: bool
    bias_direction_respected: bool
    permitted_strategies_respected: bool
    risk_budget_respected: bool
    
    # Quadrant Classification
    process_outcome_quadrant: str              # 'GOOD_PROCESS_GOOD_OUTCOME', 'GOOD_PROCESS_BAD_OUTCOME', 'BAD_PROCESS_GOOD_OUTCOME', 'BAD_PROCESS_BAD_OUTCOME'
    reconciliation_timestamp_utc: str


class DailyProcessDeltaReconciler:
    """Computes daily 4-way institutional reconciliation."""

    @classmethod
    def reconcile_session(
        cls,
        session_date: str,
        ticker: str,
        db_path: Optional[Union[str, Path]] = None
    ) -> DailyProcessDeltaScorecard:
        """Reconciles plan, forecast, execution, and tape for a single session."""
        with get_db_connection(db_path) as conn:
            # 1. Resolve Plan
            plan_ctx = PlanAdapter.get_plan_as_of(
                session_date, ticker, f"{session_date}T23:59:59Z", db_path=db_path
            )
            if plan_ctx:
                plan_summary = PlanEvaluationSummary(
                    plan_found=True,
                    plan_snapshot_id=plan_ctx.plan_snapshot_id,
                    provenance_class=plan_ctx.provenance_class,
                    primary_bias=plan_ctx.effective_primary_bias,
                    max_intended_risk_bps=plan_ctx.effective_max_intended_risk_bps,
                    permitted_strategies=plan_ctx.effective_permitted_strategies,
                    amendment_count=len(plan_ctx.amendments)
                )
            else:
                plan_summary = PlanEvaluationSummary(
                    plan_found=False,
                    plan_snapshot_id=None,
                    provenance_class=None,
                    primary_bias=None,
                    max_intended_risk_bps=None,
                    permitted_strategies=[],
                    amendment_count=0
                )
                
            # 2. Resolve Tape Actuals
            tape_cur = conn.execute(
                """
                SELECT * FROM v_session_tape_actuals_current
                WHERE session_date = ? AND ticker = ?;
                """,
                (session_date, ticker)
            )
            tape_row = tape_cur.fetchone()
            if tape_row:
                tape_summary = TapeEvaluationSummary(
                    tape_found=True,
                    actual_id=tape_row["actual_id"],
                    session_open=tape_row["session_open"],
                    session_high=tape_row["session_high"],
                    session_low=tape_row["session_low"],
                    session_close=tape_row["session_close"],
                    rth_close=tape_row["rth_close"],
                    session_range_bps=tape_row["session_range_bps"],
                    realized_day_type=tape_row["day_type_classification"],
                    quality_state=tape_row["quality_state"]
                )
            else:
                tape_summary = TapeEvaluationSummary(
                    tape_found=False,
                    actual_id=None,
                    session_open=0.0,
                    session_high=0.0,
                    session_low=0.0,
                    session_close=0.0,
                    rth_close=0.0,
                    session_range_bps=0.0,
                    realized_day_type="UNKNOWN",
                    quality_state="MISSING"
                )

            # 3. Resolve Forecast
            f_cur = conn.execute(
                """
                SELECT * FROM forecast_snapshots
                WHERE session_date = ? AND ticker = ?
                ORDER BY CASE WHEN forecast_mode = 'LIVE_PRODUCTION' THEN 1
                              WHEN forecast_mode = 'FORECAST_LATE_RECEIVED' THEN 2
                              ELSE 3 END, rowid DESC LIMIT 1;
                """,
                (session_date, ticker)
            )
            f_row = f_cur.fetchone()
            
            brier_loss = None
            log_loss = None
            scored = False
            
            if f_row:
                f_mode = f_row["forecast_mode"]
                abstain = bool(f_row["abstain_flag"])
                probs = {
                    "R1": f_row["prob_r1"] or 0.0,
                    "R2": f_row["prob_r2"] or 0.0,
                    "DNP": f_row["prob_dnp"] or 0.0,
                    "DWP": f_row["prob_dwp"] or 0.0,
                    "ROTATIONAL_CHOP": f_row["prob_rotational_chop"] or 0.0
                }
                
                # Clean Production Scoring Invariant:
                # Score ONLY if LIVE_PRODUCTION, not abstained, and tape is clean / short session
                tape_is_valid = tape_summary.tape_found and (tape_summary.quality_state in ("CLEAN", "SCHEDULED_SHORT_SESSION"))
                if f_mode == "LIVE_PRODUCTION" and not abstain and tape_is_valid:
                    realized_dt = tape_summary.realized_day_type
                    if realized_dt in VALID_DAY_TYPES:
                        brier = 0.0
                        for dt in VALID_DAY_TYPES:
                            y_k = 1.0 if dt == realized_dt else 0.0
                            brier += (probs[dt] - y_k) ** 2
                        brier_loss = round(brier, 6)
                        p_real = max(probs[realized_dt], 1e-15)
                        log_loss = round(-math.log(p_real), 6)
                        scored = True
                        
                forecast_summary = ForecastEvaluationSummary(
                    forecast_found=True,
                    forecast_id=f_row["forecast_id"],
                    forecast_mode=f_mode,
                    predicted_day_type=f_row["predicted_day_type"],
                    predicted_bias=f_row["predicted_bias"],
                    prob_distribution=probs,
                    abstain_flag=abstain,
                    session_brier_loss=brier_loss,
                    session_log_loss=log_loss,
                    scored_for_calibration=scored
                )
            else:
                forecast_summary = ForecastEvaluationSummary(
                    forecast_found=False,
                    forecast_id=None,
                    forecast_mode=None,
                    predicted_day_type=None,
                    predicted_bias=None,
                    prob_distribution={},
                    abstain_flag=False,
                    session_brier_loss=None,
                    session_log_loss=None,
                    scored_for_calibration=False
                )

            # 4. Resolve Execution & Opportunities
            opp_cur = conn.execute(
                """
                SELECT o.*,
                       COALESCE(d.disposition_state, 'PENDING_WINDOW_OPEN') AS active_disposition
                FROM signal_opportunities o
                LEFT JOIN signal_disposition_events d ON d.opportunity_id = o.opportunity_id
                  AND d.rowid = (
                      SELECT MAX(d2.rowid) FROM signal_disposition_events d2
                      WHERE d2.opportunity_id = o.opportunity_id
                  )
                WHERE o.session_date = ? AND o.ticker = ?;
                """,
                (session_date, ticker)
            )
            opp_rows = opp_cur.fetchall()
            
            exec_counts = {"EXECUTED": 0, "PASSED": 0, "MISSED": 0, "OFFLINE": 0, "PENDING_WINDOW_OPEN": 0}
            for r in opp_rows:
                st = r["active_disposition"]
                exec_counts[st] = exec_counts.get(st, 0) + 1
                
            ex_cur = conn.execute(
                "SELECT COUNT(*) AS c FROM execution_events WHERE session_date = ? AND ticker = ?;",
                (session_date, ticker)
            )
            total_execs = ex_cur.fetchone()["c"]
            
            # Session-Specific Unmatched Link Count
            unmatched_cur = conn.execute(
                """
                SELECT COUNT(*) AS c FROM v_unmatched_links_open u
                JOIN execution_events e ON u.execution_id = e.execution_id
                WHERE e.session_date = ? AND e.ticker = ?;
                """,
                (session_date, ticker)
            )
            unmatched_execs = unmatched_cur.fetchone()["c"]
            
            int_cur = conn.execute(
                "SELECT COUNT(*) AS c FROM intervention_events WHERE session_date = ? AND ticker = ?;",
                (session_date, ticker)
            )
            interventions_count = int_cur.fetchone()["c"]
            
            exec_summary = OpportunityReconciliationSummary(
                total_opportunities=len(opp_rows),
                executed_count=exec_counts.get("EXECUTED", 0),
                passed_count=exec_counts.get("PASSED", 0),
                missed_count=exec_counts.get("MISSED", 0),
                offline_count=exec_counts.get("OFFLINE", 0),
                pending_count=exec_counts.get("PENDING_WINDOW_OPEN", 0),
                unmatched_execution_count=unmatched_execs,
                total_executions=total_execs,
                interventions_count=interventions_count
            )

            # 5. Strict Process Compliance Derivation
            if not plan_summary.plan_found:
                # If no plan exists, any execution is non-compliant
                plan_compliant = (total_execs == 0)
                bias_respected = (total_execs == 0)
                strat_respected = (total_execs == 0)
                risk_respected = (total_execs == 0)
            else:
                # Bias respected: no deviation annotations (PLAN_BIAS_DIRECTION_DEVIATION / NO_TRADE_PLAN_DEVIATION)
                # against the effective plan. Generic interventions are orthogonal to plan adherence.
                bias_dev_cur = conn.execute(
                    """
                    SELECT COUNT(*) AS c FROM intervention_events
                    WHERE session_date = ? AND ticker = ?
                      AND producer = 'PYTHON_DEVIATION_ANNOTATOR'
                      AND rule_id IN ('PLAN_BIAS_DIRECTION_DEVIATION', 'NO_TRADE_PLAN_DEVIATION')
                      AND action_mode = 'ACTING';
                    """,
                    (session_date, ticker)
                )
                bias_respected = (bias_dev_cur.fetchone()["c"] == 0)

                # Permitted Strategies Check: every execution must carry a strategy_version_id that is in the
                # effective permitted list, unless no list was declared (then any tag is a breach).
                if total_execs > 0:
                    if not plan_summary.permitted_strategies or plan_summary.primary_bias == "NO_TRADE":
                        strat_respected = False
                    else:
                        bad_strat_cur = conn.execute(
                            """
                            SELECT COUNT(*) AS c FROM execution_events
                            WHERE session_date = ? AND ticker = ?
                              AND (
                                strategy_version_id IS NULL
                                OR strategy_version_id NOT IN ({})
                              );
                            """.format(",".join(["?"] * len(plan_summary.permitted_strategies))),
                            (session_date, ticker, *plan_summary.permitted_strategies)
                        )
                        strat_respected = (bad_strat_cur.fetchone()["c"] == 0)
                else:
                    strat_respected = True

                # Risk Budget Check: executed opportunities' declared stop distances must be
                # within 5% of the plan's risk budget. FAIL-CLOSED on unmatched discretionary
                # fills: a discretionary execution carries no declared stop distance, so its
                # risk compliance CANNOT be verified from the ledger — unverified is not
                # compliant.
                if total_execs > 0:
                    if plan_summary.max_intended_risk_bps is None or plan_summary.max_intended_risk_bps <= 0.0:
                        risk_respected = False
                    else:
                        risk_respected = True
                        verified_via_opportunity = 0
                        for r in opp_rows:
                            if r["active_disposition"] == "EXECUTED":
                                verified_via_opportunity += 1
                                if r["stop_distance_bps"] > (plan_summary.max_intended_risk_bps * 1.05):
                                    risk_respected = False
                                    break
                        # Every execution must be accounted for by a matched EXECUTED
                        # opportunity (1:1 within latency tolerances). Executions beyond
                        # the matched set are discretionary/unverifiable risk.
                        if verified_via_opportunity < total_execs:
                            risk_respected = False
                else:
                    risk_respected = True

                plan_compliant = bias_respected and strat_respected and risk_respected

            # 6. Quadrant Assignment
            # Good process: plan_compliant is True
            # Good outcome: Forecast direction matched or profitable/clean session
            good_outcome = (tape_summary.quality_state in ("CLEAN", "SCHEDULED_SHORT_SESSION"))
            if scored and brier_loss is not None and brier_loss > 0.50:
                good_outcome = False
                
            if plan_compliant and good_outcome:
                quadrant = "GOOD_PROCESS_GOOD_OUTCOME"
            elif plan_compliant and not good_outcome:
                quadrant = "GOOD_PROCESS_BAD_OUTCOME"
            elif not plan_compliant and good_outcome:
                quadrant = "BAD_PROCESS_GOOD_OUTCOME"
            else:
                quadrant = "BAD_PROCESS_BAD_OUTCOME"
                
            return DailyProcessDeltaScorecard(
                session_date=session_date,
                ticker=ticker,
                plan=plan_summary,
                forecast=forecast_summary,
                execution=exec_summary,
                tape=tape_summary,
                plan_compliant=plan_compliant,
                bias_direction_respected=bias_respected,
                permitted_strategies_respected=strat_respected,
                risk_budget_respected=risk_respected,
                process_outcome_quadrant=quadrant,
                reconciliation_timestamp_utc=now_iso_utc()
            )


# Backwards-compatible alias
ProcessDeltaSummary = DailyProcessDeltaScorecard
