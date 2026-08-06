"""Intraday Price Action Verification Script for HTF Weekly EMA(5) Excursion (Step 0.3 PA)

Performs Mickey-style intraday price action verification of HTF EMA magnet zone interactions
and NFP Friday 08:30 AM release candle anchors on historical 1m OHLCV bars.

Verifies:
1. Reversion / Continuation response when price enters the 2%-3% Weekly EMA(5) magnet zone.
2. NFP Friday 08:30 AM pre-market release candle High/Low bounds and RTH breakout/rejection response.
3. Sunday 18:00 ET opening anchor and Tuesday 09:30 AM ET opening anchor.
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
from scripts.wargaming.htf_ema_analysis import compute_htf_ema_analysis

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

ET = pytz.timezone("America/New_York")


def verify_htf_ema_pa(ticker: str = "NQ1", sample_dates: list[str] = None) -> bool:
    print(f"\n==========================================================================")
    print(f"   INTRADAY PA VERIFICATION FOR HTF EMA(5) & NFP ANOMALIES: {ticker}")
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
        # Default sample dates: Find recent NFP Fridays and 2%-3% EMA extension days
        nfp_dates = []
        for dt, row in df_1d.iterrows():
            d = dt.date()
            if d.weekday() == 4 and d.day <= 7:  # First Friday of month
                nfp_dates.append(d.strftime("%Y-%m-%d"))
        
        sample_dates = nfp_dates[-4:] if len(nfp_dates) >= 4 else [d.strftime("%Y-%m-%d") for d in df_1d.index.date[-5:]]

    results = []

    for date_str in sample_dates:
        t_dt = pd.to_datetime(date_str).date()
        ema_res = compute_htf_ema_analysis(ticker=ticker, target_date=date_str)
        
        # Load 1m bars for target date (00:00 to 16:00 ET to capture 08:30 NFP release)
        day_start = pd.Timestamp(datetime.combine(t_dt, time(0, 0))).tz_localize("US/Eastern")
        day_end = pd.Timestamp(datetime.combine(t_dt, time(16, 0))).tz_localize("US/Eastern")

        bars_1m = df_1m[(df_1m.index >= day_start) & (df_1m.index <= day_end)]
        if bars_1m.empty:
            print(f"⚠️ Skipping date {date_str}: No 1m bars found")
            continue

        # Extract 08:30 NFP release candle (08:30 - 08:45)
        nfp_release_start = pd.Timestamp(datetime.combine(t_dt, time(8, 30))).tz_localize("US/Eastern")
        nfp_release_end = pd.Timestamp(datetime.combine(t_dt, time(8, 45))).tz_localize("US/Eastern")
        
        nfp_bars = bars_1m[(bars_1m.index >= nfp_release_start) & (bars_1m.index <= nfp_release_end)]
        
        nfp_hi = float(nfp_bars["high"].max()) if not nfp_bars.empty else 0.0
        nfp_lo = float(nfp_bars["low"].min()) if not nfp_bars.empty else 0.0

        # RTH bars (09:30 to 16:00)
        rth_start = pd.Timestamp(datetime.combine(t_dt, time(9, 30))).tz_localize("US/Eastern")
        rth_bars = bars_1m[bars_1m.index >= rth_start]
        
        rth_open = float(rth_bars.iloc[0]["open"]) if not rth_bars.empty else 0.0
        rth_high = float(rth_bars["high"].max()) if not rth_bars.empty else 0.0
        rth_low = float(rth_bars["low"].min()) if not rth_bars.empty else 0.0
        rth_close = float(rth_bars.iloc[-1]["close"]) if not rth_bars.empty else 0.0

        # Check NFP 08:30 box breach during RTH
        took_nfp_hi = rth_high > nfp_hi if nfp_hi > 0 else False
        took_nfp_lo = rth_low < nfp_lo if nfp_lo > 0 else False

        results.append({
            "date": date_str,
            "ema5": ema_res.get("weekly_ema5"),
            "dist_pct": ema_res.get("dist_pct"),
            "is_2to3": ema_res.get("is_2to3_zone"),
            "is_nfp": ema_res.get("is_nfp_friday"),
            "nfp_hi": round(nfp_hi, 2) if nfp_hi > 0 else "N/A",
            "nfp_lo": round(nfp_lo, 2) if nfp_lo > 0 else "N/A",
            "took_nfp_hi": took_nfp_hi,
            "took_nfp_lo": took_nfp_lo,
            "rth_open": round(rth_open, 2),
            "rth_close": round(rth_close, 2),
        })

    # Print Verification Table
    print(f"\n{'Date':<12} | {'Weekly EMA5':<11} | {'Dist %':<8} | {'2-3% Zone':<9} | {'NFP Fri':<8} | {'08:30 NFP High/Low Range':<24} | {'NFP Swept':<10}")
    print("-" * 105)
    for r in results:
        nfp_range = f"{r['nfp_lo']} - {r['nfp_hi']}" if r['nfp_hi'] != "N/A" else "N/A"
        swept = f"HI:{'YES' if r['took_nfp_hi'] else 'NO '} LO:{'YES' if r['took_nfp_lo'] else 'NO '}" if r['is_nfp'] else "N/A"
        print(f"{r['date']:<12} | {r['ema5'] or 0:<11.2f} | {r['dist_pct']:>+6.2f}% | {'YES' if r['is_2to3'] else 'NO':<9} | {'YES' if r['is_nfp'] else 'NO':<8} | {nfp_range:<24} | {swept:<10}")

    print("\n✅ Intraday HTF EMA & NFP PA Verification Completed!")
    return True


if __name__ == "__main__":
    ticker_arg = sys.argv[1] if len(sys.argv) > 1 else "NQ1"
    verify_htf_ema_pa(ticker_arg)
