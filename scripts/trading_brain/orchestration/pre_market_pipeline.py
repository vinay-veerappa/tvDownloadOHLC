"""Daily Operational Orchestration Pipelines (Workstreams 1.1 & 1.2).

WS-1.1 Pre-Market Pipeline (run at ~08:40 ET, before the 08:45 cutoff):
  1. Builds a deterministic input manifest (live storage parquet + strategy artifacts).
  2. Creates a sealed forecast run via ForecastRegistrar.create_forecast_run (fail-closed on cutoff).
  3. Generates the wargame data (generate_daily_wargame) and commits the forecast snapshot payload.
  4. Snapshots the pre-market plan into plan_snapshots via PlanAdapter (EX_ANTE before cutoff).

WS-1.2 Post-Market Pipeline (run at ~16:15 ET):
  1. Extracts mechanical tape actuals (TapeMetricsExtractor.extract_and_record).
  2. Ingests broker executions & interventions from ingest files (NT8BrokerAdapter).
  3. Derives signal dispositions (OpportunityLogger.derive_dispositions).
  4. Executes the 4-way reconciliation quadrant (DailyProcessDeltaReconciler).
  5. Persists markdown & JSON daily triage reports (DailyTriageReportGenerator).

Both runners are plain CLI entry points - scheduling (Task Scheduler / cron) is external.
"""

import argparse
import hashlib
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from scripts.trading_brain.db.connection import REPO_ROOT
from scripts.trading_brain.forecast.forecast_registrar import (
    ForecastRegistrar,
    ForecastSnapshotPayload,
)
from scripts.trading_brain.plans.plan_adapter import PlanAdapter, PlanContext

log = logging.getLogger(__name__)

STRATEGY_ARTIFACTS_DIR = REPO_ROOT / "scripts" / "trading_brain" / "strategies" / "artifacts"
DEFAULT_MODEL_VERSION_ID = "MOD_WARGAME_DIRECTIONAL_V0"


# ---------------------------------------------------------------------------
# Provenance helpers
# ---------------------------------------------------------------------------

def compute_git_hash() -> str:
    """Returns the current repository commit hash; falls back to a stable unknown marker."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10, cwd=str(REPO_ROOT)
        )
        if out.returncode == 0:
            return f"git:{out.stdout.strip()[:12]}"
    except Exception as e:
        log.warning(f"git rev-parse failed: {e}")
    return "git:UNKNOWN"


def compute_config_hash() -> str:
    """Hashes the frozen strategy artifact directory contents (sorted, deterministic)."""
    h = hashlib.sha256()
    for f in sorted(STRATEGY_ARTIFACTS_DIR.glob("*.json")):
        h.update(f.name.encode("utf-8"))
        h.update(f.read_bytes())
    return f"sha256:{h.hexdigest()[:16]}"


def _hash_file(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


# ---------------------------------------------------------------------------
# WS-1.1: Pre-Market Pipeline
# ---------------------------------------------------------------------------

def build_input_manifest(ticker: str, session_date: str, cutoff_time_et: str) -> List[Dict[str, Any]]:
    """Builds the pre-market input manifest with per-input content hashes.

    Includes every data source the wargame computes from: live storage 1m parquet and the
    frozen strategy artifact registry. Fail-closed: any missing required input aborts
    registration. The live storage entry is sliced as-of the session cutoff, hashed, and
    its max_timestamp_utc is derived from the actual selected records.
    """
    import pandas as pd
    from scripts.utils.live_storage_resolver import get_session_slice_manifest, get_live_storage_path
    from scripts.utils.market_calendar import get_session_cutoff_utc

    manifest: List[Dict[str, Any]] = []

    # Live storage: slice as-of cutoff, hash the slice, derive real max timestamp.
    cutoff_dt = get_session_cutoff_utc(session_date, cutoff_time_et)
    cutoff_ts = pd.Timestamp(cutoff_dt)
    if cutoff_ts.tz is None:
        cutoff_ts = cutoff_ts.tz_localize("UTC")
    else:
        cutoff_ts = cutoff_ts.tz_convert("UTC")
    live_entry = get_session_slice_manifest(ticker, session_date, cutoff_ts)
    manifest.append(live_entry)

    # Strategy artifacts: frozen files. Hash the whole file; max_timestamp is the cutoff
    # because artifacts are version-controlled and not allowed to mutate post-cutoff.
    cutoff_iso = cutoff_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    for artifact in sorted(STRATEGY_ARTIFACTS_DIR.glob("*.json")):
        manifest.append({
            "provider_name": f"STRATEGY_ARTIFACT_{artifact.stem.upper()}",
            "data_type": "STRATEGY_DEFINITION",
            "max_timestamp_utc": cutoff_iso,
            "content_hash": _hash_file(artifact),
        })

    return manifest


def wargame_data_to_forecast_payload(
    wargame_data: Dict[str, Any],
    model_version_id: str,
    git_hash: str,
    config_hash: str,
    forecast_run_id: str
) -> ForecastSnapshotPayload:
    """Maps wargame directional output to a forecast snapshot payload.

    Current engine honesty: the trajectory engine produces directional scenario
    probabilities (SF/LF/LT/ST conditional elimination tree), NOT calibrated 5-class
    day-type probabilities (R1/R2/DNP/DWP/ROTATIONAL_CHOP). To avoid fabricating a
    distribution (the zero-fabrication doctrine from the legacy importer review),
    the pipeline registers an ABSTAIN forecast unless a calibrated 5-class model is
    configured via `probabilities_json`. Direction/level content (P12 vector, Candle
    Science targets, expected moves) is still persisted as forecast metadata.
    """
    p12 = wargame_data.get("p12", {})
    cs = wargame_data.get("candle_science", {}) or {}
    spot = float(wargame_data.get("spot_price", 0.0))

    cs_high = cs.get("bull", {}).get("p70")
    cs_low = cs.get("bear", {}).get("p70")
    cs_high_lvl = spot * (1.0 + float(cs_high) / 100.0) if cs_high is not None else None
    cs_low_lvl = spot * (1.0 + float(cs_low) / 100.0) if cs_low is not None else None

    # Weekly expected move half-width as levels, if provided by the weekly outlook engine.
    expected_move_high = None
    expected_move_low = None
    weekly_em = (wargame_data.get("weekly_outlook") or {}).get("expected_move_pct") or (
        wargame_data.get("weekly_outlook") or {}
    ).get("expected_moves") or {}
    if isinstance(weekly_em, dict):
        em_pct = weekly_em.get("this_friday") or weekly_em.get("weekly_pct")
        if em_pct is not None:
            em = spot * (float(em_pct) / 100.0)
            expected_move_high, expected_move_low = spot + em, spot - em

    payload = ForecastSnapshotPayload(
        forecast_run_id=forecast_run_id,
        predicted_bias=p12.get("bias"),
        p12_vector_direction=p12.get("bias"),
        p12_equilibrium_level=p12.get("mid"),
        candle_science_target_high=cs_high_lvl,
        candle_science_target_low=cs_low_lvl,
        expected_move_high=expected_move_high,
        expected_move_low=expected_move_low,
        git_hash=git_hash,
        config_hash=config_hash,
        # Zero-fabrication: no calibrated 5-class model registered yet -> abstain.
        abstain_flag=True,
        abstain_reason="NO_CALIBRATED_5CLASS_MODEL_V0_DIRECTIONAL_LEVELS_ONLY",
    )
    return payload


def wargame_data_to_plan_context(
    wargame_data: Dict[str, Any],
    playbook_markdown: str,
    session_date: str,
    cutoff_time_et: str,
    source_system: str = "MARKDOWN_CLI"
) -> PlanContext:
    """Maps the generated wargame playbook into a declarative pre-market PlanContext.

    The plan text is the verbatim generated playbook; bias comes from the P12 vector;
    permitted strategies from detected signature setups; risk budget from the pack
    stop ceiling (bps). The adapter stamps provenance EX_ANTE only if received
    before the calendar cutoff.
    """
    p12 = wargame_data.get("p12", {})
    pack = wargame_data.get("pack_trading", {})
    sig = wargame_data.get("signature_setups", {}) or {}

    detected = sig.get("setups_detected") or sig.get("detected_setups") or []
    permitted = [
        s["strategy_family"] if isinstance(s, dict) else str(s)
        for s in (detected if isinstance(detected, list) else [])
    ] or ["ALN_LPEU", "FIRECRACKER", "GOALPOST_BB", "P12_MID"]

    max_risk_bps = float(pack.get("stop_ceiling_bps") or 15.0)
    cutoff_iso = f"{session_date}T{cutoff_time_et}:00Z"

    scenarios = {
        "p12_bias": p12.get("bias"),
        "p12_mid": p12.get("mid"),
        "session_alignment": (wargame_data.get("sessions") or {}).get("alignment"),
        "elimination_state": (wargame_data.get("trajectory_engine") or {}).get("state"),
        "pack_brackets_bps": {
            "cover_the_queen": pack.get("cover_the_queen_bps"),
            "runner": pack.get("runner_bps"),
            "stop_ceiling": pack.get("stop_ceiling_bps"),
        },
   }
    invalidation = {
        "p12_mid_violation": p12.get("mid"),
        "long_stop_reference": pack.get("long_sl"),
        "short_stop_reference": pack.get("short_sl"),
    }

    return PlanContext(
        session_date=session_date,
        ticker=wargame_data.get("ticker", "NQ1"),
        preparation_cutoff_utc=cutoff_iso,
        verbatim_plan_text=playbook_markdown,
        primary_bias=p12.get("bias") or "NEUTRAL",
        wargamed_scenarios=scenarios,
        invalidation_levels=invalidation,
        max_intended_risk_bps=max_risk_bps,
        permitted_strategies=permitted,
        source_system=source_system,
    )


def run_pre_market_pipeline(
    ticker: str = "NQ1",
    session_date: Optional[str] = None,
    cutoff_time_et: str = "08:45",
    grace_period_sec: int = 300,
    skip_plan_snapshot: bool = False,
    db_path: Optional[Any] = None,
) -> Dict[str, Any]:
    """Executes the full WS-1.1 pre-market sequence. Fail-closed on any cutoff violation."""
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo
    from scripts.utils.market_calendar import to_iso_utc

    if session_date is None:
        session_date = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")

    # 0. Provenance stamps
    git_hash = compute_git_hash()
    config_hash = compute_config_hash()

    # 1. Generate wargame data at current clock (pre-cutoff by contract)
    from datetime import date as _date
    from scripts.wargaming.generate_daily_wargame import generate_wargame_data, format_wargame_markdown
    wargame_data = generate_wargame_data(
        ticker=ticker,
        target_date=_date.fromisoformat(session_date),
        cutoff_time_str=cutoff_time_et,
    )
    playbook_md = format_wargame_markdown(wargame_data)

    # 2. Seal input manifest BEFORE cutoff (create_forecast_run enforces; raises after)
    manifest = build_input_manifest(ticker, session_date, cutoff_time_et)
    run = ForecastRegistrar.create_forecast_run(
        session_date=session_date,
        ticker=ticker,
        model_version_id=DEFAULT_MODEL_VERSION_ID,
        input_manifest=manifest,
        commit_grace_period_sec=grace_period_sec,
        cutoff_time_et_str=f"{cutoff_time_et}:00" if len(cutoff_time_et) == 5 else cutoff_time_et,
        db_path=db_path,
    )

    # 3. Commit forecast snapshot payload
    payload = wargame_data_to_forecast_payload(
        wargame_data,
        model_version_id=DEFAULT_MODEL_VERSION_ID,
        git_hash=git_hash,
        config_hash=config_hash,
        forecast_run_id=run.forecast_run_id,
    )
    commit = ForecastRegistrar.commit_forecast_run(run.forecast_run_id, payload, db_path=db_path)

    # 4. Snapshot the generated playbook as the declared pre-market plan
    plan_result: Optional[Dict[str, Any]] = None
    if not skip_plan_snapshot:
        plan_ctx = wargame_data_to_plan_context(
            wargame_data, playbook_md, session_date, cutoff_time_et
        )
        saved_plan_id = PlanAdapter.save_plan_snapshot(plan_ctx, db_path=db_path)
        plan_result = {
            "plan_snapshot_id": saved_plan_id,
            "provenance_class": plan_ctx.provenance_class,
            "primary_bias": plan_ctx.primary_bias,
        }

    pipeline_result = {
        "pipeline": "PRE_MARKET_V1",
        "session_date": session_date,
        "ticker": ticker,
        "forecast_run_id": run.forecast_run_id,
        "forecast_id": commit.forecast_id,
        "forecast_mode": commit.forecast_mode,
        "git_hash": git_hash,
        "config_hash": config_hash,
        "manifest_inputs": len(manifest),
        "plan": plan_result,
    }
    log.info(f"[WS-1.1] Pre-market pipeline complete: {json.dumps(pipeline_result, default=str)}")
    return pipeline_result

# ---------------------------------------------------------------------------
# WS-1.2: Post-Market Pipeline
# ---------------------------------------------------------------------------

def _load_json_records(path: Path) -> List[Dict[str, Any]]:
    """Loads a JSON file containing either an array of records or {"records": [...]}."""
    content = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(content, list):
        return content
    if isinstance(content, dict) and "records" in content:
        return content["records"]
    raise ValueError(f"Ingest file {path} must be a JSON array or {{'records': [...]}}")


def run_post_market_pipeline(
    ticker: str = "NQ1",
    session_date: Optional[str] = None,
    executions_file: Optional[Union[str, Path]] = None,
    interventions_file: Optional[Union[str, Path]] = None,
    account_id: str = "PRIMARY",
    skip_tape: bool = False,
    db_path: Optional[Any] = None,
) -> Dict[str, Any]:
    """Executes the full WS-1.2 post-market sequence at 16:15 ET.

    Fills/interventions are ingested from JSON ingest files (NT8 bridge export or MCP
    dump). Missing ingest files are tolerated (capture-only day) but logged. Tape
    extraction failure on a live session is a hard error - outcome evidence cannot be
    fabricated or skipped silently.
    """
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from scripts.trading_brain.evaluation.daily_process_delta import DailyProcessDeltaReconciler
    from scripts.trading_brain.guard.deviation_annotator import DeviationAnnotator
    from scripts.trading_brain.ingest.nt8_broker_adapter import NT8BrokerAdapter
    from scripts.trading_brain.reports.daily_triage_report import DailyTriageReportGenerator
    from scripts.trading_brain.signals.opportunity_logger import OpportunityLogger
    from scripts.trading_brain.tape.tape_extractor import TapeMetricsExtractor

    if session_date is None:
        session_date = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")

    result: Dict[str, Any] = {
        "pipeline": "POST_MARKET_V1",
        "session_date": session_date,
        "ticker": ticker,
        "steps": {},
    }

    # 1. Tape actuals
    if not skip_tape:
        tape = TapeMetricsExtractor.extract_and_record(
            session_date=session_date, ticker=ticker, db_path=db_path
        )
        result["steps"]["tape_actuals"] = {
            "actual_id": tape.actual_id,
            "revision_seq": tape.revision_seq,
            "day_type": tape.day_type_classification,
            "quality_state": tape.quality_state,
            "range_bps": round(tape.session_range_bps, 2),
        }

    # 2. Broker fills & interventions (optional files)
    if executions_file is not None:
        fills = _load_json_records(Path(executions_file))
        ingest_result = NT8BrokerAdapter.ingest_fills(fills=fills, account_id=account_id, db_path=db_path)
        result["steps"]["execution_ingest"] = ingest_result
    if interventions_file is not None:
        interventions = _load_json_records(Path(interventions_file))
        inv_result = NT8BrokerAdapter.ingest_interventions(interventions=interventions, db_path=db_path)
        result["steps"]["intervention_ingest"] = inv_result

    # 3. Mechanical dispositions
    disp = OpportunityLogger.derive_dispositions(session_date, ticker, db_path=db_path)
    result["steps"]["dispositions"] = disp

    # 4. Deviation annotation for any fills that were not already annotated in step 2
    if executions_file is None:
        ann = annotate_executions_for_session(session_date, ticker, account_id=account_id, db_path=db_path)
        result["steps"]["deviation_annotation_backfill"] = ann
    else:
        # Re-run annotation in execution-timestamp order with running position awareness
        ann = annotate_executions_for_session(session_date, ticker, account_id=account_id, db_path=db_path)
        result["steps"]["deviation_annotation"] = ann

    # 5. 4-way reconciliation
    summary = DailyProcessDeltaReconciler.reconcile_session(session_date, ticker, db_path=db_path)
    result["steps"]["reconciliation"] = {
        "plan_found": summary.plan.plan_found,
        "forecast_found": summary.forecast.forecast_found,
        "tape_found": summary.tape.tape_found,
        "process_outcome_quadrant": summary.process_outcome_quadrant,
        "plan_compliant": summary.plan_compliant,
        "risk_budget_respected": summary.risk_budget_respected,
    }

    # 6. Triage report persistence
    md, json_report = DailyTriageReportGenerator.generate_report(session_date, ticker, db_path=db_path)
    result["steps"]["report"] = {
        "markdown_bytes": len(md),
        "json_keys": list(json_report.keys())[:8] if isinstance(json_report, dict) else None,
    }
    result["scorecard"] = json_report

    log.info(f"[WS-1.2] Post-market pipeline complete for {session_date} {ticker}")
    return result


def annotate_executions_for_session(
    session_date: str,
    ticker: str,
    account_id: str = "PRIMARY",
    db_path: Optional[Any] = None
) -> Dict[str, Any]:
    """Backfill DeviationAnnotator evaluations for all execution_events lacking one.

    This is exposed as a reusable helper so the post-market pipeline, ad-hoc audits,
    and test fixtures can all use the same position-aware evaluation path.
    """
    from scripts.trading_brain.db.connection import get_db_connection
    from scripts.trading_brain.guard.deviation_annotator import DeviationAnnotator

    evaluated = 0
    findings = 0
    unannotated = []
    with get_db_connection(db_path) as conn:
        cur = conn.execute(
            """
            SELECT e.* FROM execution_events e
            WHERE e.session_date = ? AND e.ticker = ? AND e.account_id = ?
              AND NOT EXISTS (
                SELECT 1 FROM intervention_events i
                WHERE i.source_event_id = e.execution_id
                  AND i.producer = 'PYTHON_DEVIATION_ANNOTATOR'
              )
            ORDER BY e.event_timestamp_utc ASC;
            """,
            (session_date, ticker, account_id),
        )
        unannotated = [dict(row) for row in cur.fetchall()]

    running_position = 0
    for exec_row in unannotated:
        qty = int(exec_row.get("quantity", 1))
        action = str(exec_row.get("order_action", "")).upper()
        net_before = running_position
        # Update running position after evaluating so the NEXT fill sees the pre-fill position.
        ann_ids = DeviationAnnotator.evaluate_execution(
            exec_row,
            current_net_position_before_fill=net_before,
            db_path=db_path,
        )
        if action in ("BUY", "LONG"):
            running_position += qty
        elif action in ("SELL", "SELL_SHORT", "SHORT"):
            running_position -= qty
        evaluated += 1
        findings += len(ann_ids)

    return {"evaluated": evaluated, "findings": findings, "final_net_position": running_position}


# ---------------------------------------------------------------------------
# CLI entry points
# ---------------------------------------------------------------------------

def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="Trading Brain Daily Pipelines (WS-1.1 / WS-1.2)")
    parser.add_argument("--mode", choices=["premarket", "postmarket"], required=True)
    parser.add_argument("--ticker", default="NQ1")
    parser.add_argument("--date", default=None, help="Session date YYYY-MM-DD (default: today ET)")
    parser.add_argument("--cutoff", default="08:45", help="Pre-market cutoff time HH:MM ET")
    parser.add_argument("--grace", type=int, default=300, help="Commit grace period seconds")
    parser.add_argument("--executions-file", default=None, help="JSON file of broker fills (postmarket)")
    parser.add_argument("--interventions-file", default=None, help="JSON file of interventions (postmarket)")
    parser.add_argument("--account", default="PRIMARY")
    parser.add_argument("--skip-plan-snapshot", action="store_true")
    parser.add_argument("--skip-tape", action="store_true")
    parser.add_argument("--db", default=None)
    args = parser.parse_args()

    if args.mode == "premarket":
        result = run_pre_market_pipeline(
            ticker=args.ticker,
            session_date=args.date,
            cutoff_time_et=args.cutoff,
            grace_period_sec=args.grace,
            skip_plan_snapshot=args.skip_plan_snapshot,
            db_path=args.db,
        )
    else:
        result = run_post_market_pipeline(
            ticker=args.ticker,
            session_date=args.date,
            executions_file=args.executions_file,
            interventions_file=args.interventions_file,
            account_id=args.account,
            skip_tape=args.skip_tape,
            db_path=args.db,
        )

    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
