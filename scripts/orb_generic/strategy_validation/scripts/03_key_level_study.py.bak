#!/usr/bin/env python3
# strategy_validation/scripts/03_key_level_study.py
"""
Study 3: Key Level Rejection/Acceptance
========================================
Quantifies price behavior at PDH, PDL, PDC, Weekly Open, ONH, ONL.

Usage:
    python 03_key_level_study.py
    python 03_key_level_study.py --symbols ES NQ

Outputs:
    {symbol}_key_level_stats.csv         — rejection/acceptance rates per level
    {symbol}_weekly_open_stats.csv       — weekly open as S/R
    {symbol}_gap_fill_stats.csv          — gap fill rates by size
    {symbol}_level_test_detail.csv       — per-day per-level detail
"""

import argparse
import sys
import os
import numpy as np
import pandas as pd
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import get_config
from scripts.utils import load_derived, save_results, log, timer


@timer
def analyze_level_touches(daily_levels: pd.DataFrame, rth: pd.DataFrame,
                          proximity_pts: float = 2.0, reject_bars: int = 15,
                          accept_bars: int = 3) -> pd.DataFrame:
    """Analysis 3.1: PDH/PDL touch and reaction statistics.

    Args:
        proximity_pts: how close price must come to "test" the level
        reject_bars: bars to look ahead for rejection confirmation
        accept_bars: consecutive bars beyond level to confirm acceptance
    """
    results = []
    levels_to_test = ["pdh", "pdl", "onh", "onl"]

    for td in daily_levels.index:
        td_str = str(td)
        day_bars = rth[rth["trade_date"].astype(str) == td_str]
        if len(day_bars) < 10:
            continue

        highs = day_bars["high"].values
        lows = day_bars["low"].values
        closes = day_bars["close"].values

        for level_name in levels_to_test:
            level_val = daily_levels.loc[td, level_name]
            if pd.isna(level_val):
                continue

            # Determine approach direction
            # PDH, ONH: approached from below (price rises to test)
            # PDL, ONL: approached from above (price falls to test)
            is_upper = level_name in ["pdh", "onh"]

            if is_upper:
                # Test: did high come within proximity_pts of level?
                touches = np.where(highs >= level_val - proximity_pts)[0]
                if len(touches) == 0:
                    continue

                first_touch = touches[0]
                # Did it break through?
                broke_through = np.any(highs[first_touch:] > level_val)
                # Rejection: after touching, close pulls back within reject_bars
                look_ahead = closes[first_touch:first_touch + reject_bars]
                rejected = np.all(look_ahead < level_val) if len(look_ahead) > 0 else False
                # Acceptance: accept_bars consecutive closes above
                if broke_through:
                    above_closes = closes[first_touch:] > level_val
                    # Check for accept_bars consecutive True values
                    accepted = False
                    count = 0
                    for ac in above_closes:
                        if ac:
                            count += 1
                            if count >= accept_bars:
                                accepted = True
                                break
                        else:
                            count = 0
                else:
                    accepted = False

                max_beyond = np.max(highs[first_touch:]) - level_val if broke_through else 0
                max_retrace = level_val - np.min(lows[first_touch:])

            else:
                # Lower level — approached from above
                touches = np.where(lows <= level_val + proximity_pts)[0]
                if len(touches) == 0:
                    continue

                first_touch = touches[0]
                broke_through = np.any(lows[first_touch:] < level_val)
                look_ahead = closes[first_touch:first_touch + reject_bars]
                rejected = np.all(look_ahead > level_val) if len(look_ahead) > 0 else False
                if broke_through:
                    below_closes = closes[first_touch:] < level_val
                    accepted = False
                    count = 0
                    for bc in below_closes:
                        if bc:
                            count += 1
                            if count >= accept_bars:
                                accepted = True
                                break
                        else:
                            count = 0
                else:
                    accepted = False

                max_beyond = level_val - np.min(lows[first_touch:]) if broke_through else 0
                max_retrace = np.max(highs[first_touch:]) - level_val

            # Number of tests (how many times price approaches within proximity)
            if is_upper:
                num_tests = len(np.where(highs >= level_val - proximity_pts)[0])
            else:
                num_tests = len(np.where(lows <= level_val + proximity_pts)[0])

            # Time of first test
            first_test_minute = day_bars.index[first_touch].hour * 60 + day_bars.index[first_touch].minute

            results.append({
                "trade_date": td,
                "level": level_name,
                "level_value": level_val,
                "touched": True,
                "broke_through": broke_through,
                "rejected": rejected,
                "accepted": accepted,
                "num_tests": num_tests,
                "first_test_minute": first_test_minute,
                "max_beyond_pts": max_beyond,
                "max_retrace_pts": max_retrace,
            })

    return pd.DataFrame(results)


@timer
def analyze_weekly_open(daily_levels: pd.DataFrame, rth: pd.DataFrame) -> pd.DataFrame:
    """Analysis 3.2: Weekly open as support/resistance."""
    results = []

    # Only Tue-Fri (Mon IS the weekly open)
    dl = daily_levels[daily_levels["day_of_week"] > 0].copy()

    for td in dl.index:
        td_str = str(td)
        day_bars = rth[rth["trade_date"].astype(str) == td_str]
        if len(day_bars) < 10:
            continue

        wo = dl.loc[td, "weekly_open"]
        if pd.isna(wo):
            continue

        opens = day_bars["open"].iloc[0]
        highs = day_bars["high"].values
        lows = day_bars["low"].values
        closes = day_bars["close"].values

        above_at_open = opens > wo
        # Count crosses: number of times price goes from above to below or vice versa
        above = closes > wo
        crosses = np.sum(np.diff(above.astype(int)) != 0)

        # S/R behavior
        if above_at_open:
            # WO should act as support
            retests = np.where(lows <= wo + 2)[0]
            held_as_support = len(retests) > 0 and np.all(closes[retests[0]:retests[0]+5] > wo) if len(retests) > 0 else None
        else:
            # WO should act as resistance
            retests = np.where(highs >= wo - 2)[0]
            held_as_support = None
            held_as_resistance = len(retests) > 0 and np.all(closes[retests[0]:retests[0]+5] < wo) if len(retests) > 0 else None

        results.append({
            "trade_date": td,
            "day_of_week": dl.loc[td, "day_of_week"],
            "weekly_open": wo,
            "above_at_open": above_at_open,
            "crosses": crosses,
            "day_close_above_wo": closes[-1] > wo,
            "day_close_below_wo": closes[-1] < wo,
        })

    df = pd.DataFrame(results)

    if len(df) > 0:
        # Summary by day of week
        day_names = {1: "Tuesday", 2: "Wednesday", 3: "Thursday", 4: "Friday"}
        for dow, name in day_names.items():
            sub = df[df["day_of_week"] == dow]
            if len(sub) > 0:
                log(f"\n  {name}: {len(sub)} days")
                log(f"    Avg crosses: {sub['crosses'].mean():.1f}")
                log(f"    Close above WO: {sub['day_close_above_wo'].mean()*100:.1f}%")

    return df


@timer
def analyze_gap_fills(daily_levels: pd.DataFrame, rth: pd.DataFrame) -> pd.DataFrame:
    """Analysis 3.3: Gap fill statistics (RTH open vs PDC)."""
    results = []

    for td in daily_levels.index:
        td_str = str(td)
        day_bars = rth[rth["trade_date"].astype(str) == td_str]
        if len(day_bars) < 10:
            continue

        pdc = daily_levels.loc[td, "pdc"]
        rth_open = daily_levels.loc[td, "rth_open"]

        if pd.isna(pdc) or pd.isna(rth_open):
            continue

        gap = rth_open - pdc
        gap_abs = abs(gap)

        if gap_abs < 0.5:  # No meaningful gap
            continue

        # Did price fill the gap (return to PDC)?
        if gap > 0:
            # Gap up — need price to come back down to PDC
            filled = np.any(day_bars["low"].values <= pdc)
        else:
            # Gap down — need price to come back up to PDC
            filled = np.any(day_bars["high"].values >= pdc)

        # Time to fill
        fill_time = np.nan
        if filled:
            if gap > 0:
                fill_idx = np.where(day_bars["low"].values <= pdc)[0]
            else:
                fill_idx = np.where(day_bars["high"].values >= pdc)[0]
            if len(fill_idx) > 0:
                fill_bar = day_bars.index[fill_idx[0]]
                fill_time = (fill_bar.hour * 60 + fill_bar.minute) - (9 * 60 + 30)

        results.append({
            "trade_date": td,
            "pdc": pdc,
            "rth_open": rth_open,
            "gap_pts": gap,
            "gap_abs_pts": gap_abs,
            "gap_direction": "up" if gap > 0 else "down",
            "filled": filled,
            "fill_time_min": fill_time,
        })

    df = pd.DataFrame(results)

    if len(df) > 0:
        # Bucket by gap size
        df["gap_bucket"] = pd.cut(df["gap_abs_pts"],
                                   bins=[0, 5, 10, 20, 50, 100, float("inf")],
                                   labels=["0-5", "5-10", "10-20", "20-50", "50-100", "100+"])

        summary = df.groupby("gap_bucket", observed=True).agg(
            count=("filled", "count"),
            fill_rate=("filled", lambda x: x.mean() * 100),
            avg_fill_time_min=("fill_time_min", "mean"),
        )
        log("\nGap Fill by Size:")
        print(summary.to_string())

        # Also by direction
        dir_summary = df.groupby("gap_direction").agg(
            count=("filled", "count"),
            fill_rate=("filled", lambda x: x.mean() * 100),
            avg_gap_pts=("gap_abs_pts", "mean"),
        )
        log("\nGap Fill by Direction:")
        print(dir_summary.to_string())

    return df


def main():
    parser = argparse.ArgumentParser(description="Study 3: Key Level Analysis")
    parser.add_argument("--symbols", nargs="*", help="Symbols to analyze")
    args = parser.parse_args()

    config = get_config()
    cfg_data = config["data"]

    derived_path = Path(cfg_data.derived_dir)
    if args.symbols:
        symbols = args.symbols
    else:
        files = list(derived_path.glob("*_daily_levels.*"))
        symbols = list(set(f.stem.split("_")[0] for f in files))

    for symbol in symbols:
        log(f"\n{'='*60}")
        log(f"STUDY 3: Key Level Analysis — {symbol}")
        log(f"{'='*60}")

        daily_levels = load_derived(f"{symbol}_daily_levels", cfg_data)
        rth = load_derived(f"{symbol}_rth_1min", cfg_data)

        # 3.1: Level touches
        log("\n--- 3.1: PDH/PDL/ONH/ONL Touch Stats ---")
        touches = analyze_level_touches(daily_levels, rth)
        save_results(touches, f"{symbol}_level_test_detail", cfg_data)

        if len(touches) > 0:
            summary = touches.groupby("level").agg(
                total_tests=("touched", "count"),
                pct_broke_through=("broke_through", lambda x: x.mean() * 100),
                pct_rejected=("rejected", lambda x: x.mean() * 100),
                pct_accepted=("accepted", lambda x: x.mean() * 100),
                avg_max_beyond=("max_beyond_pts", "mean"),
                avg_max_retrace=("max_retrace_pts", "mean"),
                avg_num_tests=("num_tests", "mean"),
                avg_first_test_time=("first_test_minute", "mean"),
            )
            save_results(summary, f"{symbol}_key_level_stats", cfg_data)
            print(summary.to_string())

        # 3.2: Weekly open
        log("\n--- 3.2: Weekly Open as S/R ---")
        wo = analyze_weekly_open(daily_levels, rth)
        save_results(wo, f"{symbol}_weekly_open_stats", cfg_data)

        # 3.3: Gap fills
        log("\n--- 3.3: Gap Fill Statistics ---")
        gaps = analyze_gap_fills(daily_levels, rth)
        save_results(gaps, f"{symbol}_gap_fill_stats", cfg_data)

        log(f"\n{symbol} Study 3 complete.")

    log(f"\n{'='*60}")
    log("STUDY 3 COMPLETE")
    log(f"{'='*60}")


if __name__ == "__main__":
    main()
