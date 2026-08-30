"""WS-4 Web Dashboard Bridge (Milestone 4.2-4.5).

Read-only JSON projections of the canonical Trading Brain ledger for the Next.js
dashboard, plus delegated write operations for the Review Queue (Milestone 4.5).
Every handler returns JSON-serializable dicts; every write goes through the
existing governance services (CatalogRouter.transition_review_state) so the
ledger's trust boundaries (ADR-024) are never bypassed by the web layer.

CLI contract (invoked by Next API routes via `python -m`):
    python -m scripts.trading_brain.web_web_bridge <handler> [--arg value ...]

Handlers:
    process_delta       - 4-way reconciliation scorecard for a session
    unmatched_links     - open unmatched links + catalog triage queue
    review              - POST-like write: transition_review_state (catalog)
    review_unmatched    - write: resolve an unmatched link
    drill_next          - generate the next blinded drill context (no answers)
    drill_submit        - commit-before-reveal evaluation (DrillDeclaration)
    governance          - model_versions + deployment events + shadow findings
    calibration         - latest calibration metrics for a model (reliability bins)
    walk_forward        - latest WalkForwardEvaluation rows for a model
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from scripts.trading_brain.db.connection import get_db_connection, resolve_db_path
from scripts.utils.market_calendar import now_iso_utc


def _row_to_dict(row) -> Dict[str, Any]:
    return {k: row[k] for k in row.keys()}


def _rows(conn, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
    return [_row_to_dict(r) for r in conn.execute(query, params).fetchall()]


# ---------------------------------------------------------------------------
# 4.2 Daily Process Delta Scorecard
# ---------------------------------------------------------------------------
def handle_process_delta(args: argparse.Namespace) -> Dict[str, Any]:
    from scripts.trading_brain.evaluation.daily_process_delta import DailyProcessDeltaReconciler

    scorecard = DailyProcessDeltaReconciler.reconcile_session(
        session_date=args.session_date, ticker=args.ticker, db_path=_db(args)
    )
    s = scorecard
    return {
        "session_date": s.session_date,
        "ticker": s.ticker,
        "plan_compliant": s.plan_compliant,
        "bias_direction_respected": s.bias_direction_respected,
        "permitted_strategies_respected": s.permitted_strategies_respected,
        "risk_budget_respected": s.risk_budget_respected,
        "risk_assessment_state": s.risk_assessment_state,
        "process_outcome_quadrant": s.process_outcome_quadrant,
        "reconciliation_timestamp_utc": s.reconciliation_timestamp_utc,
        "plan": {
            "plan_found": s.plan.plan_found,
            "plan_snapshot_id": s.plan.plan_snapshot_id,
            "provenance_class": s.plan.provenance_class,
            "primary_bias": s.plan.primary_bias,
            "max_intended_risk_bps": s.plan.max_intended_risk_bps,
            "permitted_strategies": s.plan.permitted_strategies,
            "amendment_count": s.plan.amendment_count,
        },
        "forecast": {
            "forecast_found": s.forecast.forecast_found,
            "forecast_id": s.forecast.forecast_id,
            "forecast_mode": s.forecast.forecast_mode,
            "predicted_day_type": s.forecast.predicted_day_type,
            "predicted_bias": s.forecast.predicted_bias,
            "prob_distribution": s.forecast.prob_distribution,
            "abstain_flag": s.forecast.abstain_flag,
            "session_brier_loss": s.forecast.session_brier_loss,
            "session_log_loss": s.forecast.session_log_loss,
            "scored_for_calibration": s.forecast.scored_for_calibration,
        },
        "execution": {
            "total_opportunities": s.execution.total_opportunities,
            "executed_count": s.execution.executed_count,
            "passed_count": s.execution.passed_count,
            "missed_count": s.execution.missed_count,
            "offline_count": s.execution.offline_count,
            "pending_count": s.execution.pending_count,
            "unmatched_execution_count": s.execution.unmatched_execution_count,
            "total_executions": s.execution.total_executions,
            "interventions_count": s.execution.interventions_count,
            "net_position": s.execution.net_position,
            "avg_slippage_bps": s.execution.avg_slippage_bps,
            "opportunities": s.execution.opportunities,
        },
        "tape": {
            "tape_found": s.tape.tape_found,
            "actual_id": s.tape.actual_id,
            "session_open": s.tape.session_open,
            "session_high": s.tape.session_high,
            "session_low": s.tape.session_low,
            "session_close": s.tape.session_close,
            "rth_close": s.tape.rth_close,
            "session_range_bps": s.tape.session_range_bps,
            "realized_day_type": s.tape.realized_day_type,
            "quality_state": s.tape.quality_state,
        },
    }


# ---------------------------------------------------------------------------
# 4.5 Review Queue: unmatched links + catalog triage
# ---------------------------------------------------------------------------
def handle_unmatched_links(args: argparse.Namespace) -> Dict[str, Any]:
    db = _db(args)
    with get_db_connection(db) as conn:
        links = _rows(
            conn,
            "SELECT * FROM v_unmatched_links_open ORDER BY created_at_utc DESC LIMIT 200;",
            (),
        )
        # Catalog triage: active review state per item (trusted receipt when present,
        # event time for pre-v4 rows), resolved in SQL.
        items = _rows(
            conn,
            """
            SELECT i.information_id, i.evidence_class, i.time_orientation, i.source_type,
                   i.title, i.available_at_utc, i.received_at_utc,
                   a.active_review_state
            FROM information_items i
            LEFT JOIN (
                SELECT r.information_id,
                       r.review_state AS active_review_state,
                       ROW_NUMBER() OVER (
                           PARTITION BY r.information_id
                           ORDER BY COALESCE(r.received_at_utc, r.event_timestamp_utc, r.created_at_utc) DESC
                       ) AS rn
                FROM information_item_review_events r
            ) a ON a.information_id = i.information_id AND a.rn = 1
            ORDER BY i.received_at_utc DESC LIMIT 200;
            """,
            (),
        )
    return {"unmatched_links": links, "catalog_items": items}


def handle_review_unmatched(args: argparse.Namespace) -> Dict[str, Any]:
    """Resolves an unmatched link by appending a ledger row whose source facts are
    verified FROM execution_events (caller-claimed identity is not trusted)."""
    import uuid
    link_event_id = str(uuid.uuid4())
    with get_db_connection(_db(args)) as conn:
        exec_row = conn.execute(
            "SELECT execution_id, session_date, ticker FROM execution_events WHERE execution_id = ?;",
            (args.source_event_id,),
        ).fetchone()
        if not exec_row:
            raise ValueError(f"execution_id '{args.source_event_id}' not found in execution_events.")
        resolved_state = "RESOLVED" if args.candidate_event_id else "UNMATCHED"
        opp_exists = None
        if args.candidate_event_id:
            opp_row = conn.execute(
                "SELECT opportunity_id FROM signal_opportunities WHERE opportunity_id = ?;",
                (args.candidate_event_id,),
            ).fetchone()
            if not opp_row:
                raise ValueError(f"opportunity_id '{args.candidate_event_id}' not found in signal_opportunities.")
            opp_exists = args.candidate_event_id
        conn.execute(
            """
            INSERT INTO unmatched_link_events (
                link_event_id, execution_id, candidate_opportunity_ids_json,
                resolution_status, resolved_opportunity_id, resolution_notes,
                resolved_by, event_timestamp_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (link_event_id, args.source_event_id,
             json.dumps([opp_exists]) if opp_exists else "[]",
             resolved_state, opp_exists,
             args.reason or f"Resolved via WS-4.5 review queue by {args.actor}",
             args.actor, now_iso_utc()),
        )
    return {"link_event_id": link_event_id, "status": resolved_state}


def handle_review(args: argparse.Namespace) -> Dict[str, Any]:
    """Capability-honest triage write: normal review transitions use the trusted
    server clock (now receipt). This is a NORMAL application write, so receipt
    overrides require the migration capability and are refused otherwise."""
    from scripts.trading_brain.intake.catalog_router import CatalogRouter

    event_id = CatalogRouter.transition_review_state(
        information_id=args.information_id,
        review_state=args.review_state,
        reviewer=args.reviewer,
        review_notes=args.review_notes,
        db_path=_db(args),
    )
    return {"review_event_id": event_id, "information_id": args.information_id, "state": args.review_state}


# ---------------------------------------------------------------------------
# 4.3 Deliberate Practice Terminal
# ---------------------------------------------------------------------------
def handle_drill_next(args: argparse.Namespace) -> Dict[str, Any]:
    from scripts.trading_brain.practice.drill_engine import BlindedDrillEngine

    drill = BlindedDrillEngine.generate_blinded_drill(
        drill_type=args.drill_type or "RECOGNITION",
        dataset_split=args.dataset_split or "TRAINING",
        session_date=args.session_date,
        ticker=args.ticker,
        synthetic_mode=bool(args.synthetic) if hasattr(args, "synthetic") else False,
        db_path=_db(args),
    )
    return {
        "drill_id": drill.drill_id,
        "drill_type": drill.drill_type,
        "dataset_split": drill.dataset_split,
        "custody_mode": drill.custody_mode,
        # Custody token: HMAC over drill_id under the SERVER key - proof of minting,
        # NOT derived from the sealed answers, so echoing it does not leak ground
        # truth. The UI MUST relay it opaquely to drill_submit (ASSESSMENT paths
        # fail closed without it). It is never an answer key.
        "custody_token": drill.custody_token,
        "blinded_bars": drill.blinded_bars,
    }


def handle_drill_submit(args: argparse.Namespace) -> Dict[str, Any]:
    from scripts.trading_brain.practice.drill_engine import BlindedDrillEngine, DrillDeclaration

    declaration = DrillDeclaration(
        drill_id=args.drill_id,
        declared_bias=args.declared_bias,
        declared_setup=args.declared_setup,
        declared_entry_price=float(args.declared_entry_price),
        declared_stop_bps=float(args.declared_stop_bps),
        declared_target_bps=float(args.declared_target_bps),
        latency_ms=int(args.latency_ms) if args.latency_ms else None,
        custody_token=getattr(args, "custody_token", None),
    )
    feedback = BlindedDrillEngine.submit_and_evaluate(declaration, db_path=_db(args))
    return {
        "drill_id": feedback.drill_id,
        "process_adherence_score": feedback.process_adherence_score,
        "true_bias": feedback.true_bias,
        "true_setup": feedback.true_setup,
        "notes": getattr(feedback, "notes", None),
    }


# ---------------------------------------------------------------------------
# 4.4 Model Governance & Calibration Tab
# ---------------------------------------------------------------------------
def handle_governance(args: argparse.Namespace) -> Dict[str, Any]:
    """Registry rows + deployment events + shadow findings for the governance tab."""
    with get_db_connection(_db(args)) as conn:
        models = _rows(conn, "SELECT * FROM model_versions ORDER BY created_at_utc DESC LIMIT 100;", ())
        deployments = _rows(
            conn,
            """
            SELECT * FROM model_deployment_events
            ORDER BY event_timestamp_utc DESC LIMIT 200;
            """,
            (),
        )
        findings = _rows(
            conn,
            """
            SELECT finding_event_id, finding_id, model_version_id, pipeline_stage,
                   statistical_power, fdr_q_value, evaluation_result_json, actor,
                   event_timestamp_utc
            FROM candidate_finding_events
            ORDER BY event_timestamp_utc DESC LIMIT 200;
            """,
            (),
        )
        for f in findings:
            try:
                f["evaluation_result"] = json.loads(f.pop("evaluation_result_json", None) or "{}")
            except (TypeError, ValueError):
                f["evaluation_result"] = {}
    return {"models": models, "deployments": deployments, "shadow_findings": findings}


def handle_calibration(args: argparse.Namespace) -> Dict[str, Any]:
    """ECE reliability bins + BSS from the latest calibration run stored in-ledger."""
    with get_db_connection(_db(args)) as conn:
        row = conn.execute(
            """
            SELECT * FROM forecast_snapshots
            WHERE session_date = ? AND ticker = ?
            ORDER BY effective_cutoff_utc DESC LIMIT 1;
            """,
            (args.session_date, args.ticker),
        ).fetchone()
        if not row:
            return {"found": False}
        snap = _row_to_dict(row)
    return {"found": True, "forecast": snap,
            "note": "Reliability bins require a calibrated 5-class model; current forecasts are ABSTAIN (directional levels only)."}


def handle_walk_forward(args: argparse.Namespace) -> Dict[str, Any]:
    """Latest walk-forward evaluations (from candidate_finding_events + deployment events)."""
    with get_db_connection(_db(args)) as conn:
        wfs = _rows(
            conn,
            """
            SELECT finding_event_id, finding_id, model_version_id, pipeline_stage,
                   statistical_power, fdr_q_value, event_timestamp_utc
            FROM candidate_finding_events
            WHERE evaluation_result_json LIKE '%walk_forward%'
               OR evaluation_result_json LIKE '%aggregated_p%'
            ORDER BY event_timestamp_utc DESC LIMIT 100;
            """,
            (),
        )
    return {"walk_forward_findings": wfs}


def _db(args: argparse.Namespace):
    return resolve_db_path(args.db) if getattr(args, "db", None) else None


HANDLERS = {
    "process_delta": handle_process_delta,
    "unmatched_links": handle_unmatched_links,
    "review": handle_review,
    "review_unmatched": handle_review_unmatched,
    "drill_next": handle_drill_next,
    "drill_submit": handle_drill_submit,
    "governance": handle_governance,
    "calibration": handle_calibration,
    "walk_forward": handle_walk_forward,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="WS-4 Web Dashboard <-> Trading Brain Ledger Bridge")
    sub = parser.add_subparsers(dest="handler", required=True, help="Handler name (see module docstring).")

    p = sub.add_parser("process_delta"); p.add_argument("--session-date", required=True); p.add_argument("--ticker", required=True); p.add_argument("--db", default=None)

    p = sub.add_parser("unmatched_links"); p.add_argument("--session-date", default=None); p.add_argument("--db", default=None)

    p = sub.add_parser("review")
    p.add_argument("--information-id", required=True); p.add_argument("--review-state", required=True, choices=["ACCEPTED", "REJECTED", "QUARANTINED"])
    p.add_argument("--reviewer", required=True); p.add_argument("--review-notes", default=None); p.add_argument("--db", default=None)

    p = sub.add_parser("review_unmatched")
    p.add_argument("--source-event-id", required=True, help="execution_id, verified against execution_events")
    p.add_argument("--candidate-event-id", default=None, help="opportunity_id, verified against signal_opportunities")
    p.add_argument("--actor", required=True); p.add_argument("--reason", default=None); p.add_argument("--db", default=None)

    p = sub.add_parser("drill_next")
    p.add_argument("--drill-type", default="RECOGNITION"); p.add_argument("--dataset-split", default="TRAINING")
    p.add_argument("--session-date", required=True); p.add_argument("--ticker", required=True)
    p.add_argument("--synthetic", action="store_true"); p.add_argument("--db", default=None)

    p = sub.add_parser("drill_submit")
    p.add_argument("--drill-id", required=True); p.add_argument("--declared-bias", required=True)
    p.add_argument("--declared-setup", required=True); p.add_argument("--declared-entry-price", type=float, required=True)
    p.add_argument("--declared-stop-bps", type=float, required=True); p.add_argument("--declared-target-bps", type=float, required=True)
    p.add_argument("--latency-ms", type=int, default=None)
    p.add_argument("--custody-token", default=None, help="ASSESSMENT drills: the opaque token from drill_next (HMAC over drill_id; required fail-closed)")
    p.add_argument("--db", default=None)

    p = sub.add_parser("governance"); p.add_argument("--db", default=None)

    p = sub.add_parser("calibration"); p.add_argument("--session-date", required=True); p.add_argument("--ticker", required=True); p.add_argument("--db", default=None)

    p = sub.add_parser("walk_forward"); p.add_argument("--db", default=None)

    args = parser.parse_args()
    handler = HANDLERS.get(args.handler)
    if handler is None:
        print(json.dumps({"error": f"Unknown handler '{args.handler}'. Valid: {sorted(HANDLERS)}"}))
        sys.exit(2)
    try:
        result = handler(args)
    except Exception as exc:  # fail-closed: API routes translate non-zero exits to errors
        print(json.dumps({"error": str(exc), "handler": args.handler}))
        sys.exit(1)
    print(json.dumps(result, default=str))


if __name__ == "__main__":
    main()