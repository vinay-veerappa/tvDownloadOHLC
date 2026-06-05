"""
FVG Database Generator
======================
Generates and incrementally maintains per-symbol, per-timeframe FVG databases in
data/derived/ICT/{symbol}_fvg_{timeframe}.parquet

FVGs are detected on each timeframe by resampling from the 1m source (live-fused).
Only FVG-positive rows (~1% of bars) are stored.

Schema:
  bar_time            datetime64[ns]  UTC-naive bar open time (index)
  symbol              str
  fvg_type            int64           -1 bearish, 1 bullish
  fvg_top             float64
  fvg_bottom          float64
  fvg_finalized_time  datetime64[ns]
  logical_date        date
  timeframe           str             e.g. '5m', '15m', '1h', '4h'

Usage:
  # All instruments, all timeframes, incremental
  python -m scripts.edgeful.fvg_database

  # Specific instruments + timeframes
  python -m scripts.edgeful.fvg_database --instruments NQ1,ES1 --timeframes 5m,15m

  # Full rebuild from scratch
  python -m scripts.edgeful.fvg_database --full-regen
"""

import argparse
import pandas as pd
import time
from pathlib import Path

from scripts.edgeful.lib.data_loader import get_loader
from scripts.libs_py.nqstats.ib import detect_fvgs_v5
from scripts.libs_py.nqstats.sessions import (
    normalize_to_eastern,
    get_logical_trading_date,
)

# ── Constants ──────────────────────────────────────────────────────────────────
INSTRUMENTS = ["NQ1", "ES1", "YM1", "RTY1", "CL1", "GC1"]
ICT_DIR = Path("data/derived/ICT")

# Supported timeframes: label -> pandas resample rule
TIMEFRAME_RULES = {
    "5m":  "5min",
    "15m": "15min",
    "1h":  "1h",
    "4h":  "4h",
}
DEFAULT_TIMEFRAMES = list(TIMEFRAME_RULES.keys())


def db_path(symbol: str, tf: str) -> Path:
    return ICT_DIR / f"{symbol}_fvg_{tf}.parquet"


def build_fvg_db(symbol: str, df_1m: pd.DataFrame, tf: str) -> pd.DataFrame:
    """
    Resample df_1m to the given timeframe, run detect_fvgs_v5, return
    FVG-positive rows with logical_date and timeframe columns attached.
    """
    rule = TIMEFRAME_RULES[tf]
    df_1m_norm = normalize_to_eastern(df_1m)
    df_rs = (
        df_1m_norm[["high", "low"]]
        .resample(rule, origin="start_day")
        .agg({"high": "max", "low": "min"})
        .dropna()
    )

    fvg_raw = detect_fvgs_v5(df_rs, rule)
    fvg_raw["logical_date"] = get_logical_trading_date(fvg_raw.index)

    # Keep only bars where an FVG was detected
    fvg_pos = fvg_raw[fvg_raw["fvg_type"] != 0].copy()
    fvg_pos.index.name = "bar_time"
    fvg_pos.insert(0, "symbol", symbol)
    fvg_pos["timeframe"] = tf

    return fvg_pos


def update_symbol_tf(symbol: str, tf: str, df_1m_full: pd.DataFrame, full_regen: bool) -> int:
    """
    Incrementally update (or fully rebuild) the FVG database for one symbol+timeframe.
    df_1m_full is the complete live-fused 1m history (pre-loaded, shared across TFs).
    Returns the number of new rows written.
    """
    out = db_path(symbol, tf)
    start_date = None

    if not full_regen and out.exists():
        existing = pd.read_parquet(out)
        if not existing.empty:
            last_bar = existing.index.max()
            start_date = (last_bar + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
            print(f"    [{tf}] Incremental from {start_date}  (existing: {len(existing):,} rows)")
    else:
        print(f"    [{tf}] Full build from scratch")

    # Filter 1m bars to only the new date range
    df_1m = df_1m_full
    if start_date:
        df_1m = df_1m[df_1m.index >= pd.to_datetime(start_date)]

    if df_1m.empty:
        print(f"    [{tf}] No new bars — already up to date.")
        return 0

    new_fvgs = build_fvg_db(symbol, df_1m, tf)
    print(f"    [{tf}] {len(new_fvgs):,} new FVG rows detected")

    if new_fvgs.empty:
        return 0

    # Merge with existing and write
    if out.exists() and not full_regen:
        existing = pd.read_parquet(out)
        combined = pd.concat([existing, new_fvgs])
        combined = combined[~combined.index.duplicated(keep="last")].sort_index()
    else:
        combined = new_fvgs.sort_index()

    combined.to_parquet(out)
    size_kb = out.stat().st_size / 1024
    print(f"    [{tf}] Wrote {len(combined):,} total rows -> {out.name}  ({size_kb:.0f} KB)")
    return len(new_fvgs)


def main():
    parser = argparse.ArgumentParser(
        description="FVG Database Generator — builds/updates data/derived/ICT/{sym}_fvg_{tf}.parquet"
    )
    parser.add_argument(
        "--instruments", type=str,
        help=f"Comma-separated instruments (default: {', '.join(INSTRUMENTS)})",
    )
    parser.add_argument(
        "--timeframes", type=str,
        default=",".join(DEFAULT_TIMEFRAMES),
        help=f"Comma-separated timeframes (default: {', '.join(DEFAULT_TIMEFRAMES)})",
    )
    parser.add_argument(
        "--full-regen", action="store_true",
        help="Rebuild all FVG databases from scratch (ignores existing files)",
    )
    args = parser.parse_args()

    target_symbols = args.instruments.split(",") if args.instruments else INSTRUMENTS
    target_tfs = [tf.strip() for tf in args.timeframes.split(",")]

    invalid_tfs = [tf for tf in target_tfs if tf not in TIMEFRAME_RULES]
    if invalid_tfs:
        print(f"[ERROR] Unknown timeframes: {invalid_tfs}. Valid: {DEFAULT_TIMEFRAMES}")
        return

    ICT_DIR.mkdir(parents=True, exist_ok=True)

    print("=== FVG Database Generator ===")
    print(f"Instruments: {target_symbols}")
    print(f"Timeframes:  {target_tfs}")
    print(f"Mode:        {'Full rebuild' if args.full_regen else 'Incremental update'}")
    print(f"Output:      {ICT_DIR}")
    print()

    loader = get_loader()
    t0 = time.time()
    total_new = 0

    for symbol in target_symbols:
        print(f"[{symbol}]")
        try:
            # Load full 1m history once — shared across all timeframes for this symbol
            df_1m_full = loader.load_1m(symbol)
            if df_1m_full.empty:
                print(f"  -> No 1m data found. Skipping.")
                continue
            print(f"  -> Loaded {len(df_1m_full):,} 1m bars  [{df_1m_full.index[0]} -> {df_1m_full.index[-1]}]")

            for tf in target_tfs:
                n = update_symbol_tf(symbol, tf, df_1m_full, full_regen=args.full_regen)
                total_new += n
        except Exception as e:
            import traceback
            print(f"  -> ERROR: {e}")
            traceback.print_exc()
        print()

    elapsed = time.time() - t0
    print(f"Done. {total_new:,} new FVG rows written in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
