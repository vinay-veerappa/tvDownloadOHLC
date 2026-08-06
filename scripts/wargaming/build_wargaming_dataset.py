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
    "P12 early rejection 06:00-07:00: 84.52% HOD locked if P12 High rejected, 81.85% LOD locked if P12 Low rejected.\n"
    "Both-sides sweep 06:00-08:30: 99.26% probability both HOD and LOD form after 08:30 AM.\n"
    "Given pre-market 08:30 AM EST inputs, produce a strictly causal briefing with ranked scenarios, key pivots, and position sizing. Do NOT invent future post-market outcomes."
)


def build_dataset_for_ticker(ticker: str = "NQ1", max_days: int = 50) -> tuple[list[dict], list[dict]]:
    print(f"[Dataset Generator] Generating ChatML instruction-tuning pairs for {ticker} (max {max_days} days)...")

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
    
    selected_dates = valid_dates[-max_days:]
    sft_records = []
    postmortem_records = []

    for d in selected_dates:
        date_str = d.strftime("%Y-%m-%d")
        try:
            res = run_pilot_wargame_and_reengineering(ticker=ticker, target_date=date_str)
            if res.get("error") or res.get("premarket_0830", {}).get("p12_midline") is None:
                continue

            pre = res["premarket_0830"]
            eod = res["eod_reengineering_1600"]

            dt_probs = pre.get("day_type_probabilities", {})
            user_input = (
                f"PRE-MARKET PROFILER INPUTS ({ticker} | {date_str}):\n"
                f"- Daily Profiler Overnight Key: {pre.get('overnight_key', 'N/A')} (Prior Day Type: {pre.get('prior_day_type', 'N/A')})\n"
                f"- Profiler Classification Matrix: Most Likely = {pre.get('profiler_most_likely', 'R1')} (n={pre.get('profiler_n_samples', 0)}) | R1={dt_probs.get('R1%', 0):.1f}%, R2={dt_probs.get('R2%', 0):.1f}%, DWP={dt_probs.get('DWP%', 0):.1f}%, DNP={dt_probs.get('DNP%', 0):.1f}%\n"
                f"- InStat High / Low Lock (06:00-07:00 ET - Within Statistical Expectation): InStat High = {'YES (84.52% HOD Locked)' if pre.get('instat_high_locked') else 'NO'} | InStat Low = {'YES (81.85% LOD Locked)' if pre.get('instat_low_locked') else 'NO'}\n"
                f"- Candle Science Bias: {pre['candle_science_bias']} (P_bull={pre['candle_science_p_bull']:.1f}%)\n"
                f"- HTF Weekly EMA(5) Excursion: {pre['htf_ema_dist_pct']:+.2f}% (2-3% Magnet Zone: {'YES' if pre['is_2to3_magnet_zone'] else 'NO'})\n"
                f"- P12 Range (18:00-06:00 ET): {pre['p12_range']} | Midline: {pre['p12_midline']}\n"
                f"- 06:00-08:30 Pre-Market Bias: {pre['p12_premarket_bias']} | 08:30 Pre-Market Handshake: {pre['premarket_handshake']}\n"
                f"- Signal Confluence Status: {pre['confluence_status']}\n"
                f"- Risk Management Position Sizing: {pre['position_sizing']['contract_count']} contracts (${pre['position_sizing']['dollars_at_risk']} at risk, {pre['position_sizing']['stop_distance_points']} pt stop)\n"
            )

            # Task A: Pure Causal SFT Briefing (ZERO Future RTH Data)
            sft_assistant_response = (
                f"=== PRE-MARKET WARGAME BRIEFING & TRADING PLAN (08:30 AM EST) ===\n\n"
                f"1. DAILY PROFILER & OUTCOME PROBABILITIES:\n"
                f"   - Overnight Scenario: {pre.get('overnight_key', 'N/A')} (n={pre.get('profiler_n_samples', 0)} days)\n"
                f"   - Predicted Day Type: {pre.get('profiler_most_likely', 'R1')}\n"
                f"   - Outcome Matrix: R1 (Chop) = {dt_probs.get('R1%', 0):.1f}% | DWP (Trend Pullback) = {dt_probs.get('DWP%', 0):.1f}% | R2 (Reversal) = {dt_probs.get('R2%', 0):.1f}% | DNP (Power Trend) = {dt_probs.get('DNP%', 0):.1f}%\n"
                f"   - Early Rejection Locks (InStat): InStat High = {'LOCKED (84.52%)' if pre.get('instat_high_locked') else 'NO'} | InStat Low = {'LOCKED (81.85%)' if pre.get('instat_low_locked') else 'NO'}\n\n"
                f"2. MICKEY & AUSTIN 4-STEP COUNTER PLAN:\n"
                f"   - Step 1 (08:30 Handshake): {pre['premarket_handshake']} ({pre['p12_premarket_bias']} 06:00-08:30 vector vs P12 Midline {pre['p12_midline']}).\n"
                f"   - Step 2 (09:30 RTH Open): Monitor 09:30 open print relative to P12 Midline ({pre['p12_midline']}) and C2 Open line in the sand.\n"
                f"   - Step 3 (10:00 AM Expansion): If price expands past P12 Midline with momentum, confirm DWP/DNP trend continuation.\n"
                f"   - Step 4 (10:30-11:00 AM Reversal Check): If 10:00 AM expansion fails at key wall/level and returns to 09:30 open, switch to R2 Reversal.\n\n"
                f"3. CONFLUENCE & POSITION SIZING:\n"
                f"   - Confluence Status: {pre['confluence_status']}\n"
                f"   - Risk Limit: {pre['position_sizing']['contract_count']} contracts (${pre['position_sizing']['dollars_at_risk']} fixed risk limit, {pre['position_sizing']['stop_distance_points']} pt stop)\n\n"
                f"4. ACTIONABLE SCENARIO MAP:\n"
                f"   ➤ Scenario A (Bullish Continuation): {pre['scenarios']['Scenario A (Bullish Continuation)']}\n"
                f"   ➤ Scenario B (Bearish Reversion): {pre['scenarios']['Scenario B (Bearish Reversion)']}\n"
                f"   ➤ Scenario C (Goalpost Chop / R1): {pre['scenarios']['Scenario C (Goalpost Chop / R1)']}\n"
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
                f"- Open: {eod['rth_open']} (Actual Handshake: {eod['actual_rth_handshake']})\n"
                f"- High: {eod['rth_high']} ({eod['hod_timestamp']}) | Low: {eod['rth_low']} ({eod['lod_timestamp']})\n"
                f"- Close: {eod['rth_close']}\n"
                f"- 3-Hour Line vs Apex Score: {eod['line_vs_apex']}\n"
            )

            postmortem_assistant = (
                f"=== EOD REENGINEERING POST-MORTEM (16:00 PM EST) ===\n"
                f"RTH Session Summary: Open={eod['rth_open']} | High={eod['rth_high']} ({eod['hod_timestamp']}) | Low={eod['rth_low']} ({eod['lod_timestamp']}) | Close={eod['rth_close']}\n"
                f"Actual NY Handshake Vector: {eod['actual_rth_handshake']}\n"
                f"3-Hour Line vs Apex Score: {eod['line_vs_apex']}\n"
                f"🏆 WINNING SCENARIO: {eod['winning_scenario']}\n"
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

        except Exception as e:
            log.warning("Failed dataset generation for %s %s: %s", ticker, date_str, e)

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
