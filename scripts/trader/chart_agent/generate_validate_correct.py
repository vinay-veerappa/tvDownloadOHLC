"""generate_validate_correct.py — the full chart agent loop.

Phase 5: Generate-Validate-Correct Loop.

Flow:
  1. GENERATE: Reasoner emits verdict from features + KB context
  2. VALIDATE: 3 blind vision analyses (Gemini reads chart, NO verdict context)
  3. COMPARE: Programmatic comparison of verdict vs vision analyses
  4. CORRECT: If disagreement, feed vision observations back to reasoner for re-evaluation
  5. RE-EMIT: Reasoner produces corrected verdict

Usage:
    python -m scripts.trader.chart_agent.generate_validate_correct --ticker ES1
    python -m scripts.trader.chart_agent.generate_validate_correct --ticker ES1 --model gemma4:31b-cloud
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)

_REPO = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(_REPO))

# Load .env
_env_file = _REPO / ".env"
if _env_file.exists():
    with open(_env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                if k not in os.environ:
                    os.environ[k] = v

from scripts.trader import _path_setup  # noqa: F401
from scripts.trader.chart_agent.reasoner import assemble_features, retrieve_kb_context, call_llm
from scripts.trader.chart_agent.gen_charts import generate_charts, _trading_days_from_data
from scripts.trader.chart_agent.blind_vision import run_blind_vision, compare_with_verdict
from scripts.utils.fused_data_loader import load_fused_data

PROMPT_DIR = Path(__file__).parent / "prompts"
VERDICT_DIR = _REPO / "data" / "vision" / "verdicts"
GVC_DIR = _REPO / "data" / "vision" / "gvc_results"
GVC_DIR.mkdir(parents=True, exist_ok=True)

# DST-aware timezone
from zoneinfo import ZoneInfo
ET_TZ = ZoneInfo("America/New_York")


# ═══════════════════════════════════════════════════════════════════════
#  CORRECTION PROMPT — feeds vision observations back to reasoner
# ═══════════════════════════════════════════════════════════════════════

CORRECTION_PROMPT_TEMPLATE = """# ICT Daily Bias Verdict — CORRECTION REQUEST

You previously generated the following verdict for {ticker}:

--- ORIGINAL VERDICT ---
{VERDICT}
--- END VERDICT ---

Three independent vision analyses were performed on the chart image.
These analyses were BLIND — they did NOT see your verdict. They read the chart independently.

## BULLISH CASE (from vision):
{BULLISH_ANALYSIS}

## BEARISH CASE (from vision):
{BEARISH_ANALYSIS}

## NEUTRAL OBSERVATIONS (from vision):
{NEUTRAL_ANALYSIS}

## Your Task

Review your original verdict against these independent vision observations. Consider:

1. Did the vision analyses identify levels or patterns you missed?
2. Does the bullish case from vision challenge your bearish call (or vice versa)?
3. Are there discrepancies in the session ranges or level status?
4. Should you change your bias, alternate_scenario, or readiness?

If your original verdict is still correct, re-emit it unchanged with a note explaining why.
If corrections are needed, re-emit the FULL verdict with corrections applied.

Output ONLY the corrected YAML verdict. No preamble."""

# ═══════════════════════════════════════════════════════════════════════
#  The full loop
# ═══════════════════════════════════════════════════════════════════════

async def run_gvc_loop(
    ticker: str,
    model: str | None = None,
    chart_path: str | None = None,
) -> dict:
    """Run the full Generate-Validate-Correct loop.

    Args:
        ticker: e.g. "ES1"
        model: LLM model for reasoner
        chart_path: path to chart image (if None, generates one)

    Returns:
        dict with all results: verdict, blind_vision, comparison, corrected_verdict
    """
    from scripts.trader.chart_agent.reasoner import emit_verdict, DEFAULT_MODEL
    from scripts.trader.config_loader import get_llm_config

    _cfg = get_llm_config()
    use_model = model or _cfg.get("default_trader_model") or _cfg.get("default_model") or "gemma4:31b-cloud"

    # ── Step 1: Generate chart ────────────────────────────────────────
    if chart_path is None:
        df = load_fused_data(ticker, timeframe="1m", require_historical=False)
        dates = _trading_days_from_data(df, 1)
        if not dates:
            raise RuntimeError(f"No data with substantial rows for {ticker}")
        target_date = dates[0]
        charts = generate_charts([ticker], dates=[target_date], dpi=150)
        if not charts:
            raise RuntimeError("Chart generation failed")
        chart_path = str(charts[0])

    # Use the small version for vision (faster)
    small_chart = chart_path.replace("_daily_context.png", "_small.png")
    if not os.path.exists(small_chart):
        small_chart = chart_path

    log.info("="*60)
    log.info("GVC LOOP: %s | model=%s | chart=%s", ticker, use_model, chart_path)
    log.info("="*60)

    # ── Step 2: GENERATE — reasoner emits verdict ─────────────────────
    log.info("STEP 1: GENERATE — Reasoner emitting verdict...")
    features = assemble_features(ticker)
    kb_context = retrieve_kb_context(features)
    prompt_path = PROMPT_DIR / "daily_bias_reasoner.md"
    prompt = prompt_path.read_text(encoding="utf-8")
    prompt = prompt.replace("{FEATURES_BLOCK}", features).replace("{KB_CONTEXT_BLOCK}", kb_context)
    verdict = call_llm(prompt, use_model)
    log.info("  Verdict: %d chars", len(verdict))

    # ── Step 3: VALIDATE — blind vision analyses ──────────────────────
    log.info("STEP 2: VALIDATE — 3 blind vision analyses...")
    blind_results = await run_blind_vision(small_chart)
    for k, v in blind_results.items():
        status = "OK" if not v.startswith("ERROR") else "FAILED"
        log.info("  %s: %s (%d chars)", k, status, len(v))

    # ── Step 4: COMPARE ───────────────────────────────────────────────
    log.info("STEP 3: COMPARE — checking agreement...")
    comparison = compare_with_verdict(blind_results, verdict)
    log.info("  Verdict bias: %s", comparison["verdict_bias"])
    log.info("  Bullish analysis: %s", "present" if comparison["bullish_analysis_present"] else "missing")
    log.info("  Bearish analysis: %s", "present" if comparison["bearish_analysis_present"] else "missing")
    log.info("  Neutral analysis: %s", "present" if comparison["neutral_analysis_present"] else "missing")

    # ── Step 5: CORRECT — feed vision back to reasoner ────────────────
    log.info("STEP 4: CORRECT — feeding vision observations back to reasoner...")
    correction_prompt = CORRECTION_PROMPT_TEMPLATE.replace("{ticker}", ticker)
    correction_prompt = correction_prompt.replace("{VERDICT}", verdict)
    correction_prompt = correction_prompt.replace("{BULLISH_ANALYSIS}", blind_results.get("bullish", "N/A"))
    correction_prompt = correction_prompt.replace("{BEARISH_ANALYSIS}", blind_results.get("bearish", "N/A"))
    correction_prompt = correction_prompt.replace("{NEUTRAL_ANALYSIS}", blind_results.get("neutral", "N/A"))

    corrected_verdict = call_llm(correction_prompt, use_model)
    log.info("  Corrected verdict: %d chars", len(corrected_verdict))

    # ── Save all results ──────────────────────────────────────────────
    date_str = datetime.now(ET_TZ).strftime("%Y-%m-%d")
    result = {
        "ticker": ticker,
        "date": date_str,
        "model": use_model,
        "chart": chart_path,
        "timestamp": datetime.now(ET_TZ).isoformat(),
        "original_verdict": verdict,
        "blind_vision": blind_results,
        "comparison": comparison,
        "corrected_verdict": corrected_verdict,
    }

    save_path = GVC_DIR / f"{ticker}_{date_str}_gvc.json"
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    log.info("Saved GVC result to %s", save_path)

    # Also save verdicts individually
    VERDICT_DIR.mkdir(parents=True, exist_ok=True)
    (VERDICT_DIR / f"{ticker}_{date_str}_gvc_original.yaml").write_text(verdict, encoding="utf-8")
    (VERDICT_DIR / f"{ticker}_{date_str}_gvc_corrected.yaml").write_text(corrected_verdict, encoding="utf-8")

    return result


def _print_summary(result: dict):
    """Print a concise summary of the GVC loop."""
    print("\n" + "=" * 60)
    print(f"  GVC LOOP: {result['ticker']} | {result['date']}")
    print("=" * 60)

    # Original bias
    for line in result["original_verdict"].split("\n"):
        if line.strip().startswith("bias:"):
            print(f"  Original bias: {line.strip()}")
            break

    # Corrected bias
    for line in result["corrected_verdict"].split("\n"):
        if line.strip().startswith("bias:"):
            print(f"  Corrected bias: {line.strip()}")
            break

    # Vision
    comp = result["comparison"]
    print(f"\n  Vision analyses:")
    print(f"    Bullish: {'present' if comp['bullish_analysis_present'] else 'missing'}")
    print(f"    Bearish: {'present' if comp['bearish_analysis_present'] else 'missing'}")
    print(f"    Neutral: {'present' if comp['neutral_analysis_present'] else 'missing'}")

    print(f"\n  Results: {GVC_DIR}")
    print("=" * 60)


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    ap = argparse.ArgumentParser(description="Generate-Validate-Correct loop")
    ap.add_argument("--ticker", default="ES1", help="Ticker symbol")
    ap.add_argument("--model", default=None, help="LLM model")
    ap.add_argument("--chart", default=None, help="Chart image path (auto-generated if not provided)")
    args = ap.parse_args()

    result = asyncio.run(run_gvc_loop(args.ticker, model=args.model, chart_path=args.chart))
    _print_summary(result)


if __name__ == "__main__":
    main()