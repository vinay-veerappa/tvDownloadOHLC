#!/usr/bin/env python3
# strategy_validation/scripts/02_session_sweep_study.py
"""
Study 2: Session Sweep Sequences
=================================
Validates ICT session sweep concepts:
- London sweeps Asia liquidity → NY response
- Overnight range as day framing
- Session-to-session directional relationships

Usage:
    python 02_session_sweep_study.py
    python 02_session_sweep_study.py --symbols ES NQ

Outputs:
    {symbol}_london_asia_sweeps.csv      — London vs Asia sweep patterns
    {symbol}_ny_response.csv             — NY response to London sweeps
    {symbol}_overnight_framing.csv       — Overnight range as day frame
    {symbol}_session_sequence_summary.json — Overall session flow summary
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


@timer
def analyze_london_asia_sweeps(session_ranges: pd.DataFrame) -> pd.DataFrame:
    """Analysis 2.1: How does London interact with Asia's range?"""

    asia_h = session_ranges["asia_high"]
    asia_l = session_ranges["asia_low"]
    london_h = session_ranges["london_high"]
    london_l = session_ranges["london_low"]

    # Did London sweep Asia high/low?
    swept_high = london_h > asia_h
    swept_low = london_l < asia_l
    swept_both = swept_high & swept_low
    swept_neither = ~swept_high & ~swept_low
    swept_high_only = swept_high & ~swept_low
    swept_low_only = swept_low & ~swept_high

    # London net direction
    london_open = session_ranges["london_open"]
    london_close = session_ranges["london_close"]
    london_bullish = london_close > london_open
    london_bearish = london_close < london_open

    n = len(session_ranges)
    valid = (~asia_h.isna() & ~london_h.isna())
    n_valid = valid.sum()

    result = pd.DataFrame([{
        "total_days": n_valid,
        "pct_swept_asia_high": swept_high[valid].sum() / n_valid * 100,
        "pct_swept_asia_low": swept_low[valid].sum() / n_valid * 100,
        "pct_swept_both": swept_both[valid].sum() / n_valid * 100,
        "pct_swept_neither": swept_neither[valid].sum() / n_valid * 100,
        "pct_swept_high_only": swept_high_only[valid].sum() / n_valid * 100,
        "pct_swept_low_only": swept_low_only[valid].sum() / n_valid * 100,
        "pct_london_bullish": london_bullish[valid].sum() / n_valid * 100,
        "pct_london_bearish": london_bearish[valid].sum() / n_valid * 100,
        # When London sweeps high only, is it bullish or bearish?
        "pct_bullish_when_high_sweep": london_bullish[swept_high_only & valid].sum() / max(swept_high_only[valid].sum(), 1) * 100,
        "pct_bearish_when_low_sweep": london_bearish[swept_low_only & valid].sum() / max(swept_low_only[valid].sum(), 1) * 100,
    }])

    return result


@timer
def analyze_ny_response(session_ranges: pd.DataFrame, daily_levels: pd.DataFrame,
                        rth: pd.DataFrame) -> pd.DataFrame:
    """Analysis 2.2: How does NY respond to London's sweep?

    Focus on single-side sweeps (cleaner signal).
    """
    results = []

    asia_h = session_ranges["asia_high"]
    asia_l = session_ranges["asia_low"]
    london_h = session_ranges["london_high"]
    london_l = session_ranges["london_low"]

    swept_high_only = (london_h > asia_h) & ~(london_l < asia_l)
    swept_low_only = (london_l < asia_l) & ~(london_h > asia_h)

    common_dates = session_ranges.index.intersection(daily_levels.index)

    # NY session = 9:30-12:00 (first 2.5 hours)
    for td in common_dates:
        td_str = str(td)
        ny_bars = rth[(rth["trade_date"].astype(str) == td_str)]
        if len(ny_bars) == 0:
            continue

        # Filter to 9:30-12:00
        ny_minutes = ny_bars.index.hour * 60 + ny_bars.index.minute
        ny_am = ny_bars[(ny_minutes >= 570) & (ny_minutes <= 720)]  # 9:30-12:00
        if len(ny_am) == 0:
            continue

        ny_high = ny_am["high"].max()
        ny_low = ny_am["low"].min()
        ny_close = ny_am["close"].iloc[-1]
        ny_open = ny_am["open"].iloc[0]

        if td not in session_ranges.index:
            continue

        ah = asia_h.get(td, np.nan)
        al = asia_l.get(td, np.nan)

        if pd.isna(ah) or pd.isna(al):
            continue

        entry = {
            "trade_date": td,
            "asia_high": ah,
            "asia_low": al,
            "ny_high": ny_high,
            "ny_low": ny_low,
            "ny_open": ny_open,
            "ny_close": ny_close,
            "ny_direction": "up" if ny_close > ny_open else "down",
        }

        if td in swept_high_only.index and swept_high_only.get(td, False):
            entry["london_sweep"] = "high_only"
            entry["ny_reversed"] = ny_low < al  # NY took out Asia low
            entry["ny_continuation"] = ny_high > london_h.get(td, np.nan)  # NY went higher than London
            entry["ny_excursion_from_asia_low"] = al - ny_low if ny_low < al else 0
        elif td in swept_low_only.index and swept_low_only.get(td, False):
            entry["london_sweep"] = "low_only"
            entry["ny_reversed"] = ny_high > ah  # NY took out Asia high
            entry["ny_continuation"] = ny_low < london_l.get(td, np.nan)
            entry["ny_excursion_from_asia_high"] = ny_high - ah if ny_high > ah else 0
        else:
            entry["london_sweep"] = "both_or_neither"
            entry["ny_reversed"] = False
            entry["ny_continuation"] = False

        results.append(entry)

    df = pd.DataFrame(results)

    # Compute summary by sweep type
    if len(df) > 0:
        summary = df.groupby("london_sweep").agg(
            count=("trade_date", "count"),
            pct_ny_reversed=("ny_reversed", lambda x: x.mean() * 100),
            pct_ny_continued=("ny_continuation", lambda x: x.mean() * 100),
            pct_ny_up=("ny_direction", lambda x: (x == "up").mean() * 100),
        )
        log("\nNY Response Summary:")
        print(summary.to_string())

    return df


@timer
def analyze_overnight_framing(daily_levels: pd.DataFrame, rth: pd.DataFrame) -> pd.DataFrame:
    """Analysis 2.3: How well does the overnight range frame the day?"""
    results = []

    for td in daily_levels.index:
        onh = daily_levels.loc[td, "onh"]
        onl = daily_levels.loc[td, "onl"]
        rth_h = daily_levels.loc[td, "rth_high"]
        rth_l = daily_levels.loc[td, "rth_low"]

        if any(pd.isna(x) for x in [onh, onl, rth_h, rth_l]):
            continue

        results.append({
            "trade_date": td,
            "onh": onh,
            "onl": onl,
            "rth_high": rth_h,
            "rth_low": rth_l,
            "on_range": onh - onl,
            "rth_range": rth_h - rth_l,
            "onh_held_as_high": rth_h <= onh,  # RTH never exceeded ON high
            "onl_held_as_low": rth_l >= onl,    # RTH never went below ON low
            "inside_overnight": (rth_h <= onh) and (rth_l >= onl),
            "onh_broken_up": rth_h > onh,
            "onl_broken_down": rth_l < onl,
            "continuation_above_onh": rth_h - onh if rth_h > onh else 0,
            "continuation_below_onl": onl - rth_l if rth_l < onl else 0,
        })

    df = pd.DataFrame(results)

    if len(df) > 0:
        n = len(df)
        summary = {
            "total_days": n,
            "pct_onh_held": df["onh_held_as_high"].sum() / n * 100,
            "pct_onl_held": df["onl_held_as_low"].sum() / n * 100,
            "pct_inside_overnight": df["inside_overnight"].sum() / n * 100,
            "pct_onh_broken": df["onh_broken_up"].sum() / n * 100,
            "pct_onl_broken": df["onl_broken_down"].sum() / n * 100,
            "avg_continuation_above_onh": df.loc[df["onh_broken_up"], "continuation_above_onh"].mean(),
            "avg_continuation_below_onl": df.loc[df["onl_broken_down"], "continuation_below_onl"].mean(),
        }
        log("\nOvernight Framing Summary:")
        for k, v in summary.items():
            log(f"  {k}: {v:.2f}")

    return df


def main():
    parser = argparse.ArgumentParser(description="Study 2: Session Sweep Sequences")
    parser.add_argument("--symbols", nargs="*", help="Symbols to analyze")
    args = parser.parse_args()

    config = get_config()
    cfg_data = config["data"]

    derived_path = Path(cfg_data.derived_dir)
    if args.symbols:
        symbols = args.symbols
    else:
        files = list(derived_path.glob("*_session_ranges.*"))
        symbols = list(set(f.stem.split("_")[0] for f in files))

    if not symbols:
        log("ERROR: No derived data found. Run 00_data_prep.py first.")
        sys.exit(1)

    for symbol in symbols:
        log(f"\n{'='*60}")
        log(f"STUDY 2: Session Sweep Analysis — {symbol}")
        log(f"{'='*60}")

        session_ranges = load_derived(f"{symbol}_session_ranges", cfg_data)
        daily_levels = load_derived(f"{symbol}_daily_levels", cfg_data)
        rth = load_derived(f"{symbol}_rth_1min", cfg_data)

        # 2.1: London vs Asia
        log("\n--- 2.1: London-Asia Sweeps ---")
        la_sweeps = analyze_london_asia_sweeps(session_ranges)
        save_results(la_sweeps, f"{symbol}_london_asia_sweeps", cfg_data)
        print(la_sweeps.to_string())

        # 2.2: NY Response
        log("\n--- 2.2: NY Response to London Sweeps ---")
        ny_resp = analyze_ny_response(session_ranges, daily_levels, rth)
        save_results(ny_resp, f"{symbol}_ny_response", cfg_data)

        # 2.3: Overnight Framing
        log("\n--- 2.3: Overnight Range Framing ---")
        on_frame = analyze_overnight_framing(daily_levels, rth)
        save_results(on_frame, f"{symbol}_overnight_framing", cfg_data)

        log(f"\n{symbol} Study 2 complete.")

    log(f"\n{'='*60}")
    log("STUDY 2 COMPLETE")
    log(f"{'='*60}")


if __name__ == "__main__":
    main()
