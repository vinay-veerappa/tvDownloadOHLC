"""Intraday Price Action Verification Script for Line vs Apex & 0-5 Box (Step 0.4 PA)

Verifies 3-Hour Block Sequencing (09:00-12:00 Line vs Apex), 5-stage weighted reversal counter (0-4 score),
0-5 box momentum threshold from ticker_registry.json, and level acceptance filters on 1m OHLCV bars.
"""
from __future__ import annotations

import sys
import logging
import argparse
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
from scripts.risk.position_sizer import load_ticker_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

ET = pytz.timezone("America/New_York")


def verify_line_vs_apex_pa(ticker: str = "NQ1", sample_dates: list[str] = None) -> bool:
    print(f"\n==========================================================================")
    print(f"   INTRADAY PA VERIFICATION FOR 3-HOUR LINE VS APEX (STEP 0.4): {ticker}")
    print(f"==========================================================================")

    cfg = load_ticker_config(ticker)
    mom_threshold = cfg.get("momentum_threshold_points", 20.0)

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
        unique_dates = sorted(list(set(df_1d.index.date)))
        sample_dates = [d.strftime("%Y-%m-%d") for d in unique_dates[-6:-1]]

    results = []

    for date_str in sample_dates:
        t_dt = pd.to_datetime(date_str).date()

        # 09:00 to 12:00 EST block
        h9_start = pd.Timestamp(datetime.combine(t_dt, time(9, 0))).tz_localize("US/Eastern")
        h9_end = pd.Timestamp(datetime.combine(t_dt, time(10, 0))).tz_localize("US/Eastern")
        h10_start = pd.Timestamp(datetime.combine(t_dt, time(10, 0))).tz_localize("US/Eastern")
        h10_q1_end = pd.Timestamp(datetime.combine(t_dt, time(10, 15))).tz_localize("US/Eastern")
        h10_end = pd.Timestamp(datetime.combine(t_dt, time(11, 0))).tz_localize("US/Eastern")
        block_end = pd.Timestamp(datetime.combine(t_dt, time(12, 0))).tz_localize("US/Eastern")

        bars_9 = df_1m[(df_1m.index >= h9_start) & (df_1m.index < h9_end)]
        bars_10_q1 = df_1m[(df_1m.index >= h10_start) & (df_1m.index <= h10_q1_end)]
        bars_10 = df_1m[(df_1m.index >= h10_start) & (df_1m.index < h10_end)]
        bars_block = df_1m[(df_1m.index >= h9_start) & (df_1m.index <= block_end)]

        if bars_9.empty or bars_10.empty:
            print(f"⚠️ Skipping date {date_str}: Insufficient 1m bars in 09:00-12:00 block")
            continue

        h9_hi = float(bars_9["high"].max())
        h9_lo = float(bars_9["low"].min())
        h9_mid = (h9_hi + h9_lo) / 2.0

        rth_open_bars = df_1m[df_1m.index == pd.Timestamp(datetime.combine(t_dt, time(9, 30))).tz_localize("US/Eastern")]
        rth_open = float(rth_open_bars.iloc[0]["open"]) if not rth_open_bars.empty else h9_mid

        # 0-5 box in 10:00 AM hour (10:00 to 10:05)
        box_end = pd.Timestamp(datetime.combine(t_dt, time(10, 5))).tz_localize("US/Eastern")
        bars_05box = df_1m[(df_1m.index >= h10_start) & (df_1m.index <= box_end)]
        box_hi = float(bars_05box["high"].max()) if not bars_05box.empty else h9_hi
        box_lo = float(bars_05box["low"].min()) if not bars_05box.empty else h9_lo

        # Evaluate 5-stage counter steps
        # Step 1: Breach outside 09:30 RTH open range (> mom_threshold)
        h10_hi = float(bars_10["high"].max())
        h10_lo = float(bars_10["low"].min())
        
        step1 = bool(abs(h10_hi - rth_open) >= mom_threshold or abs(rth_open - h10_lo) >= mom_threshold)

        # Step 2: Accept past 09:00 hour 50% midpoint line (close past midpoint + validation bar)
        step2 = False
        for i in range(1, len(bars_10)):
            if bars_10.iloc[i-1]["close"] > h9_mid and bars_10.iloc[i]["low"] > h9_mid:
                step2 = True
                break
            elif bars_10.iloc[i-1]["close"] < h9_mid and bars_10.iloc[i]["high"] < h9_mid:
                step2 = True
                break

        # Step 3: 10:00 AM candle takes out 09:00 AM high or low
        step3 = bool(h10_hi > h9_hi or h10_lo < h9_lo)

        # Step 4: Instant High/Low (Q1 fails to breach 0-5 box by >= mom_threshold and reverses)
        q1_hi = float(bars_10_q1["high"].max()) if not bars_10_q1.empty else h10_hi
        q1_lo = float(bars_10_q1["low"].min()) if not bars_10_q1.empty else h10_lo
        
        breach_hi = (q1_hi - box_hi) >= mom_threshold
        breach_lo = (box_lo - q1_lo) >= mom_threshold

        whipsaw = breach_hi and breach_lo
        step4 = not whipsaw and ((q1_hi <= box_hi + mom_threshold) or (q1_lo >= box_lo - mom_threshold))

        step_score = sum([step1, step2, step3, step4])

        if step_score == 0:
            regime = "Line (Trend Locked)"
        elif step_score <= 2:
            regime = "Reversal Watch"
        elif step_score == 3:
            regime = "Probable Apex"
        else:
            regime = "Confirmed Apex Reversal"

        # Determine actual 3-hour outcome
        block_hi = float(bars_block["high"].max())
        block_lo = float(bars_block["low"].min())
        
        # Check if 10:00 AM candle set the block high/low (Apex) vs continued expansion (Line)
        is_apex = (h10_hi == block_hi) or (h10_lo == block_lo)
        actual_outcome = "3-Hour Apex (Pivot)" if is_apex else "3-Hour Line (Trend)"

        results.append({
            "date": date_str,
            "h9_range": f"{h9_lo:.2f} - {h9_hi:.2f}",
            "h9_mid": round(h9_mid, 2),
            "step_score": f"{step_score}/4",
            "whipsaw": "YES" if whipsaw else "NO",
            "regime": regime,
            "actual_outcome": actual_outcome,
        })

    # Print Verification Table
    print(f"\n{'Date':<12} | {'09:00 Range':<22} | {'09:00 Mid':<9} | {'Score':<6} | {'Whipsaw':<8} | {'Regime Classification':<25} | {'Actual 3-Hour Outcome':<22}")
    print("-" * 115)
    for r in results:
        print(f"{r['date']:<12} | {r['h9_range']:<22} | {r['h9_mid']:<9.2f} | {r['step_score']:<6} | {r['whipsaw']:<8} | {r['regime']:<25} | {r['actual_outcome']:<22}")

    print("\n✅ Intraday 3-Hour Line vs Apex PA Verification Completed!")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate 3-hour line vs apex price action")
    parser.add_argument("positional_ticker", nargs="?", default=None, help="Optional positional ticker")
    parser.add_argument("--ticker", dest="ticker", default=None, help="Ticker symbol (e.g., NQ1, ES1)")
    args = parser.parse_args()

    ticker_arg = args.ticker or args.positional_ticker or "NQ1"
    verify_line_vs_apex_pa(ticker_arg)
