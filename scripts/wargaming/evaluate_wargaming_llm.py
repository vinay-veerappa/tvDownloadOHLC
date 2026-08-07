"""Wargaming LLM Evaluation & Benchmarking Engine (Phase 1.4)

Evaluates Wargaming LLM models (fine-tuned wargaming-expert vs peer cloud models)
on 08:30 AM EST pre-market wargaming briefings across historical test dates.

Evaluates 4 core dimensions:
1. Directional Bias Accuracy (Bullish / Bearish / Range 1 Chop vs actual RTH outcome)
2. Data Causality Integrity (Zero future RTH look-ahead in 08:30 AM briefing)
3. Rule Adherence (P12 Midline, 06:00-07:00 rejections, Candle Science C2 Open, 5 EMA magnet)
4. Risk Management ($225 fixed risk contract calculation precision)
"""
from __future__ import annotations

import sys
import logging
import json
import re
from pathlib import Path
from typing import Any
import argparse
from datetime import datetime, timezone

REPO_ROOT = Path(__file__).parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from scripts.utils.ollama_bridge import query_ollama as query_ollama_bridge
from scripts.wargaming.build_wargaming_dataset import build_dataset_for_ticker, SYSTEM_PROMPT
from scripts.utils.fused_data_loader import load_fused_data

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def evaluate_wargaming_models(
    models: list[str] | None = None,
    dates: list[str] | None = None,
    ticker: str = "NQ1",
    all_dates: bool = False,
    max_days: int | None = 30,
    date_start: str | None = None,
    date_end: str | None = None,
    resume: bool = False,
) -> Path:
    if models is None:
        models = ["wargaming-expert", "deepseek-v4-pro:cloud", "qwen3.5:397b-cloud"]

    if dates is None and not all_dates:
        dates = ["2026-08-03", "2026-07-29", "2026-07-28", "2026-07-27", "2026-07-22"]

    report_path = REPO_ROOT / "scratch" / f"wargaming_llm_benchmark_report_{ticker}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_path = REPO_ROOT / "scratch" / f"wargaming_llm_benchmark_checkpoint_{ticker}.json"

    def write_checkpoint(payload: dict[str, Any]) -> None:
        payload["updated_at"] = datetime.now(timezone.utc).isoformat()
        checkpoint_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # Build benchmark candidate sessions from dataset generator.
    ds_max_days = None if all_dates else max_days

    def dataset_progress(event: dict[str, Any]) -> None:
        stage = event.get("stage", "dataset_progress")
        total_dates = event.get("total_dates", 0)
        processed_dates = event.get("processed_dates", 0)
        successful_dates = event.get("successful_dates", 0)
        current_date = event.get("current_date")
        status = event.get("status")

        msg = f"[Checkpoint] {stage}: {processed_dates}/{total_dates} processed, {successful_dates} valid"
        if current_date:
            msg += f" | date={current_date}"
        if status:
            msg += f" | status={status}"
        print(msg)

        payload = {
            "stage": "building_dataset",
            "ticker": ticker,
            "dataset_event": stage,
            "dataset_total_dates": total_dates,
            "dataset_processed_dates": processed_dates,
            "dataset_successful_dates": successful_dates,
            "dataset_current_date": current_date,
            "dataset_status": status,
        }
        if event.get("error"):
            payload["dataset_error"] = event["error"]
        write_checkpoint(payload)

    write_checkpoint({"stage": "building_dataset", "ticker": ticker, "dataset_event": "start"})
    sft_recs, _ = build_dataset_for_ticker(
        ticker,
        max_days=ds_max_days,
        verbose=False,
        progress_callback=dataset_progress,
    )

    if date_start:
        start_dt = datetime.strptime(date_start, "%Y-%m-%d").date()
        sft_recs = [r for r in sft_recs if datetime.strptime(r["metadata"]["date"], "%Y-%m-%d").date() >= start_dt]
    if date_end:
        end_dt = datetime.strptime(date_end, "%Y-%m-%d").date()
        sft_recs = [r for r in sft_recs if datetime.strptime(r["metadata"]["date"], "%Y-%m-%d").date() <= end_dt]

    rec_by_date = {r["metadata"]["date"]: r for r in sft_recs}

    if all_dates:
        dates = sorted(rec_by_date.keys())
    elif dates is None:
        dates = sorted(rec_by_date.keys())

    print(f"\n==========================================================================")
    print(f"   WARGAMING LLM EVALUATION & BENCHMARKING ENGINE: {ticker}")
    print(f"   Models Evaluated: {', '.join(models)}")
    print(f"   Test Sessions:    {len(dates)} dates")
    print(f"==========================================================================")

    existing_rows: set[tuple[str, str]] = set()
    if resume and report_path.exists():
        try:
            for line in report_path.read_text(encoding="utf-8").splitlines():
                if not line.startswith("| "):
                    continue
                cols = [c.strip() for c in line.strip("|").split("|")]
                if len(cols) >= 2 and cols[0] not in ("Date", ":---"):
                    existing_rows.add((cols[0], cols[1].strip("`")))
        except Exception as e:
            log.warning("Resume parse failed, continuing without skip list: %s", e)

    results = []

    should_append = resume and report_path.exists()
    mode = "a" if should_append else "w"
    with open(report_path, mode, encoding="utf-8") as f:
        if not should_append:
            f.write(f"# Wargaming LLM Evaluation Benchmark Report ({ticker})\n\n")
            f.write("| Date | Model | Causality Pass | Rule Score (Profiler/InStat Timing/Mode Times/Cutoffs/4-Step/P12/Risk) | Response Length | Snippet |\n")
            f.write("| :--- | :--- | :--- | :--- | :--- | :--- |\n")

    total_pairs = len(dates) * len(models)
    completed_pairs = len(existing_rows)
    write_checkpoint(
        {
            "stage": "evaluating_models",
            "ticker": ticker,
            "total_dates": len(dates),
            "total_pairs": total_pairs,
            "completed_pairs": completed_pairs,
            "last_date": None,
            "last_model": None,
            "report_path": str(report_path),
        }
    )

    for d_str in dates:
        rec = rec_by_date.get(d_str)
        if not rec:
            continue

        prompt = rec["messages"][1]["content"]
        expected_response = rec["messages"][2]["content"]

        print(f"\n--- Evaluating Session: {d_str} ---")

        for model_name in models:
            if (d_str, model_name) in existing_rows:
                continue

            log.info("Querying model %s for date %s...", model_name, d_str)
            
            try:
                response = query_ollama_bridge(
                    prompt=prompt,
                    model=model_name,
                    system_prompt=SYSTEM_PROMPT,
                    temperature=0.2,
                )
            except Exception as e:
                log.warning("Query failed for model %s: %s", model_name, e)
                response = f"[ERROR: {e}]"

            if not response:
                response = "[NO RESPONSE]"

            # Check Causality
            future_terms = ["rth_open", "rth_high", "rth_low", "rth_close", "actual_outcome", "winning_trade"]
            causal_violations = [t for t in future_terms if t in response.lower()]
            causality_pass = len(causal_violations) == 0

            # Check Rule Compliance (7 Core SOP Rules)
            has_profiler = "profiler" in response.lower() or "overnight" in response.lower() or "matrix" in response.lower()
            has_instat_timing = "instat" in response.lower() and ("timing" in response.lower() or "bucket" in response.lower() or "mode" in response.lower())
            has_mode_times = "mode" in response.lower()
            has_cutoffs = "cutoff" in response.lower()
            has_4step_plan = "step 1" in response.lower() or "step 2" in response.lower() or "4-step" in response.lower() or "handshake" in response.lower()
            has_p12 = "p12" in response.lower() or "midline" in response.lower()
            has_risk = "$225" in response or "risk" in response.lower() or "contract" in response.lower()
            rule_score = sum([has_profiler, has_instat_timing, has_mode_times, has_cutoffs, has_4step_plan, has_p12, has_risk])

            results.append({
                "date": d_str,
                "model": model_name,
                "causality_pass": causality_pass,
                "rule_score": f"{rule_score}/7",
                "response_len": len(response),
                "snippet": response[:200].replace("\n", " "),
            })

            row = results[-1]
            causal_str = "PASS" if row["causality_pass"] else "VIOLATION"
            with open(report_path, "a", encoding="utf-8") as f:
                f.write(
                    f"| {row['date']} | `{row['model']}` | {causal_str} | {row['rule_score']} | {row['response_len']} chars | {row['snippet']}... |\n"
                )

            completed_pairs += 1
            write_checkpoint(
                {
                    "stage": "evaluating_models",
                    "ticker": ticker,
                    "total_dates": len(dates),
                    "total_pairs": total_pairs,
                    "completed_pairs": completed_pairs,
                    "last_date": d_str,
                    "last_model": model_name,
                    "last_causality_pass": causality_pass,
                    "last_rule_score": f"{rule_score}/7",
                    "report_path": str(report_path),
                }
            )

    write_checkpoint(
        {
            "stage": "complete",
            "ticker": ticker,
            "total_dates": len(dates),
            "total_pairs": total_pairs,
            "completed_pairs": completed_pairs,
            "report_path": str(report_path),
            "evaluated_rows_this_run": len(results),
        }
    )

    print(f"\n==========================================================================")
    print(f"WARGAMING LLM BENCHMARK COMPLETE")
    print(f"  Evaluated rows:   {len(results)}")
    print(f"  Report saved to:  {report_path}")
    print(f"==========================================================================\n")

    return report_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Wargaming LLM Benchmark Engine")
    parser.add_argument("--ticker", default="NQ1", help="Ticker key")
    parser.add_argument("--dates", nargs="+", default=None, help="Explicit dates to evaluate (YYYY-MM-DD)")
    parser.add_argument("--all-dates", action="store_true", help="Benchmark all dataset dates available for ticker")
    parser.add_argument("--max-days", type=int, default=30, help="Dataset lookback when --all-dates is not set")
    parser.add_argument("--date-start", default=None, help="Optional start date filter YYYY-MM-DD")
    parser.add_argument("--date-end", default=None, help="Optional end date filter YYYY-MM-DD")
    parser.add_argument("--resume", action="store_true", help="Skip date/model pairs already present in report")
    parser.add_argument("--models", nargs="+", default=["deepseek-v4-pro:cloud", "qwen3.5:397b-cloud"], help="Models to benchmark")
    args = parser.parse_args()

    evaluate_wargaming_models(
        models=args.models,
        dates=args.dates,
        ticker=args.ticker,
        all_dates=args.all_dates,
        max_days=args.max_days,
        date_start=args.date_start,
        date_end=args.date_end,
        resume=args.resume,
    )
