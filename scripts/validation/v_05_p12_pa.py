"""Intraday Price Action Verification Script for P12 & Pre-Market Alignment (Step 0.5 P12)

Performs Mickey-style intraday price action verification of P12 level interaction,
06:00-08:30 AM ET directional switch, 06:00-07:00 AM early rejection (84.52% HOD / 81.85% LOD),
NY Opening Handshake Vector, and 99.26% both-sides sweep rule on 1m OHLCV bars.
"""
from __future__ import annotations

import sys
import logging
from pathlib import Path
import pandas as pd
import numpy as np
import pytz
from datetime import datetime, time, timedelta

REPO_ROOT = Path(__file__).parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from scripts.utils.fused_data_loader import load_fused_data

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

ET = pytz.timezone("America/New_York")


def verify_p12_pa(ticker: str = "NQ1", sample_dates: list[str] = None) -> bool:
    print(f"\n==========================================================================")
    print(f"   INTRADAY PA VERIFICATION FOR P12 & HANDSHAKE VECTOR: {ticker}")
    print(f"==========================================================================")

    df_1d = pd.read_parquet(REPO_ROOT / "data" / f"{ticker}_1d.parquet")
    if df_1d.index.tz is not None:
        df_1d.index = df_1d.index.tz_convert("US/Eastern")
    else:
        df_1d.index = df_1d.index.tz_localize("UTC").tz_convert("US/Eastern")

    df_1m = load_fused_data(ticker, timeframe="1m")
    if df_1m.index.tz is not None:
        df_1m.index = df_1m.index.tz_convert("US/Eastern")
    else:
        df_1m.index = df_1m.index.tz_localize("UTC").tz_convert("US/Eastern")

    if sample_dates is None:
        # Default: last 5 available trading days
        unique_dates = sorted(list(set(df_1d.index.date)))
        sample_dates = [d.strftime("%Y-%m-%d") for d in unique_dates[-6:-1]]

    results = []

    for date_str in sample_dates:
        t_dt = pd.to_datetime(date_str).date()
        prev_day = t_dt - timedelta(days=1)
        
        # P12 window: 18:00 ET (prev_day) to 06:00 ET (t_dt)
        p12_start = pd.Timestamp(datetime.combine(prev_day, time(18, 0))).tz_localize("US/Eastern")
        p12_end = pd.Timestamp(datetime.combine(t_dt, time(6, 0))).tz_localize("US/Eastern")

        p12_bars = df_1m[(df_1m.index >= p12_start) & (df_1m.index < p12_end)]
        if p12_bars.empty:
            print(f"⚠️ Skipping date {date_str}: No 1m P12 bars found")
            continue

        p12_high = float(p12_bars["high"].max())
        p12_low = float(p12_bars["low"].min())
        p12_mid = (p12_high + p12_low) / 2.0

        # Pre-market window: 06:00 to 08:30 ET
        pre_start = pd.Timestamp(datetime.combine(t_dt, time(6, 0))).tz_localize("US/Eastern")
        pre_end = pd.Timestamp(datetime.combine(t_dt, time(8, 30))).tz_localize("US/Eastern")
        pre_bars = df_1m[(df_1m.index >= pre_start) & (df_1m.index <= pre_end)]

        pre_high = float(pre_bars["high"].max()) if not pre_bars.empty else p12_mid
        pre_low = float(pre_bars["low"].min()) if not pre_bars.empty else p12_mid

        # 1. Check 99.26% Both-Sides Sweep Rule (Both P12 High & Low broken before 08:30)
        both_swept_pre = (pre_high > p12_high) and (pre_low < p12_low)

        # 2. Check 06:00-07:00 Early Rejection Window
        window7_end = pd.Timestamp(datetime.combine(t_dt, time(7, 0))).tz_localize("US/Eastern")
        w7_bars = df_1m[(df_1m.index >= pre_start) & (df_1m.index <= window7_end)]
        w7_high = float(w7_bars["high"].max()) if not w7_bars.empty else p12_mid
        w7_low = float(w7_bars["low"].min()) if not w7_bars.empty else p12_mid

        early_rej_h = abs(w7_high - p12_high) < (p12_mid * 0.0005)  # within 5 bps of P12 High
        early_rej_l = abs(w7_low - p12_low) < (p12_mid * 0.0005)

        # 3. Directional Switch (06:00-08:30 Footing vs Rejection relative to P12 Mid)
        last_pre_close = float(pre_bars.iloc[-1]["close"]) if not pre_bars.empty else p12_mid
        p12_bias = "BULLISH (P12 High Target)" if last_pre_close >= p12_mid else "BEARISH (P12 Low Target)"

        # 4. RTH 09:30 Open Handshake Vector
        rth_start = pd.Timestamp(datetime.combine(t_dt, time(9, 30))).tz_localize("US/Eastern")
        rth_end = pd.Timestamp(datetime.combine(t_dt, time(16, 0))).tz_localize("US/Eastern")
        rth_bars = df_1m[(df_1m.index >= rth_start) & (df_1m.index <= rth_end)]

        if rth_bars.empty:
            continue

        rth_open = float(rth_bars.iloc[0]["open"])
        handshake = "AGREEMENT" if (p12_bias.startswith("BULLISH") and rth_open >= p12_mid) or (p12_bias.startswith("BEARISH") and rth_open < p12_mid) else "DISAGREEMENT"

        # RTH Actual HOD/LOD Timestamps
        hod_val = float(rth_bars["high"].max())
        lod_val = float(rth_bars["low"].min())
        hod_time = rth_bars[rth_bars["high"] == hod_val].index[0].strftime("%H:%M")
        lod_time = rth_bars[rth_bars["low"] == lod_val].index[0].strftime("%H:%M")

        results.append({
            "date": date_str,
            "p12_range": f"{p12_low:.2f} - {p12_high:.2f}",
            "p12_mid": round(p12_mid, 2),
            "p12_bias": p12_bias,
            "handshake": handshake,
            "both_swept_pre": "YES (99.26% Rule)" if both_swept_pre else "No",
            "hod_time": hod_time,
            "lod_time": lod_time,
            "rth_close": round(float(rth_bars.iloc[-1]["close"]), 2),
        })

    # Print Verification Table
    print(f"\n{'Date':<12} | {'P12 Mid':<9} | {'Pre-Market Bias':<25} | {'Handshake':<12} | {'99.26% Sweep':<15} | {'HOD Time':<8} | {'LOD Time':<8}")
    print("-" * 105)
    for r in results:
        print(f"{r['date']:<12} | {r['p12_mid']:<9.2f} | {r['p12_bias']:<25} | {r['handshake']:<12} | {r['both_swept_pre']:<15} | {r['hod_time']:<8} | {r['lod_time']:<8}")

    print("\n✅ Intraday P12 & Handshake Vector PA Verification Completed!")
    return True


if __name__ == "__main__":
    ticker_arg = sys.argv[1] if len(sys.argv) > 1 else "NQ1"
    verify_p12_pa(ticker_arg)
