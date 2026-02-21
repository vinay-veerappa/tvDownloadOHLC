#!/usr/bin/env python3
# strategy_validation/scripts/00_data_prep.py
"""
Data Preparation Script
=======================
Loads raw parquet files, computes session-level reference data,
and caches everything as CSV/JSON so downstream scripts never
touch the parquet files again.

Usage:
    python 00_data_prep.py                           # process all .parquet in input_dir
    python 00_data_prep.py --symbols ES NQ           # process specific symbols
    python 00_data_prep.py --input-dir /path/to/data  # override input directory

Outputs (in derived_dir):
    {symbol}_daily_levels.csv
    {symbol}_session_ranges.csv
    {symbol}_opening_ranges.csv
    {symbol}_rth_1min.csv          (RTH bars only — used by most studies)
    {symbol}_eth_1min.csv          (Full ETH bars — used by session sweep study)
    data_quality_report.json
"""

import argparse
import sys
import os
import json
import numpy as np
import pandas as pd
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import get_config
from scripts.utils import (
    load_parquet, log, timer, assign_trade_date, session_ohlcv_by_date,
    compute_opening_ranges, filter_session, get_rth, time_mask,
    save_derived, check_data_quality, save_results_json
)


@timer
def compute_daily_levels(df: pd.DataFrame, trade_dates: pd.Series,
                         cfg_sess) -> pd.DataFrame:
    """Compute PDH, PDL, PDC, PDO, ONH, ONL, weekly levels for each trade date.
    All vectorized using groupby.
    """
    # --- RTH aggregation ---
    rth_mask = time_mask(df.index, cfg_sess.rth_start, cfg_sess.rth_end)
    rth = df[rth_mask].copy()
    rth["trade_date"] = trade_dates[rth_mask]

    rth_daily = rth.groupby("trade_date").agg(
        rth_open=("open", "first"),
        rth_high=("high", "max"),
        rth_low=("low", "min"),
        rth_close=("close", "last"),
        rth_volume=("volume", "sum"),
    )

    # Previous day levels (shift by 1 trade date)
    rth_daily["pdh"] = rth_daily["rth_high"].shift(1)
    rth_daily["pdl"] = rth_daily["rth_low"].shift(1)
    rth_daily["pdc"] = rth_daily["rth_close"].shift(1)
    rth_daily["pdo"] = rth_daily["rth_open"].shift(1)

    # RTH range
    rth_daily["rth_range"] = rth_daily["rth_high"] - rth_daily["rth_low"]

    # --- Overnight range ---
    # ON = 18:00 prev day to 09:29 current day
    # We need bars from overnight_start to overnight_end
    on_mask = time_mask(df.index, cfg_sess.overnight_start, cfg_sess.overnight_end)
    on = df[on_mask].copy()
    on["trade_date"] = trade_dates[on_mask]

    on_daily = on.groupby("trade_date").agg(
        onh=("high", "max"),
        onl=("low", "min"),
        on_volume=("volume", "sum"),
    )

    # --- Weekly levels ---
    rth_daily["day_of_week"] = pd.to_datetime(rth_daily.index).dayofweek  # 0=Mon

    # Weekly open = Monday's RTH open (forward-fill through the week)
    rth_daily["weekly_open"] = np.where(
        rth_daily["day_of_week"] == 0,
        rth_daily["rth_open"],
        np.nan
    )
    rth_daily["weekly_open"] = rth_daily["weekly_open"].ffill()

    # Week number for grouping
    rth_daily["week_id"] = pd.to_datetime(rth_daily.index).isocalendar().week.values
    rth_daily["year"] = pd.to_datetime(rth_daily.index).year

    # Previous week high/low
    week_group = rth_daily.groupby(["year", "week_id"])
    weekly_hl = week_group.agg(
        week_high=("rth_high", "max"),
        week_low=("rth_low", "min"),
    )

    # Shift weekly levels by 1 week
    weekly_hl["prev_week_high"] = weekly_hl["week_high"].shift(1)
    weekly_hl["prev_week_low"] = weekly_hl["week_low"].shift(1)

    # Merge back
    rth_daily = rth_daily.join(
        weekly_hl[["prev_week_high", "prev_week_low"]],
        on=["year", "week_id"]
    )

    # --- Merge overnight data ---
    result = rth_daily.join(on_daily, how="left")

    # Gap: RTH open vs PDC
    result["gap"] = result["rth_open"] - result["pdc"]
    result["gap_pct"] = result["gap"] / result["pdc"] * 100

    # Clean up helper columns
    result = result.drop(columns=["year", "week_id"], errors="ignore")

    return result


@timer
def compute_session_ranges(df: pd.DataFrame, trade_dates: pd.Series,
                           cfg_sess) -> pd.DataFrame:
    """Compute Asia, London, pre-market session ranges per trade date."""

    sessions = {
        "asia": (cfg_sess.asia_start, cfg_sess.asia_end),
        "london": (cfg_sess.london_start, cfg_sess.london_end),
        "london_open": (cfg_sess.london_open_start, cfg_sess.london_open_end),
        "pre_market": (cfg_sess.pre_market_start, cfg_sess.pre_market_end),
    }

    all_results = {}
    for name, (start, end) in sessions.items():
        agg = session_ohlcv_by_date(df, trade_dates, start, end)
        agg.columns = [f"{name}_{c.replace('session_', '')}" for c in agg.columns]
        for col in agg.columns:
            all_results[col] = agg[col]

    result = pd.DataFrame(all_results)

    # Session ranges
    for name in sessions:
        result[f"{name}_range"] = result[f"{name}_high"] - result[f"{name}_low"]

    return result


def main():
    parser = argparse.ArgumentParser(description="Prepare derived data from raw parquet files")
    parser.add_argument("--symbols", nargs="*", help="Specific symbols to process (default: all parquet files)")
    parser.add_argument("--input-dir", help="Override input directory")
    parser.add_argument("--output-format", choices=["csv", "json"], default="csv",
                        help="Output format for derived data")
    args = parser.parse_args()

    config = get_config()
    cfg_data = config["data"]
    cfg_sess = config["sessions"]
    cfg_or = config["opening_range"]

    if args.input_dir:
        cfg_data.input_dir = args.input_dir
    if args.output_format:
        cfg_data.derived_format = args.output_format

    cfg_data.ensure_dirs()

    # Find parquet files
    input_path = Path(cfg_data.input_dir)
    if args.symbols:
        parquet_files = []
        for sym in args.symbols:
            matches = list(input_path.glob(f"*{sym}*.[pP]arquet")) + \
                      list(input_path.glob(f"*{sym}*.parquet"))
            parquet_files.extend(matches)
    else:
        parquet_files = list(input_path.glob("*.parquet"))

    if not parquet_files:
        log(f"ERROR: No parquet files found in {input_path}")
        log(f"  Expected files like: ES_1min.parquet, NQ_1min.parquet")
        sys.exit(1)

    log(f"Found {len(parquet_files)} parquet files: {[f.name for f in parquet_files]}")

    quality_reports = {}

    for pq_file in parquet_files:
        # Extract symbol from filename (e.g., "ES_1min.parquet" → "ES")
        symbol = pq_file.stem.split("_")[0].upper()
        log(f"\n{'='*60}")
        log(f"Processing {symbol} from {pq_file.name}")
        log(f"{'='*60}")

        # Load raw data
        df = load_parquet(str(pq_file), cfg_data)

        # Data quality check
        quality = check_data_quality(df, symbol)
        quality_reports[symbol] = quality
        log(f"  Trading days: {quality['unique_trading_days']}")
        log(f"  OHLC violations: {quality['ohlc_violations']}")
        log(f"  Duplicate timestamps: {quality['duplicate_timestamps']}")
        if quality['suspicious_gaps']:
            log(f"  Suspicious gaps: {len(quality['suspicious_gaps'])}")
            for gap in quality['suspicious_gaps'][:5]:
                log(f"    {gap[0]} → {gap[1]} ({gap[2]} days)")

        # Remove duplicates if any
        if quality['duplicate_timestamps'] > 0:
            df = df[~df.index.duplicated(keep='first')]

        # Assign trade dates
        log("Assigning trade dates...")
        trade_dates = assign_trade_date(df, cfg_sess)

        # Compute daily levels
        log("Computing daily levels...")
        daily_levels = compute_daily_levels(df, trade_dates, cfg_sess)
        save_derived(daily_levels, f"{symbol}_daily_levels", cfg_data)

        # Compute session ranges
        log("Computing session ranges...")
        session_ranges = compute_session_ranges(df, trade_dates, cfg_sess)
        save_derived(session_ranges, f"{symbol}_session_ranges", cfg_data)

        # Compute opening ranges
        log(f"Computing opening ranges (durations: {cfg_or.or_durations_minutes})...")
        or_data = compute_opening_ranges(df, trade_dates, cfg_or)
        save_derived(or_data, f"{symbol}_opening_ranges", cfg_data)

        # Save RTH-only 1-min bars (most studies only need RTH)
        log("Extracting RTH bars...")
        rth = get_rth(df, cfg_sess).copy()
        rth["trade_date"] = trade_dates[rth.index].values
        save_derived(rth, f"{symbol}_rth_1min", cfg_data)
        log(f"  RTH bars: {len(rth)}")

        # Save full ETH bars (needed for session sweep study)
        log("Saving ETH bars...")
        df_eth = df.copy()
        df_eth["trade_date"] = trade_dates.values
        save_derived(df_eth, f"{symbol}_eth_1min", cfg_data)
        log(f"  ETH bars: {len(df_eth)}")

        log(f"\n{symbol} complete.")

    # Save quality report
    save_results_json(quality_reports, "data_quality_report", cfg_data)

    log(f"\n{'='*60}")
    log("DATA PREPARATION COMPLETE")
    log(f"{'='*60}")
    log(f"Derived data saved to: {cfg_data.derived_dir}/")
    log(f"Quality report: {cfg_data.results_dir}/data_quality_report.json")
    log(f"\nFiles created per symbol:")
    log(f"  {{symbol}}_daily_levels.{cfg_data.derived_format}")
    log(f"  {{symbol}}_session_ranges.{cfg_data.derived_format}")
    log(f"  {{symbol}}_opening_ranges.{cfg_data.derived_format}")
    log(f"  {{symbol}}_rth_1min.{cfg_data.derived_format}")
    log(f"  {{symbol}}_eth_1min.{cfg_data.derived_format}")


if __name__ == "__main__":
    main()
