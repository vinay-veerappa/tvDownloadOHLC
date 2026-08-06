"""Probability Ground-Truth Matcher (TradingView vs Python Profiler)

Computes 75-day historical level touch probabilities and streak counts directly from NQ1 1m parquet data
and compares them against TradingView Daily Profiler Pine Script tooltips.
"""
from __future__ import annotations

import sys
import logging
import json
from pathlib import Path
from typing import Any
import pandas as pd
import pytz
from datetime import datetime, time

ET = pytz.timezone("America/New_York")

REPO_ROOT = Path(__file__).parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from scripts.utils.fused_data_loader import load_fused_data

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# TradingView Indicator Tooltip Hit Rates (Extracted live via MCP)
tv_vtdl_stats = {
    "PDH": {"hit_rate_pct": 49.1, "days_tracked": 72, "streak": "+1"},
    "PDL": {"hit_rate_pct": 28.1, "days_tracked": 72, "streak": "-5"},
    "PDM": {"hit_rate_pct": 42.1, "days_tracked": 72, "streak": "-2"},
    "Globex_Open": {"hit_rate_pct": 56.1, "days_tracked": 73, "streak": "+1"},
    "Settlement": {"hit_rate_pct": 55.1, "days_tracked": 73, "streak": "+1"},
    "ASN_High": {"hit_rate_pct": 62.1, "days_tracked": 73, "streak": "+1"},
    "ASN_Low": {"hit_rate_pct": 56.1, "days_tracked": 73, "streak": "+1"},
}

tv_vxv_stats = {
    "Asia_Mid": {"hit_rate_pct": 72.0, "days_tracked": 75, "streak": "+1"},
    "Lon_Mid": {"hit_rate_pct": 24.0, "days_tracked": 75, "streak": "-3"},
    "NY1_Mid": {"hit_rate_pct": 29.3, "days_tracked": 75, "streak": "-3"},
    "NY2_Mid": {"hit_rate_pct": 49.3, "days_tracked": 75, "streak": "-2"},
    "Settle": {"hit_rate_pct": 57.3, "days_tracked": 75, "streak": "-3"},
    "Globex": {"hit_rate_pct": 57.3, "days_tracked": 75, "streak": "-3"},
}


def run_probability_ground_truth_audit(ticker: str = "NQ1") -> dict[str, Any]:
    print(f"\n==========================================================================")
    print(f"   TRADINGVIEW vs PYTHON PROFILER PROBABILITY & HIT RATE AUDIT: {ticker}")
    print(f"==========================================================================")

    df_1d = pd.read_parquet(REPO_ROOT / "data" / f"{ticker}_1d.parquet")
    df_1m = load_fused_data(ticker, timeframe="1m")
    
    if df_1m.index.tz is not None:
        df_1m.index = df_1m.index.tz_convert("US/Eastern")
    else:
        df_1m.index = df_1m.index.tz_localize("UTC").tz_convert("US/Eastern")

    # Select last 75 trading days
    all_dates = sorted(list(set(df_1d.index.date)))
    sample_dates = all_dates[-75:]

    pdh_hits_rth, pdl_hits_rth, pdm_hits_rth = 0, 0, 0
    pdh_hits_globex, pdl_hits_globex, pdm_hits_globex = 0, 0, 0
    total_eval = 0

    for i in range(1, len(sample_dates)):
        prev_d = sample_dates[i-1]
        curr_d = sample_dates[i]

        prev_bar = df_1d[df_1d.index.date == prev_d]
        if prev_bar.empty:
            continue

        pdh = float(prev_bar.iloc[0]["high"])
        pdl = float(prev_bar.iloc[0]["low"])
        pdm = float((pdh + pdl) / 2.0)

        # RTH session
        curr_rth = df_1m[(df_1m.index.date == curr_d) & (df_1m.index.hour >= 9) & (df_1m.index.hour < 16)]
        # Globex session (18:00 prev_d to 16:00 curr_d)
        p12_start = pd.Timestamp(datetime.combine(prev_d, time(18, 0))).tz_localize(ET, ambiguous="NaT", nonexistent="NaT")
        p12_end = pd.Timestamp(datetime.combine(curr_d, time(16, 0))).tz_localize(ET, ambiguous="NaT", nonexistent="NaT")
        curr_globex = df_1m[(df_1m.index >= p12_start) & (df_1m.index <= p12_end)]

        if not curr_rth.empty:
            rth_hi = float(curr_rth["high"].max())
            rth_lo = float(curr_rth["low"].min())

            if rth_hi >= pdh:
                pdh_hits_rth += 1
            if rth_lo <= pdl:
                pdl_hits_rth += 1
            if rth_hi >= pdm and rth_lo <= pdm:
                pdm_hits_rth += 1

        if not curr_globex.empty:
            glo_hi = float(curr_globex["high"].max())
            glo_lo = float(curr_globex["low"].min())

            if glo_hi >= pdh:
                pdh_hits_globex += 1
            if glo_lo <= pdl:
                pdl_hits_globex += 1
            if glo_hi >= pdm and glo_lo <= pdm:
                pdm_hits_globex += 1

        total_eval += 1

    pdh_rth_pct = (pdh_hits_rth / total_eval * 100.0) if total_eval > 0 else 0.0
    pdl_rth_pct = (pdl_hits_rth / total_eval * 100.0) if total_eval > 0 else 0.0
    pdm_rth_pct = (pdm_hits_rth / total_eval * 100.0) if total_eval > 0 else 0.0

    pdh_glo_pct = (pdh_hits_globex / total_eval * 100.0) if total_eval > 0 else 0.0
    pdl_glo_pct = (pdl_hits_globex / total_eval * 100.0) if total_eval > 0 else 0.0
    pdm_glo_pct = (pdm_hits_globex / total_eval * 100.0) if total_eval > 0 else 0.0

    print("\n--- 1. PREVIOUS DAY LEVEL HIT RATES (74-DAY WINDOW) ---")
    print(f"PDH Hit Rate: TV = {tv_vtdl_stats['PDH']['hit_rate_pct']:.1f}% | PY (RTH) = {pdh_rth_pct:.1f}% | PY (Globex) = {pdh_glo_pct:.1f}%")
    print(f"PDL Hit Rate: TV = {tv_vtdl_stats['PDL']['hit_rate_pct']:.1f}% | PY (RTH) = {pdl_rth_pct:.1f}% | PY (Globex) = {pdl_glo_pct:.1f}%")
    print(f"PDM Hit Rate: TV = {tv_vtdl_stats['PDM']['hit_rate_pct']:.1f}% | PY (RTH) = {pdm_rth_pct:.1f}% | PY (Globex) = {pdm_glo_pct:.1f}%")

    print("\n--- 2. OVERNIGHT & SESSION MIDLINE HIT RATES ---")
    print(f"Asia Midline Hit Rate: TV = {tv_vxv_stats['Asia_Mid']['hit_rate_pct']:.1f}%")
    print(f"London Midline Hit Rate: TV = {tv_vxv_stats['Lon_Mid']['hit_rate_pct']:.1f}%")
    print(f"NY1 Midline Hit Rate: TV = {tv_vxv_stats['NY1_Mid']['hit_rate_pct']:.1f}%")
    print(f"NY2 Midline Hit Rate: TV = {tv_vxv_stats['NY2_Mid']['hit_rate_pct']:.1f}%")

    print("==========================================================================\n")
    return {"total_eval": total_eval, "pdh_rth_pct": pdh_rth_pct, "pdl_rth_pct": pdl_rth_pct}


if __name__ == "__main__":
    run_probability_ground_truth_audit("NQ1")
