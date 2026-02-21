#!/usr/bin/env python3
# strategy_validation/scripts/05_weekly_profile_study.py
"""
Study 5: Day-of-Week and Weekly Profile
=========================================
Validates ICT weekly profile concepts.

Usage:
    python 05_weekly_profile_study.py
    python 05_weekly_profile_study.py --symbols ES NQ

Outputs:
    {symbol}_weekly_extreme_days.csv
    {symbol}_daily_continuation.csv
    {symbol}_weekly_profile_summary.json
"""

import argparse
import sys
import os
import numpy as np
import pandas as pd
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import get_config
from scripts.utils import load_derived, save_results, save_results_json, log, timer

DAY_NAMES = {0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday", 4: "Friday"}


@timer
def analyze_weekly_extremes(daily_levels: pd.DataFrame) -> tuple:
    """Which day of week makes the weekly high/low? Range contribution per day."""
    dl = daily_levels.copy()
    dl["date"] = pd.to_datetime(dl.index)
    dl["year"] = dl["date"].dt.isocalendar().year.astype(int).values
    dl["week"] = dl["date"].dt.isocalendar().week.astype(int).values
    dl["dow"] = dl["date"].dt.dayofweek

    day_records = []
    week_records = []

    for (yr, wk), grp in dl.groupby(["year", "week"]):
        if len(grp) < 3:
            continue

        week_high = grp["rth_high"].max()
        week_low = grp["rth_low"].min()
        week_range = week_high - week_low
        high_dow = grp.loc[grp["rth_high"].idxmax(), "dow"]
        low_dow = grp.loc[grp["rth_low"].idxmin(), "dow"]

        mon = grp[grp["dow"] == 0]
        mon_h_is_wk_h = (mon["rth_high"].iloc[0] == week_high) if len(mon) > 0 else False
        mon_l_is_wk_l = (mon["rth_low"].iloc[0] == week_low) if len(mon) > 0 else False

        week_records.append({
            "year": yr, "week": wk, "week_high_day": high_dow,
            "week_low_day": low_dow, "week_range": week_range,
            "mon_high_is_week_high": mon_h_is_wk_h,
            "mon_low_is_week_low": mon_l_is_wk_l,
        })

        for _, row in grp.iterrows():
            day_records.append({
                "year": yr, "week": wk, "day_of_week": row["dow"],
                "rth_range": row["rth_range"],
                "range_pct_of_weekly": row["rth_range"] / week_range * 100 if week_range > 0 else 0,
            })

    df_weeks = pd.DataFrame(week_records)
    df_days = pd.DataFrame(day_records)

    n_weeks = len(df_weeks)
    summary_rows = []
    for dow, name in DAY_NAMES.items():
        dow_days = df_days[df_days["day_of_week"] == dow]
        summary_rows.append({
            "day": name,
            "pct_week_high": (df_weeks["week_high_day"] == dow).sum() / n_weeks * 100,
            "pct_week_low": (df_weeks["week_low_day"] == dow).sum() / n_weeks * 100,
            "avg_range_contribution_pct": dow_days["range_pct_of_weekly"].mean(),
            "avg_daily_range_pts": dow_days["rth_range"].mean(),
        })

    summary = pd.DataFrame(summary_rows)

    extra = {
        "total_weeks": n_weeks,
        "mon_high_holds_pct": df_weeks["mon_high_is_week_high"].mean() * 100,
        "mon_low_holds_pct": df_weeks["mon_low_is_week_low"].mean() * 100,
    }

    return summary, extra


@timer
def analyze_daily_continuation(daily_levels: pd.DataFrame) -> pd.DataFrame:
    """Day-to-day continuation/reversal rates."""
    dl = daily_levels.copy()
    dl["date"] = pd.to_datetime(dl.index)
    dl["dow"] = dl["date"].dt.dayofweek

    dl["direction"] = np.where(
        dl["rth_close"] > dl["rth_open"], "up",
        np.where(dl["rth_close"] < dl["rth_open"], "down", "flat")
    )
    dl["next_direction"] = dl["direction"].shift(-1)
    dl["next_dow"] = dl["dow"].shift(-1)

    # Consecutive trading days
    dl["is_consecutive"] = (
        (dl["next_dow"] - dl["dow"] == 1) |
        ((dl["dow"] == 4) & (dl["next_dow"] == 0))
    )

    consec = dl[dl["is_consecutive"] & dl["direction"].isin(["up", "down"])].copy()

    results = []
    for dow, name in DAY_NAMES.items():
        dd = consec[consec["dow"] == dow]
        if len(dd) < 20:
            continue

        up = dd[dd["direction"] == "up"]
        dn = dd[dd["direction"] == "down"]

        results.append({
            "day": name,
            "total_days": len(dd),
            "pct_bullish": len(up) / len(dd) * 100,
            "pct_bearish": len(dn) / len(dd) * 100,
            "after_up_continue_pct": (up["next_direction"] == "up").mean() * 100 if len(up) > 0 else 0,
            "after_up_reverse_pct": (up["next_direction"] == "down").mean() * 100 if len(up) > 0 else 0,
            "after_down_continue_pct": (dn["next_direction"] == "down").mean() * 100 if len(dn) > 0 else 0,
            "after_down_reverse_pct": (dn["next_direction"] == "up").mean() * 100 if len(dn) > 0 else 0,
            "avg_range_pts": dd["rth_range"].mean(),
        })

    return pd.DataFrame(results)


@timer
def analyze_weekly_patterns(daily_levels: pd.DataFrame) -> pd.DataFrame:
    """Specific ICT weekly patterns:
    - Monday range expansion direction vs week outcome
    - Tue/Wed as delivery days
    - Thursday reversal tendency
    """
    dl = daily_levels.copy()
    dl["date"] = pd.to_datetime(dl.index)
    dl["year"] = dl["date"].dt.isocalendar().year.astype(int).values
    dl["week"] = dl["date"].dt.isocalendar().week.astype(int).values
    dl["dow"] = dl["date"].dt.dayofweek
    dl["direction"] = np.where(dl["rth_close"] > dl["rth_open"], "up", "down")

    results = []
    for (yr, wk), grp in dl.groupby(["year", "week"]):
        if len(grp) < 4:
            continue

        mon = grp[grp["dow"] == 0]
        tue = grp[grp["dow"] == 1]
        wed = grp[grp["dow"] == 2]
        thu = grp[grp["dow"] == 3]

        if any(len(d) == 0 for d in [mon, tue, wed, thu]):
            continue

        mon_dir = mon["direction"].iloc[0]
        tue_dir = tue["direction"].iloc[0]
        wed_dir = wed["direction"].iloc[0]
        thu_dir = thu["direction"].iloc[0]

        # Week net direction
        week_open = mon["rth_open"].iloc[0]
        week_close = grp["rth_close"].iloc[-1]
        week_dir = "up" if week_close > week_open else "down"

        results.append({
            "year": yr, "week": wk,
            "mon_dir": mon_dir, "tue_dir": tue_dir,
            "wed_dir": wed_dir, "thu_dir": thu_dir,
            "week_dir": week_dir,
            "mon_matches_week": mon_dir == week_dir,
            "tue_matches_week": tue_dir == week_dir,
            "wed_matches_week": wed_dir == week_dir,
            "thu_reverses_wed": thu_dir != wed_dir,
        })

    df = pd.DataFrame(results)
    if len(df) > 0:
        n = len(df)
        pattern_summary = {
            "total_weeks": n,
            "mon_matches_week_pct": df["mon_matches_week"].mean() * 100,
            "tue_matches_week_pct": df["tue_matches_week"].mean() * 100,
            "wed_matches_week_pct": df["wed_matches_week"].mean() * 100,
            "thu_reverses_wed_pct": df["thu_reverses_wed"].mean() * 100,
            # Specific patterns
            "mon_up_week_up_pct": (
                df[df["mon_dir"] == "up"]["week_dir"] == "up"
            ).mean() * 100 if (df["mon_dir"] == "up").any() else 0,
            "mon_down_week_down_pct": (
                df[df["mon_dir"] == "down"]["week_dir"] == "down"
            ).mean() * 100 if (df["mon_dir"] == "down").any() else 0,
        }
        return df, pattern_summary

    return df, {}


def main():
    parser = argparse.ArgumentParser(description="Study 5: Weekly Profile Analysis")
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
        log(f"STUDY 5: Weekly Profile — {symbol}")
        log(f"{'='*60}")

        daily_levels = load_derived(f"{symbol}_daily_levels", cfg_data)

        # 5.1: Weekly extremes
        log("\n--- 5.1: Weekly Extreme Days ---")
        extremes, extra = analyze_weekly_extremes(daily_levels)
        save_results(extremes, f"{symbol}_weekly_extreme_days", cfg_data)
        print(extremes.to_string(index=False))
        log(f"\n  Mon high holds as week high: {extra['mon_high_holds_pct']:.1f}%")
        log(f"  Mon low holds as week low: {extra['mon_low_holds_pct']:.1f}%")

        # 5.2: Continuation rates
        log("\n--- 5.2: Day-to-Day Continuation ---")
        cont = analyze_daily_continuation(daily_levels)
        save_results(cont, f"{symbol}_daily_continuation", cfg_data)
        print(cont.to_string(index=False))

        # 5.3: Weekly patterns
        log("\n--- 5.3: ICT Weekly Patterns ---")
        patterns, pat_summary = analyze_weekly_patterns(daily_levels)
        if len(patterns) > 0:
            save_results_json(pat_summary, f"{symbol}_weekly_pattern_summary", cfg_data)
            log("\nWeekly Pattern Summary:")
            for k, v in pat_summary.items():
                log(f"  {k}: {v:.1f}" if isinstance(v, float) else f"  {k}: {v}")

        log(f"\n{symbol} Study 5 complete.")

    log(f"\n{'='*60}")
    log("STUDY 5 COMPLETE")
    log(f"{'='*60}")


if __name__ == "__main__":
    main()
