"""Wargaming & Reengineering Fine-Tuning Dataset Generator (Phase 1.2 - Refactored)

Transforms pre-market profiler states and intraday RTH price action replays into
structured ChatML instruction-tuning datasets (JSONL format) for LLM fine-tuning.
Enforces zero look-ahead bias in the SFT completion and includes Master Rule Catalog flags.
Generates:
1. data/wargaming_sft.jsonl (Causal Pre-Market 08:30 Wargaming Task)
2. data/wargaming_postmortem.jsonl (EOD Reengineering Task)
"""
from __future__ import annotations

import sys
import logging
import json
import io
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any
import pandas as pd
import pytz
from datetime import datetime, time, timedelta

REPO_ROOT = Path(__file__).parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from scripts.utils.fused_data_loader import load_fused_data
from scripts.wargaming.pilot_single_day import run_pilot_wargame_and_reengineering, et_timestamp

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

ET = pytz.timezone("America/New_York")

SYSTEM_PROMPT = (
    "You are an expert futures market profiler and quantitative wargamer trained on Matt Mickey & Austin's reengineering framework.\n"
    "Daily classifications: R1 (4+ hourly touches of 09:30 open print), DNP (5+ hours trend without pullback), "
    "DWP (morning explosion, afternoon range), R2 (thigh gap reversion to 09:30 open).\n"
    "Overnight profiles: LT (Long True), LF (Long False), ST (Short True), SF (Short False).\n"
    "InStat = HOD/LOD printed within the profiler's expected 15-min mode window for the day's scenario. Compare actual overnight print time vs hod_mode/lod_mode bucket per outcome.\n"
    "Both-sides sweep 06:00-08:30: 99.26% probability both HOD and LOD form after 08:30 AM.\n"
    "Given pre-market 08:30 AM EST inputs, produce a strictly causal briefing with ranked scenarios, key pivots, and position sizing. Do NOT invent future post-market outcomes."
)


def build_dataset_for_ticker(
    ticker: str = "NQ1",
    max_days: int | None = 50,
    verbose: bool = True,
    progress_callback=None,
) -> tuple[list[dict], list[dict]]:
    day_scope = "all available days" if max_days is None else f"max {max_days} days"
    print(f"[Dataset Generator] Generating ChatML instruction-tuning pairs for {ticker} ({day_scope})...")

    df_1d = pd.read_parquet(REPO_ROOT / "data" / f"{ticker}_1d.parquet")
    if df_1d.index.tz is not None:
        df_1d.index = df_1d.index.tz_convert("US/Eastern")
    else:
        df_1d.index = df_1d.index.tz_localize("UTC").tz_convert("US/Eastern")

    df_1m = load_fused_data(ticker, timeframe="1m")
    if df_1m is None or df_1m.empty:
        log.warning("No 1m data for %s", ticker)
        return [], []
    if df_1m.index.tz is not None:
        df_1m.index = df_1m.index.tz_convert("US/Eastern")
    else:
        df_1m.index = df_1m.index.tz_localize("UTC").tz_convert("US/Eastern")

    min_date = df_1m.index[0].date()
    max_date = df_1m.index[-1].date()

    all_dates = sorted(list(set(df_1d.index.date)))
    valid_dates = [d for d in all_dates if d.weekday() < 5 and (min_date + timedelta(days=2)) <= d <= (max_date - timedelta(days=1))]
    
    if max_days is None:
        selected_dates = valid_dates
    else:
        selected_dates = valid_dates[-max_days:]
    if progress_callback:
        progress_callback(
            {
                "stage": "dataset_init",
                "ticker": ticker,
                "total_dates": len(selected_dates),
                "processed_dates": 0,
                "successful_dates": 0,
            }
        )
    sft_records = []
    postmortem_records = []

    total_dates = len(selected_dates)
    successful_dates = 0

    for idx, d in enumerate(selected_dates, start=1):
        date_str = d.strftime("%Y-%m-%d")
        try:
            if verbose:
                res = run_pilot_wargame_and_reengineering(ticker=ticker, target_date=date_str)
            else:
                with redirect_stdout(io.StringIO()):
                    res = run_pilot_wargame_and_reengineering(ticker=ticker, target_date=date_str)
            if res.get("error") or res.get("premarket_0830", {}).get("p12_midline") is None:
                if progress_callback:
                    progress_callback(
                        {
                            "stage": "dataset_progress",
                            "ticker": ticker,
                            "total_dates": total_dates,
                            "processed_dates": idx,
                            "successful_dates": successful_dates,
                            "current_date": date_str,
                            "status": "skipped",
                        }
                    )
                continue

            pre = res["premarket_0830"]
            eod = res["eod_reengineering_1600"]

            dt_probs = pre.get("day_type_probabilities", {})
            user_input = (
                f"PRE-MARKET PROFILER INPUTS ({ticker} | {date_str}):\n"
                f"- Daily Profiler Overnight Key: {pre.get('overnight_key', 'N/A')} (Prior Day Type: {pre.get('prior_day_type', 'N/A')})\n"
                f"- Overnight Context: {pre.get('overnight_context')}\n"
                f"- Profiler Classification Matrix: NY1 Probabilities = {pre.get('profiler_ny1_probabilities', {})} (n={pre.get('profiler_ny1_samples', 0)})\n"
                f"- InStat HOD/LOD Timing: {pre.get('instat_timing', 'N/A')}\n"
                f"- InStat Per Outcome Details: {pre.get('instat_per_outcome', {})}\n"
                f"- HTF Weekly EMA(5) Excursion: {pre.get('htf_ema_dist_pct', 0):+.2f}% (2-3% Magnet Zone: {'YES' if pre.get('is_2to3_magnet_zone') else 'NO'})\n"
                f"- P12 Range (18:00-06:00 ET): {pre.get('p12_range')} | Midline: {pre.get('p12_midline')}\n"
                f"- 06:00-08:30 Pre-Market Bias: {pre.get('p12_premarket_bias')} | 08:30 Pre-Market Handshake: {pre.get('premarket_handshake')}\n"
                f"- Signal Confluence Status: {pre.get('confluence_status')}\n"
                f"- Risk Management Position Sizing: {pre.get('position_sizing', {}).get('contract_count', 0)} contracts (${pre.get('position_sizing', {}).get('dollars_at_risk', 0)} at risk, {pre.get('position_sizing', {}).get('stop_distance_points', 0)} pt stop)\n"
                f"- Candle Science Target Boxes: {pre.get('candle_science_target_boxes')}\n"
                f"- False Scenario (Reversion): {pre.get('false_scenario')}\n"
                f"- True Scenario (Continuation): {pre.get('true_scenario')}\n"
            )

            # Task A: Pure Causal SFT Briefing (ZERO Future RTH Data)
            sft_assistant_response = (
                f"=== PRE-MARKET WARGAME BRIEFING & TRADING PLAN (08:30 AM EST) ===\n\n"
                f"1. DAILY PROFILER & OUTCOME PROBABILITIES:\n"
                f"   - Overnight Scenario: {pre.get('overnight_key', 'N/A')} (n={pre.get('profiler_ny1_samples', 0)} days)\n"
                f"   - Overnight Context: {pre.get('overnight_context', 'N/A')}\n"
                f"   - Outcome Matrix: {pre.get('profiler_ny1_probabilities', {})}\n\n"
                f"2. INSTAT HOD/LOD TIMING & CONTEXT:\n"
                f"   - Timing Overview: {pre.get('instat_timing', 'N/A')}\n"
                f"   - Mode Breakdowns: {pre.get('instat_per_outcome', {})}\n\n"
                f"3. ACTIONABLE SCENARIO MAP:\n"
                f"   ➤ FALSE SCENARIO (Reversion): {pre.get('false_scenario', {})}\n"
                f"   ➤ TRUE SCENARIO (Continuation): {pre.get('true_scenario', {})}\n"
                f"   ➤ CANDLE SCIENCE TARGETS: {pre.get('candle_science_target_boxes', 'N/A')}\n\n"
                f"4. MICKEY & AUSTIN 4-STEP COUNTER PLAN:\n"
                f"   - Step 1 (08:30 Handshake): {pre.get('premarket_handshake')} ({pre.get('p12_premarket_bias')} 06:00-08:30 vector vs P12 Midline {pre.get('p12_midline')}).\n"
                f"   - Step 2 (09:30 RTH Open): Monitor 09:30 open print relative to P12 Midline ({pre.get('p12_midline')}).\n"
                f"   - Step 3 (10:00 AM Expansion): If price expands past P12 Midline with momentum, confirm trend continuation.\n"
                f"   - Step 4 (10:30-11:00 AM Reversal Check): If 10:00 AM expansion fails at key wall/level and returns to 09:30 open, switch to Reversal.\n\n"
                f"5. CONFLUENCE & POSITION SIZING:\n"
                f"   - Confluence Status: {pre.get('confluence_status')}\n"
                f"   - Risk Limit: {pre.get('position_sizing', {}).get('contract_count', 0)} contracts (${pre.get('position_sizing', {}).get('dollars_at_risk', 0)} fixed risk limit, {pre.get('position_sizing', {}).get('stop_distance_points', 0)} pt stop)\n"
            )

            sft_record = {
                "id": f"sft_{ticker}_{date_str}",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_input},
                    {"role": "assistant", "content": sft_assistant_response},
                ],
                "metadata": {
                    "ticker": ticker,
                    "date": date_str,
                    "confluence": pre['confluence_status'],
                }
            }
            sft_records.append(sft_record)

            # Task B: EOD Post-Mortem & Reengineering Task
            postmortem_user = (
                f"{user_input}\n"
                f"ACTUAL RTH SESSION SUMMARY (16:00 PM EST):\n"
                f"- Open: {eod.get('rth_open')} (Actual Handshake: {eod.get('actual_rth_handshake')})\n"
                f"- High: {eod.get('rth_high')} ({eod.get('hod_timestamp')}) | Low: {eod.get('rth_low')} ({eod.get('lod_timestamp')})\n"
                f"- Close: {eod.get('rth_close')}\n"
                f"- 3-Hour Line vs Apex Score: {eod.get('line_vs_apex')}\n"
                f"- 4-Step Counter Score: {eod.get('4step_score')} (Step 4 Q1 InStat: {eod.get('step4_q1_instat')})\n"
            )

            postmortem_assistant = (
                f"=== EOD REENGINEERING POST-MORTEM (16:00 PM EST) ===\n"
                f"RTH Session Summary: Open={eod.get('rth_open')} | High={eod.get('rth_high')} ({eod.get('hod_timestamp')}) | Low={eod.get('rth_low')} ({eod.get('lod_timestamp')}) | Close={eod.get('rth_close')}\n"
                f"Actual NY Handshake Vector: {eod.get('actual_rth_handshake')}\n"
                f"3-Hour Line vs Apex Score: {eod.get('line_vs_apex')} | 4-Step Counter Score: {eod.get('4step_score')} (Step 4 Q1 InStat: {eod.get('step4_q1_instat')})\n"
                f"🏆 WINNING SCENARIO: {eod.get('winning_scenario')}\n"
            )

            postmortem_record = {
                "id": f"postmortem_{ticker}_{date_str}",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": postmortem_user},
                    {"role": "assistant", "content": postmortem_assistant},
                ],
                "metadata": {
                    "ticker": ticker,
                    "date": date_str,
                    "winning_scenario": eod['winning_scenario'],
                }
            }
            postmortem_records.append(postmortem_record)
            successful_dates += 1

            if progress_callback and (idx == 1 or idx == total_dates or idx % 10 == 0):
                progress_callback(
                    {
                        "stage": "dataset_progress",
                        "ticker": ticker,
                        "total_dates": total_dates,
                        "processed_dates": idx,
                        "successful_dates": successful_dates,
                        "current_date": date_str,
                        "status": "ok",
                    }
                )

        except Exception as e:
            log.warning("Failed dataset generation for %s %s: %s", ticker, date_str, e)
            if progress_callback:
                progress_callback(
                    {
                        "stage": "dataset_progress",
                        "ticker": ticker,
                        "total_dates": total_dates,
                        "processed_dates": idx,
                        "successful_dates": successful_dates,
                        "current_date": date_str,
                        "status": "error",
                        "error": str(e),
                    }
                )

    if progress_callback:
        progress_callback(
            {
                "stage": "dataset_complete",
                "ticker": ticker,
                "total_dates": total_dates,
                "processed_dates": total_dates,
                "successful_dates": successful_dates,
            }
        )

    return sft_records, postmortem_records


def build_full_wargaming_dataset():
    tickers = ["NQ1", "ES1"]
    all_sft = []
    all_postmortem = []

    for t in tickers:
        sft_recs, pm_recs = build_dataset_for_ticker(t, max_days=30)
        all_sft.extend(sft_recs)
        all_postmortem.extend(pm_recs)

    sft_path = REPO_ROOT / "data" / "wargaming_sft.jsonl"
    pm_path = REPO_ROOT / "data" / "wargaming_postmortem.jsonl"
    
    sft_path.parent.mkdir(parents=True, exist_ok=True)

    with open(sft_path, "w", encoding="utf-8") as f:
        for r in all_sft:
            f.write(json.dumps(r) + "\n")

    with open(pm_path, "w", encoding="utf-8") as f:
        for r in all_postmortem:
            f.write(json.dumps(r) + "\n")

    print(f"\n==========================================================================")
    print(f"🎉 REFACTORED CHATML FINE-TUNING DATASET GENERATION COMPLETE!")
    print(f"  1. Causal Wargaming SFT Pairs: {len(all_sft)} -> {sft_path}")
    print(f"  2. EOD Post-Mortem Pairs:      {len(all_postmortem)} -> {pm_path}")
    print(f"==========================================================================\n")


if __name__ == "__main__":
    build_full_wargaming_dataset()
