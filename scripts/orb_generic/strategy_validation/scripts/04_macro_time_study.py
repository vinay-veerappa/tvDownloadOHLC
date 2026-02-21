#!/usr/bin/env python3
# strategy_validation/scripts/04_macro_time_study.py
"""
Study 4: Macro Time Window Analysis
=====================================
Validates ICT macro time concepts (x:50 to x+1:10) as high-displacement windows.

Usage:
    python 04_macro_time_study.py
    python 04_macro_time_study.py --symbols ES NQ

Outputs:
    {symbol}_time_window_volatility.csv  — volatility by 20-min window across the day
    {symbol}_macro_vs_nonmacro.csv       — macro windows compared to non-macro
    {symbol}_fvg_by_time.csv             — FVG formation rates by time window
"""

import argparse
import sys
import os
import numpy as np
import pandas as pd
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import get_config
from scripts.utils import load_derived, save_results, log, timer, detect_fvgs


@timer
def analyze_time_window_volatility(rth: pd.DataFrame, window_minutes: int = 20) -> pd.DataFrame:
    """Analysis 4.1: Volatility by fixed time windows across the trading day.

    Segments RTH into non-overlapping windows and computes volatility metrics.
    Also flags which windows are ICT macro times.
    """
    # Define macro windows (minutes from midnight)
    macro_ranges = [
        (9*60+50, 10*60+10),    # 09:50-10:10
        (10*60+50, 11*60+10),   # 10:50-11:10
        (13*60+50, 14*60+10),   # 13:50-14:10
        (14*60+50, 15*60+10),   # 14:50-15:10
    ]

    rth = rth.copy()
    rth_minutes = rth.index.hour * 60 + rth.index.minute

    # Create window bins starting from 9:30
    rth_start_min = 9 * 60 + 30
    rth_end_min = 16 * 60
    window_starts = list(range(rth_start_min, rth_end_min, window_minutes))

    results = []

    for ws in window_starts:
        we = ws + window_minutes
        mask = (rth_minutes >= ws) & (rth_minutes < we)
        window_bars = rth[mask]

        if len(window_bars) == 0:
            continue

        # Group by trade date
        groups = window_bars.groupby("trade_date")

        ranges = groups["high"].max() - groups["low"].min()
        abs_changes = (groups["close"].last() - groups["open"].first()).abs()
        volumes = groups["volume"].sum()

        # Displacement rate: |close-open| > 0.7 * (high-low)
        displacement = abs_changes / ranges.replace(0, np.nan)
        disp_rate = (displacement > 0.7).mean() * 100

        # Is this a macro window?
        is_macro = any(
            (ws >= m_start and ws < m_end) or (we > m_start and we <= m_end)
            for m_start, m_end in macro_ranges
        )

        window_label = f"{ws//60:02d}:{ws%60:02d}-{we//60:02d}:{we%60:02d}"

        results.append({
            "window": window_label,
            "window_start_min": ws,
            "is_macro": is_macro,
            "num_days": len(groups),
            "avg_range_pts": ranges.mean(),
            "median_range_pts": ranges.median(),
            "std_range_pts": ranges.std(),
            "avg_abs_change_pts": abs_changes.mean(),
            "displacement_rate_pct": disp_rate,
            "avg_volume": volumes.mean(),
            "p75_range_pts": ranges.quantile(0.75),
            "p90_range_pts": ranges.quantile(0.90),
        })

    return pd.DataFrame(results)


@timer
def compare_macro_vs_nonmacro(vol_data: pd.DataFrame) -> pd.DataFrame:
    """Compare macro windows against non-macro windows."""
    macro = vol_data[vol_data["is_macro"]]
    non_macro = vol_data[~vol_data["is_macro"]]

    comparison = pd.DataFrame({
        "metric": [
            "avg_range_pts", "avg_abs_change_pts", "displacement_rate_pct",
            "avg_volume", "p75_range_pts", "p90_range_pts"
        ],
        "macro_mean": [
            macro["avg_range_pts"].mean(),
            macro["avg_abs_change_pts"].mean(),
            macro["displacement_rate_pct"].mean(),
            macro["avg_volume"].mean(),
            macro["p75_range_pts"].mean(),
            macro["p90_range_pts"].mean(),
        ],
        "non_macro_mean": [
            non_macro["avg_range_pts"].mean(),
            non_macro["avg_abs_change_pts"].mean(),
            non_macro["displacement_rate_pct"].mean(),
            non_macro["avg_volume"].mean(),
            non_macro["p75_range_pts"].mean(),
            non_macro["p90_range_pts"].mean(),
        ],
    })
    comparison["ratio"] = comparison["macro_mean"] / comparison["non_macro_mean"].replace(0, np.nan)
    comparison["pct_diff"] = (comparison["macro_mean"] - comparison["non_macro_mean"]) / comparison["non_macro_mean"].replace(0, np.nan) * 100

    return comparison


@timer
def analyze_fvgs_by_time(rth: pd.DataFrame, window_minutes: int = 20) -> pd.DataFrame:
    """Analysis 4.2: FVG formation and fill rates by time window."""
    rth = rth.copy()

    # Detect FVGs
    log("  Detecting FVGs...")
    fvg_data = detect_fvgs(rth)
    rth = rth.join(fvg_data)

    rth_minutes = rth.index.hour * 60 + rth.index.minute
    rth_start_min = 9 * 60 + 30
    rth_end_min = 16 * 60
    window_starts = list(range(rth_start_min, rth_end_min, window_minutes))

    # Macro windows
    macro_ranges = [
        (9*60+50, 10*60+10),
        (10*60+50, 11*60+10),
        (13*60+50, 14*60+10),
        (14*60+50, 15*60+10),
    ]

    results = []

    for ws in window_starts:
        we = ws + window_minutes
        mask = (rth_minutes >= ws) & (rth_minutes < we)
        window_bars = rth[mask]
        fvgs = window_bars[window_bars["fvg_type"] != 0]

        if len(window_bars) == 0:
            continue

        n_days = window_bars["trade_date"].nunique()
        n_fvgs = len(fvgs)
        n_bull = (fvgs["fvg_type"] == 1).sum()
        n_bear = (fvgs["fvg_type"] == -1).sum()

        # FVG fill analysis: for each FVG, check if it gets filled within next 30 bars
        fill_count = 0
        respect_count = 0
        for idx_pos in range(len(fvgs)):
            fvg_row = fvgs.iloc[idx_pos]
            fvg_idx = fvgs.index[idx_pos]
            # Get next 30 bars from main DataFrame
            fvg_loc = rth.index.get_loc(fvg_idx)
            if isinstance(fvg_loc, slice):
                fvg_loc = fvg_loc.start
            future = rth.iloc[fvg_loc+1:fvg_loc+31]

            if len(future) == 0:
                continue

            if fvg_row["fvg_type"] == 1:  # Bullish — gap between top and bottom
                mid = (fvg_row["fvg_top"] + fvg_row["fvg_bottom"]) / 2
                filled = future["low"].min() <= mid
                # Respect: price touches FVG zone and reverses up
                touched = future["low"].min() <= fvg_row["fvg_top"]
                if touched:
                    touch_idx = np.where(future["low"].values <= fvg_row["fvg_top"])[0]
                    if len(touch_idx) > 0:
                        post_touch = future.iloc[touch_idx[0]:]
                        respected = post_touch["close"].iloc[-1] > fvg_row["fvg_top"] if len(post_touch) > 0 else False
                    else:
                        respected = False
                else:
                    respected = False
            else:  # Bearish
                mid = (fvg_row["fvg_top"] + fvg_row["fvg_bottom"]) / 2
                filled = future["high"].max() >= mid
                touched = future["high"].max() >= fvg_row["fvg_bottom"]
                if touched:
                    touch_idx = np.where(future["high"].values >= fvg_row["fvg_bottom"])[0]
                    if len(touch_idx) > 0:
                        post_touch = future.iloc[touch_idx[0]:]
                        respected = post_touch["close"].iloc[-1] < fvg_row["fvg_bottom"] if len(post_touch) > 0 else False
                    else:
                        respected = False
                else:
                    respected = False

            fill_count += int(filled)
            respect_count += int(respected)

        is_macro = any(
            (ws >= m_start and ws < m_end) or (we > m_start and we <= m_end)
            for m_start, m_end in macro_ranges
        )

        window_label = f"{ws//60:02d}:{ws%60:02d}-{we//60:02d}:{we%60:02d}"

        results.append({
            "window": window_label,
            "window_start_min": ws,
            "is_macro": is_macro,
            "num_days": n_days,
            "total_fvgs": n_fvgs,
            "fvgs_per_day": n_fvgs / n_days if n_days > 0 else 0,
            "bull_fvgs": n_bull,
            "bear_fvgs": n_bear,
            "avg_fvg_width": fvgs["fvg_width"].mean() if n_fvgs > 0 else 0,
            "fill_rate_50pct": fill_count / n_fvgs * 100 if n_fvgs > 0 else 0,
            "respect_rate": respect_count / n_fvgs * 100 if n_fvgs > 0 else 0,
        })

    return pd.DataFrame(results)


def main():
    parser = argparse.ArgumentParser(description="Study 4: Macro Time Analysis")
    parser.add_argument("--symbols", nargs="*", help="Symbols to analyze")
    parser.add_argument("--window", type=int, default=20, help="Window size in minutes")
    args = parser.parse_args()

    config = get_config()
    cfg_data = config["data"]

    derived_path = Path(cfg_data.derived_dir)
    if args.symbols:
        symbols = args.symbols
    else:
        files = list(derived_path.glob("*_rth_1min.*"))
        symbols = list(set(f.stem.split("_")[0] for f in files))

    for symbol in symbols:
        log(f"\n{'='*60}")
        log(f"STUDY 4: Macro Time Analysis — {symbol}")
        log(f"{'='*60}")

        rth = load_derived(f"{symbol}_rth_1min", cfg_data)

        # 4.1: Time window volatility
        log("\n--- 4.1: Volatility by Time Window ---")
        vol_data = analyze_time_window_volatility(rth, args.window)
        save_results(vol_data, f"{symbol}_time_window_volatility", cfg_data)

        # Highlight top 5 most volatile windows
        top5 = vol_data.nlargest(5, "avg_range_pts")
        log("\nTop 5 most volatile windows:")
        print(top5[["window", "is_macro", "avg_range_pts", "displacement_rate_pct"]].to_string())

        # Macro comparison
        log("\n--- Macro vs Non-Macro ---")
        comparison = compare_macro_vs_nonmacro(vol_data)
        save_results(comparison, f"{symbol}_macro_vs_nonmacro", cfg_data)
        print(comparison.to_string())

        # 4.2: FVG by time
        log("\n--- 4.2: FVG Formation by Time Window ---")
        fvg_data = analyze_fvgs_by_time(rth, args.window)
        save_results(fvg_data, f"{symbol}_fvg_by_time", cfg_data)

        # Compare FVG stats in macro vs non-macro
        if len(fvg_data) > 0:
            macro_fvg = fvg_data[fvg_data["is_macro"]]
            non_macro_fvg = fvg_data[~fvg_data["is_macro"]]
            log(f"\n  Macro FVGs/day: {macro_fvg['fvgs_per_day'].mean():.2f}, "
                f"fill rate: {macro_fvg['fill_rate_50pct'].mean():.1f}%, "
                f"respect rate: {macro_fvg['respect_rate'].mean():.1f}%")
            log(f"  Non-macro FVGs/day: {non_macro_fvg['fvgs_per_day'].mean():.2f}, "
                f"fill rate: {non_macro_fvg['fill_rate_50pct'].mean():.1f}%, "
                f"respect rate: {non_macro_fvg['respect_rate'].mean():.1f}%")

        log(f"\n{symbol} Study 4 complete.")

    log(f"\n{'='*60}")
    log("STUDY 4 COMPLETE")
    log(f"{'='*60}")


if __name__ == "__main__":
    main()
