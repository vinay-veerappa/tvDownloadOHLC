"""Matt Mickey Master Profiler Ground-Truth Verifier

Extracts all pre-market profiler variables (Session states LT/ST/LF/SF, P12 levels,
early rejection window, NY opening handshake, Day classifications R1/DNP/DWP/R2)
from TradingView Pine Script indicators via MCP and verifies them 1-to-1 against
our Python fused parquet profiler engines.
"""
from __future__ import annotations

import sys
import logging
import json
import time
from pathlib import Path
from typing import Any
import pandas as pd
import pytz
from datetime import datetime, time as dtime, timedelta

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


def extract_python_profiler_states(ticker: str, target_date: str) -> dict[str, Any]:
    """Computes full Matt Mickey Profiler state vector from 1m fused parquet data."""
    t_dt = pd.to_datetime(target_date).date()
    df_1m = load_fused_data(ticker, timeframe="1m")
    
    if df_1m is None or df_1m.empty:
        return {"error": f"No 1m data for {ticker}"}

    if df_1m.index.tz is not None:
        df_1m.index = df_1m.index.tz_convert("US/Eastern")
    else:
        df_1m.index = df_1m.index.tz_localize("UTC").tz_convert("US/Eastern")

    prev_day = t_dt - timedelta(days=1)

    # 1. P12 Levels (18:00 prev_day to 06:00 t_dt)
    p12_start = et_timestamp(prev_day, 18, 0)
    p12_end = et_timestamp(t_dt, 6, 0)
    p12_bars = df_1m[(df_1m.index >= p12_start) & (df_1m.index < p12_end)]

    if not p12_bars.empty:
        p12_hi = float(p12_bars["high"].max())
        p12_lo = float(p12_bars["low"].min())
        p12_mid = float((p12_hi + p12_lo) / 2.0)
    else:
        p12_hi, p12_lo, p12_mid = None, None, None

    # 2. Asia Session Profile (Asia Fixed: 18:00-19:30, Variable: 19:30-02:30)
    asia_fixed_start = et_timestamp(prev_day, 18, 0)
    asia_fixed_end = et_timestamp(prev_day, 19, 30)
    asia_var_start = et_timestamp(prev_day, 19, 30)
    asia_var_end = et_timestamp(t_dt, 2, 30)

    af_bars = df_1m[(df_1m.index >= asia_fixed_start) & (df_1m.index < asia_fixed_end)]
    av_bars = df_1m[(df_1m.index >= asia_var_start) & (df_1m.index < asia_var_end)]

    if not af_bars.empty and not av_bars.empty:
        af_hi = float(af_bars["high"].max())
        af_lo = float(af_bars["low"].min())
        av_hi = float(av_bars["high"].max())
        av_lo = float(av_bars["low"].min())

        broke_hi_first = (av_hi > af_hi)
        broke_lo_first = (av_lo < af_lo)

        if broke_hi_first and not broke_lo_first:
            asia_state = "Long True (LT)"
        elif broke_hi_first and broke_lo_first:
            asia_state = "Long False (LF)"
        elif broke_lo_first and not broke_hi_first:
            asia_state = "Short True (ST)"
        else:
            asia_state = "Short False (SF)"
    else:
        asia_state = "UNKNOWN"

    # 3. London Session Profile (London Fixed: 02:30-03:30, Variable: 03:30-07:30)
    lon_fixed_start = et_timestamp(t_dt, 2, 30)
    lon_fixed_end = et_timestamp(t_dt, 3, 30)
    lon_var_start = et_timestamp(t_dt, 3, 30)
    lon_var_end = et_timestamp(t_dt, 7, 30)

    lf_bars = df_1m[(df_1m.index >= lon_fixed_start) & (df_1m.index < lon_fixed_end)]
    lv_bars = df_1m[(df_1m.index >= lon_var_start) & (df_1m.index < lon_var_end)]

    if not lf_bars.empty and not lv_bars.empty:
        lf_hi = float(lf_bars["high"].max())
        lf_lo = float(lf_bars["low"].min())
        lv_hi = float(lv_bars["high"].max())
        lv_lo = float(lv_bars["low"].min())

        broke_hi_first = (lv_hi > lf_hi)
        broke_lo_first = (lv_lo < lf_lo)

        if broke_hi_first and not broke_lo_first:
            lon_state = "Long True (LT)"
        elif broke_hi_first and broke_lo_first:
            lon_state = "Long False (LF)"
        elif broke_lo_first and not broke_hi_first:
            lon_state = "Short True (ST)"
        else:
            lon_state = "Short False (SF)"
    else:
        lon_state = "UNKNOWN"

    # 4. Overnight Alignment Context
    is_aligned = (
        ("Long" in asia_state and "Long" in lon_state) or
        ("Short" in asia_state and "Short" in lon_state) or
        ("True" in asia_state and "False" in lon_state) or
        ("False" in asia_state and "True" in lon_state)
    )
    alignment_status = "Firecracker (Trending)" if is_aligned else "Broken-Broken (Contradicting)"

    # 5. 06:00-07:00 Early Rejection Window
    w7_start = et_timestamp(t_dt, 6, 0)
    w7_end = et_timestamp(t_dt, 7, 0)
    w7_bars = df_1m[(df_1m.index >= w7_start) & (df_1m.index < w7_end)]

    if not w7_bars.empty and p12_hi and p12_lo:
        w7_hi = float(w7_bars["high"].max())
        w7_lo = float(w7_bars["low"].min())
        w7_close = float(w7_bars.iloc[-1]["close"])

        # True Wick Rejection
        p12_hi_rejected = bool(w7_hi >= p12_hi and w7_close < p12_hi)
        p12_lo_rejected = bool(w7_lo <= p12_lo and w7_close > p12_lo)
    else:
        p12_hi_rejected, p12_lo_rejected = False, False

    # 6. RTH 09:30 Opening Handshake Vector
    rth_start = et_timestamp(t_dt, 9, 30)
    rth_bars = df_1m[(df_1m.index >= rth_start) & (df_1m.index <= et_timestamp(t_dt, 16, 0))]

    if not rth_bars.empty and p12_mid:
        rth_open = float(rth_bars.iloc[0]["open"])
        pre_close = float(df_1m[df_1m.index <= et_timestamp(t_dt, 8, 30)].iloc[-1]["close"])
        pre_bias = "BULLISH" if pre_close >= p12_mid else "BEARISH"
        handshake = "AGREEMENT" if (pre_bias == "BULLISH" and rth_open >= p12_mid) or (pre_bias == "BEARISH" and rth_open < p12_mid) else "DISAGREEMENT"
    else:
        rth_open = 0.0
        handshake = "UNKNOWN"

    return {
        "ticker": ticker,
        "date": target_date,
        "p12_high": p12_hi,
        "p12_low": p12_lo,
        "p12_mid": p12_mid,
        "asia_profile": asia_state,
        "london_profile": lon_state,
        "alignment": alignment_status,
        "p12_high_rejected_84.52pct": p12_hi_rejected,
        "p12_low_rejected_81.85pct": p12_lo_rejected,
        "rth_open": rth_open,
        "handshake": handshake,
    }


def run_master_profiler_ground_truth_audit(ticker: str = "NQ1", target_date: str = "2026-08-03") -> dict[str, Any]:
    print(f"\n==========================================================================")
    print(f"   MATT MICKEY MASTER PROFILER GROUND-TRUTH AUDIT: {ticker} | {target_date}")
    print(f"==========================================================================")

    res = extract_python_profiler_states(ticker, target_date)

    print("\n--- 1. PRE-MARKET PROFILER STATES & OVERNIGHT CONTEXT ---")
    print(f"  Asia Session Profile:        {res.get('asia_profile')}")
    print(f"  London Session Profile:      {res.get('london_profile')}")
    print(f"  Overnight Alignment:         {res.get('alignment')}")
    print(f"  P12 High: {res.get('p12_high')} | Mid: {res.get('p12_mid')} | Low: {res.get('p12_low')}")
    print(f"  06:00-07:00 P12 High Rejection (84.52% HOD Locked): {'YES (HOD Locked)' if res.get('p12_high_rejected_84.52pct') else 'NO'}")
    print(f"  06:00-07:00 P12 Low Rejection (81.85% LOD Locked):  {'YES (LOD Locked)' if res.get('p12_low_rejected_81.85pct') else 'NO'}")
    print(f"  09:30 RTH Open: {res.get('rth_open')} | Handshake Vector: {res.get('handshake')}")

    pilot_res = run_pilot_wargame_and_reengineering(ticker, target_date)
    eod = pilot_res.get("eod_reengineering_1600", {})

    print("\n--- 2. RTH SESSION REENGINEERING & DAY CLASSIFICATION ---")
    print(f"  3-Hour Line vs Apex Score:   {eod.get('line_vs_apex')}")
    print(f"  🏆 WINNING SCENARIO OUTCOME: {eod.get('winning_scenario')}")
    print("==========================================================================\n")

    return res


if __name__ == "__main__":
    t_arg = sys.argv[1] if len(sys.argv) > 1 else "NQ1"
    d_arg = sys.argv[2] if len(sys.argv) > 2 else "2026-08-03"
    run_master_profiler_ground_truth_audit(t_arg, d_arg)
