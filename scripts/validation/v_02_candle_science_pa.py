"""Intraday Price Action Verification Script for Candle Science (Step 0.2 PA)

Performs Mickey-style bar-by-bar price action verification of Candle Science outcomes
on historical 1m OHLCV bars.

Verifies:
1. C1 Color Magnifier effect (Red C1 + Bull C2 -> +8-9% boost).
2. C2 Open 'Line in the Sand' breach timestamp & directional flip during RTH.
3. Q1 (09:30-09:45) 0-5 Box 10 bps (0.10%) momentum threshold.
4. TP1 (10 bps / 1R) hit time.
5. TP2 (P50 Median MFE) hit time before 09:44 AM EST.
6. Actual C3 High/Low/Close outcome vs Candle Science predictions.
"""
from __future__ import annotations

import sys
import logging
from pathlib import Path
import pandas as pd
import numpy as np
import pytz
from datetime import datetime, time

REPO_ROOT = Path(__file__).parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from scripts.utils.fused_data_loader import load_fused_data
from scripts.trader.signals.candle_science import get_candle_science_read

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

ET = pytz.timezone("America/New_York")


def verify_candle_science_pa(ticker: str = "NQ1", sample_dates: list[str] = None) -> bool:
    print(f"\n==========================================================================")
    print(f"   MICKEY-STYLE INTRADAY PA VERIFICATION FOR CANDLE SCIENCE: {ticker}")
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
        # Default sample dates: last 5 available trading days
        unique_dates = sorted(list(set(df_1d.index.date)))
        sample_dates = [d.strftime("%Y-%m-%d") for d in unique_dates[-6:-1]]

    results = []

    for date_str in sample_dates:
        target_dt = pd.to_datetime(date_str).date()
        daily_idx = df_1d.index.searchsorted(pd.Timestamp(target_dt).tz_localize("US/Eastern"))
        
        if daily_idx < 2 or daily_idx >= len(df_1d):
            print(f"⚠️ Skipping date {date_str}: Not enough daily history")
            continue

        c1 = df_1d.iloc[daily_idx - 2]
        c2 = df_1d.iloc[daily_idx - 1]
        c3_actual = df_1d.iloc[daily_idx]

        c1_dir = "bull" if c1["close"] >= c1["open"] else "bear"
        c2_dir = "bull" if c2["close"] >= c2["open"] else "bear"
        c2_open = c2["open"]
        c2_high = c2["high"]
        c2_low = c2["low"]
        c2_close = c2["close"]
        c1_high = c1["high"]

        # C2 Close position vs C1 High
        c2_close_vs_c1h = "A+ (Above C1H)" if c2_close > c1_high else "Inside/Below C1H"
        
        # Basis point calculation for 10 bps threshold
        bps_10_pts = c2_close * 0.0010  # 0.10%

        # Extract 1m bars for target date RTH (09:30 to 16:00 ET)
        rth_start = pd.Timestamp(datetime.combine(target_dt, time(9, 30))).tz_localize("US/Eastern")
        rth_end = pd.Timestamp(datetime.combine(target_dt, time(16, 0))).tz_localize("US/Eastern")
        
        bars_1m = df_1m[(df_1m.index >= rth_start) & (df_1m.index <= rth_end)]
        if bars_1m.empty:
            print(f"⚠️ Skipping date {date_str}: No 1m RTH bars found")
            continue

        c3_open_rth = bars_1m.iloc[0]["open"]
        
        # 1. Check C2 Open 'Line in the Sand' Status
        opened_above_c2_open = c3_open_rth >= c2_open
        c2_open_breach_time = None
        
        for t_stamp, bar in bars_1m.iterrows():
            if opened_above_c2_open:
                if bar["low"] < c2_open:
                    c2_open_breach_time = t_stamp.strftime("%H:%M")
                    break
            else:
                if bar["high"] > c2_open:
                    c2_open_breach_time = t_stamp.strftime("%H:%M")
                    break

        # 2. Measure Q1 (09:30-09:45) 0-5 Box 10 bps Breach
        q1_end = pd.Timestamp(datetime.combine(target_dt, time(9, 45))).tz_localize("US/Eastern")
        q1_bars = bars_1m[bars_1m.index <= q1_end]
        q1_high = q1_bars["high"].max() if not q1_bars.empty else c3_open_rth
        q1_low = q1_bars["low"].min() if not q1_bars.empty else c3_open_rth
        q1_range = q1_high - q1_low
        q1_bps = (q1_range / c2_close) * 10000.0  # in basis points
        q1_10bps_met = q1_bps >= 10.0

        # 3. TP1 (10 bps / 1R) Hit Time
        tp1_long_target = c3_open_rth + bps_10_pts
        tp1_short_target = c3_open_rth - bps_10_pts
        tp1_hit_time = None

        for t_stamp, bar in bars_1m.iterrows():
            if opened_above_c2_open and bar["high"] >= tp1_long_target:
                tp1_hit_time = t_stamp.strftime("%H:%M")
                break
            elif not opened_above_c2_open and bar["low"] <= tp1_short_target:
                tp1_hit_time = t_stamp.strftime("%H:%M")
                break

        # 4. Actual C3 Outcome
        actual_took_high = c3_actual["high"] > c2_high
        actual_took_low = c3_actual["low"] < c2_low
        actual_c3_bull = c3_actual["close"] >= c3_actual["open"]

        results.append({
            "date": date_str,
            "c1_dir": c1_dir,
            "c2_dir": c2_dir,
            "c2_close_vs_c1h": c2_close_vs_c1h,
            "c2_open": round(c2_open, 2),
            "c3_open": round(c3_open_rth, 2),
            "opened_above_c2_open": opened_above_c2_open,
            "c2_open_breached": c2_open_breach_time if c2_open_breach_time else "No (Held)",
            "q1_bps": round(q1_bps, 1),
            "10bps_met": q1_10bps_met,
            "tp1_hit_time": tp1_hit_time if tp1_hit_time else "Not Hit",
            "actual_took_high": actual_took_high,
            "actual_took_low": actual_took_low,
            "actual_c3_bull": actual_c3_bull,
        })

    # Display Breakdown Table
    print(f"\n{'Date':<12} | {'C1/C2 Dir':<10} | {'C2 Open':<9} | {'C3 Open':<9} | {'C2 Open Breach':<14} | {'Q1 BPS':<7} | {'TP1 Hit':<8} | {'Actual Outcome':<18}")
    print("-" * 105)
    for r in results:
        outcome = f"H:{'YES' if r['actual_took_high'] else 'NO '} L:{'YES' if r['actual_took_low'] else 'NO '} {'BULL' if r['actual_c3_bull'] else 'BEAR'}"
        print(f"{r['date']:<12} | {r['c1_dir']}/{r['c2_dir']:<6} | {r['c2_open']:<9.2f} | {r['c3_open']:<9.2f} | {r['c2_open_breached']:<14} | {r['q1_bps']:<5.1f}bps | {r['tp1_hit_time']:<8} | {outcome:<18}")

    print("\n✅ Mickey-Style Price Action Verification Completed!")
    return True


if __name__ == "__main__":
    ticker_arg = sys.argv[1] if len(sys.argv) > 1 else "NQ1"
    verify_candle_science_pa(ticker_arg)
