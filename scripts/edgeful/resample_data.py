"""
Resample Data Utility
=====================
Regenerates derivable OHLCV parquet files from the 1m source.

SAFE TO RUN: Only writes to DERIVABLE tier files (_5m, _15m, _1h, _4h).
NEVER TOUCHES: _1d, _1W, _1d_unadjusted parquets (settlement close prices).

Usage:
  # Regenerate 5m, 15m, 1h, 4h for all instruments
  python -m scripts.edgeful.resample_data

  # Specific instruments
  python -m scripts.edgeful.resample_data --instruments NQ1,ES1

  # Specific timeframes only
  python -m scripts.edgeful.resample_data --timeframes 15m,1h

  # Verify only (no write)
  python -m scripts.edgeful.resample_data --dry-run
"""

import argparse
import pandas as pd
import numpy as np
import time
from pathlib import Path

from scripts.edgeful.lib.data_loader import get_loader
from scripts.libs_py.nqstats.sessions import normalize_to_eastern

# ── Constants ──────────────────────────────────────────────────────────────────
DATA_DIR = Path("data")
INSTRUMENTS = ["NQ1", "ES1", "YM1", "RTY1", "CL1", "GC1"]

# Derivable timeframes: (pandas_rule, output_suffix)
# origin='start_day' aligns to midnight, matching TradingView bar boundaries.
TIMEFRAMES = {
    "5m":  "5min",
    "15m": "15min",
    "1h":  "1h",
    "4h":  "4h",
}

# Columns in standard OHLCV order
OHLCV_COLS = ["open", "high", "low", "close", "volume"]

# UNTOUCHABLE suffixes — never write to these
PROTECTED_SUFFIXES = {"1d", "1W", "1d_unadjusted"}


def resample_1m_to(df_1m: pd.DataFrame, rule: str) -> pd.DataFrame:
    """
    Resample a 1m OHLCV DataFrame to the given pandas rule.
    Preserves all OHLCV columns. origin='start_day' matches TradingView bar boundaries.
    """
    agg = {
        "open":   "first",
        "high":   "max",
        "low":    "min",
        "close":  "last",
        "volume": "sum",
    }
    # Only aggregate columns that exist
    agg = {k: v for k, v in agg.items() if k in df_1m.columns}
    df_rs = df_1m.resample(rule, origin="start_day").agg(agg).dropna(how="all")
    # Drop bars where there were no actual trades (all NaN)
    if "close" in df_rs.columns:
        df_rs = df_rs.dropna(subset=["close"])
    return df_rs


def regenerate_symbol(
    symbol: str,
    timeframes: list[str],
    dry_run: bool = False,
) -> dict:
    """
    Regenerate all requested derivable timeframes for one symbol.
    Returns a dict of {timeframe: row_count}.
    """
    loader = get_loader()
    results = {}

    print(f"\n[{symbol}] Loading 1m source (live-fused)...")
    df_1m = loader.load_1m(symbol)
    if df_1m.empty:
        print(f"  -> No 1m data found.")
        return results

    print(f"  -> {len(df_1m):,} 1m bars  [{df_1m.index[0]}  →  {df_1m.index[-1]}]")

    for tf in timeframes:
        # Safety guard: never write to protected files
        if tf in PROTECTED_SUFFIXES:
            print(f"  -> [{tf}] SKIPPED — protected tier (settlement data)")
            continue

        rule = TIMEFRAMES[tf]
        out_path = DATA_DIR / f"{symbol}_{tf}.parquet"

        print(f"  -> Resampling to {tf} ({rule})...")
        df_rs = resample_1m_to(df_1m, rule)
        print(f"     {len(df_rs):,} bars  [{df_rs.index[0]}  →  {df_rs.index[-1]}]")

        if dry_run:
            print(f"     [DRY RUN] Would write to {out_path}")
        else:
            df_rs.to_parquet(out_path)
            size_mb = out_path.stat().st_size / 1_048_576
            print(f"     Written → {out_path}  ({size_mb:.1f} MB)")

        results[tf] = len(df_rs)

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Regenerate derivable OHLCV parquets (5m/15m/1h/4h) from 1m source."
    )
    parser.add_argument(
        "--instruments", type=str,
        help=f"Comma-separated symbols (default: {', '.join(INSTRUMENTS)})",
    )
    parser.add_argument(
        "--timeframes", type=str,
        default=",".join(TIMEFRAMES.keys()),
        help=f"Comma-separated timeframes to generate (default: {', '.join(TIMEFRAMES.keys())})",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview what would be written without writing any files",
    )
    args = parser.parse_args()

    target_symbols = args.instruments.split(",") if args.instruments else INSTRUMENTS
    target_tfs = [tf.strip() for tf in args.timeframes.split(",")]

    # Validate timeframes
    invalid = [tf for tf in target_tfs if tf not in TIMEFRAMES]
    if invalid:
        print(f"[ERROR] Unknown timeframes: {invalid}. Valid: {list(TIMEFRAMES.keys())}")
        return

    print("=== Resample Data Utility ===")
    print(f"Instruments: {target_symbols}")
    print(f"Timeframes:  {target_tfs}")
    print(f"Mode:        {'DRY RUN (no writes)' if args.dry_run else 'WRITE'}")
    print(f"Source:      {{symbol}}_1m.parquet (live-fused)")
    print(f"Protected:   _1d, _1W, _1d_unadjusted  (never touched)")
    print()

    t0 = time.time()
    summary = {}

    for symbol in target_symbols:
        results = regenerate_symbol(symbol, target_tfs, dry_run=args.dry_run)
        summary[symbol] = results

    elapsed = time.time() - t0
    print("\n=== Summary ===")
    for sym, tfs in summary.items():
        for tf, n in tfs.items():
            status = "[DRY RUN]" if args.dry_run else "written"
            print(f"  {sym:6s} {tf:4s}: {n:>8,} bars  {status}")
    print(f"\nCompleted in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
