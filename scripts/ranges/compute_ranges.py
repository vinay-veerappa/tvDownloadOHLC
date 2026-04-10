"""
Range Records Computation Pipeline  (Module 2 — Phase 3)

Generates ``data/derived/range_records.parquet`` — one row per
(symbol, range_name, trading_date).

Usage
-----
python -m scripts.ranges.compute_ranges
python -m scripts.ranges.compute_ranges --symbols NQ1,ES1 --ranges OR_5,IB_60
python -m scripts.ranges.compute_ranges --start 2020-01-01 --append

Schema
------
See RangeRecord dataclass below (mirrors spec section 5.3).
All time assumptions: America/New_York naive datetimes (ADR-001).
"""
from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path
from typing import List, Optional

import numpy as np
import pandas as pd

# ── project paths ──────────────────────────────────────────────────────────
_REPO_ROOT   = Path(__file__).parent.parent.parent
_DATA_DIR    = _REPO_ROOT / "data"
_DERIVED_DIR = _DATA_DIR / "derived"
_OUTPUT_PATH = _DERIVED_DIR / "range_records.parquet"

import sys
sys.path.insert(0, str(_REPO_ROOT))

from scripts.edgeful.lib.data_loader   import DataLoader
from scripts.edgeful.lib.session_tagger import tag_session
from scripts.edgeful.lib.range_core    import (
    compute_range_hl,
    compute_extensions,
    compute_mr_metrics,
    _parse_hhmm,
)
from scripts.ranges.range_definitions  import RangeDefinition, RANGE_PRESETS

logger = logging.getLogger(__name__)

# ── instruments ────────────────────────────────────────────────────────────
DEFAULT_SYMBOLS = ["ES1", "NQ1", "YM1", "RTY1", "CL1", "GC1"]

# ── default ranges for initial run ────────────────────────────────────────
DEFAULT_RANGES = ["OR_5", "OR_15", "OR_30", "IB_60", "IB_90"]

# ── RTH observe end (when no observe_until set) ────────────────────────────
_RTH_CLOSE_MIN = 16 * 60    # 960 minutes since midnight


# ══════════════════════════════════════════════════════════════════════════════
# Core computation helpers
# ══════════════════════════════════════════════════════════════════════════════

def _parse_observe_until(rdef: RangeDefinition) -> Optional[int]:
    """Return observe_until in minutes-since-midnight, or None for EOD."""
    return _parse_hhmm(rdef.observe_until) if rdef.observe_until else None


def _get_post_bars(
    day_bars: pd.DataFrame,
    range_end_min: int,
    observe_until_min: Optional[int],
) -> pd.DataFrame:
    """Return bars after range end, up to observe_until (or RTH close)."""
    bmin = day_bars.index.hour * 60 + day_bars.index.minute
    stop = observe_until_min if observe_until_min is not None else _RTH_CLOSE_MIN
    return day_bars[(bmin >= range_end_min) & (bmin < stop)]


def _range_width_percentiles(
    df: pd.DataFrame,
    width_col: str = "range_width",
    windows: tuple[int, int] = (20, 50),
) -> pd.DataFrame:
    """
    Add causal rolling-percentile and category columns to a per-day DataFrame
    sorted by trading_date.

    Adds: range_width_pctile_20d, range_width_pctile_50d, range_width_category
    """
    df = df.sort_values("trading_date").copy()

    for w in windows:
        col = f"range_width_pctile_{w}d"
        # pandas rolling rank
        df[col] = (
            df[width_col]
            .rolling(w, min_periods=5)
            .apply(lambda x: float(np.searchsorted(np.sort(x[:-1]), x[-1]) / max(len(x) - 1, 1)), raw=True)
        )

    # Category from 20d percentile
    p = df["range_width_pctile_20d"]
    df["range_width_category"] = np.select(
        [p < 0.25, p > 0.75],
        ["NARROW", "WIDE"],
        default="NORMAL",
    )

    return df


# ══════════════════════════════════════════════════════════════════════════════
# Per-day record builder
# ══════════════════════════════════════════════════════════════════════════════

def _build_range_record(
    symbol: str,
    rdef: RangeDefinition,
    trading_date: str,
    rng_row: pd.Series,
    day_bars: pd.DataFrame,
) -> dict:
    """
    Build one RangeRecord dict for a single (symbol, range, date).

    Parameters
    ----------
    rng_row   : Series from compute_range_hl output (range_high, etc.)
    day_bars  : Full day's 1m bars (ET naive DatetimeIndex, trading_date tagged)
    """
    rh  = float(rng_row["range_high"])
    rl  = float(rng_row["range_low"])
    rm  = float(rng_row["range_mid"])
    rw  = float(rng_row["range_width"])
    rw_pct = float(rng_row["range_width_pct"]) if not np.isnan(rng_row["range_width_pct"]) else None
    ro  = float(rng_row["range_open"])
    rc  = float(rng_row["range_close"])
    bc  = int(rng_row["bar_count"])

    range_end_min     = _parse_hhmm(rdef.end_time)
    observe_until_min = _parse_observe_until(rdef)

    post_bars = _get_post_bars(day_bars, range_end_min, observe_until_min)

    # ── directional bias ──────────────────────────────────────────────────────
    close_vs_mid     = "ABOVE" if rc > rm else "BELOW"
    close_pct        = float((rc - rl) / rw) if rw > 0 else 0.5

    # ── extensions ───────────────────────────────────────────────────────────
    range_end_ts  = day_bars[day_bars.index.hour * 60 + day_bars.index.minute == range_end_min].index
    t0            = range_end_ts[0] if len(range_end_ts) else None
    ext           = compute_extensions(post_bars, rh, rl, rdef.extension_levels, t0)

    # ── MR metrics ───────────────────────────────────────────────────────────
    mr            = compute_mr_metrics(post_bars, rh, rl, rm)

    # ── excursions ────────────────────────────────────────────────────────────
    max_up = float(post_bars["high"].max() - rh) if not post_bars.empty else 0.0
    max_dn = float(rl - post_bars["low"].min()) if not post_bars.empty else 0.0
    max_up_pct = float(max_up / rw * 100) if rw > 0 else None
    max_dn_pct = float(max_dn / rw * 100) if rw > 0 else None

    rec: dict = {
        "symbol"         : symbol,
        "range_name"     : rdef.name,
        "trading_date"   : trading_date,
        # intrinsic denormalized key for standalone interpretability
        "day_of_week"    : pd.Timestamp(trading_date).weekday(),
        # levels
        "range_high"     : rh,
        "range_low"      : rl,
        "range_mid"      : rm,
        "range_width"    : rw,
        "range_width_pct": rw_pct,
        "range_open"     : ro,
        "range_close"    : rc,
        "bar_count"      : bc,
        # directional
        "close_vs_mid"          : close_vs_mid,
        "close_pct_of_range"    : close_pct,
        "first_bo_direction"    : mr["first_bo_direction"],
        "first_boundary_broken" : "HIGH" if mr["broke_high_first"] else ("LOW" if mr["broke_low_first"] else "NONE"),
        # excursions
        "max_excursion_up"       : max_up,
        "max_excursion_dn"       : max_dn,
        "max_excursion_up_pct"   : max_up_pct,
        "max_excursion_dn_pct"   : max_dn_pct,
        "close_vs_range"         : mr["close_vs_range"],
        "final_direction"        : mr["final_direction"],
        # MR
        "broke_high_first"                  : mr["broke_high_first"],
        "broke_low_first"                   : mr["broke_low_first"],
        "first_bo_held"                     : mr["first_bo_held"],
        "first_bo_retested_boundary"        : mr["first_bo_retested_boundary"],
        "first_bo_failed"                   : mr["first_bo_failed"],
        "retest_mid_after_high_break"       : mr["retest_mid_after_high_break"],
        "retest_mid_after_high_break_time_min": mr["retest_mid_after_high_break_time_min"],
        "retest_mid_after_low_break"        : mr["retest_mid_after_low_break"],
        "retest_mid_after_low_break_time_min": mr["retest_mid_after_low_break_time_min"],
        "retest_opposite_after_high_break"  : mr["retest_opposite_after_high_break"],
        "retest_opposite_after_low_break"   : mr["retest_opposite_after_low_break"],
    }

    # ── extension columns ─────────────────────────────────────────────────────
    rec.update(ext)

    return rec


# ══════════════════════════════════════════════════════════════════════════════
# Per-instrument pipeline
# ══════════════════════════════════════════════════════════════════════════════

def compute_ranges_for_symbol(
    symbol: str,
    rdefs: List[RangeDefinition],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> pd.DataFrame:
    """
    Compute all RangeRecords for one symbol across all specified ranges.

    Returns DataFrame with one row per (symbol, range_name, trading_date).
    """
    loader = DataLoader()
    bars   = loader.load_1m(symbol, start_date, end_date)

    if bars is None or bars.empty:
        logger.warning("compute_ranges: no 1m data for %s", symbol)
        return pd.DataFrame()

    # Tag trading_date, session, is_rth, day_of_week
    bars = tag_session(bars)

    # Pre-group bars by trading_date for per-day lookups
    date_groups = {str(td): grp for td, grp in bars.groupby("trading_date")}

    all_records: list[dict] = []

    for rdef in rdefs:
        logger.info("  [%s] %s computing %d trading dates", symbol, rdef.name, len(date_groups))

        # ── batch vectorized range computation ────────────────────────────────
        rng_df = compute_range_hl(bars, rdef.start_time, rdef.end_time)
        if rng_df.empty:
            logger.warning("  [%s] %s: no range bars found", symbol, rdef.name)
            continue

        # ── rolling percentiles (causal) ──────────────────────────────────────
        rng_df = rng_df.reset_index(names=["trading_date"])
        rng_df = _range_width_percentiles(rng_df)

        # ── per-day derived metrics (requires bar walk) ───────────────────────
        date_end_min      = _parse_hhmm(rdef.end_time)
        observe_until_min = _parse_observe_until(rdef)

        for _, rrow in rng_df.iterrows():
            td       = str(rrow["trading_date"])
            day_bars = date_groups.get(td)
            if day_bars is None or day_bars.empty:
                continue

            # Skip incomplete ranges (< 80% of expected bar count)
            if rdef.require_complete:
                start_m    = _parse_hhmm(rdef.start_time)
                if start_m < date_end_min:
                    expected = date_end_min - start_m
                else:
                    expected = (1440 - start_m) + date_end_min
                if int(rrow["bar_count"]) < expected * 0.80:
                    continue

            rec = _build_range_record(symbol, rdef, td, rrow, day_bars)

            # Attach percentile fields
            rec["range_width_pctile_20d"] = rrow.get("range_width_pctile_20d")
            rec["range_width_pctile_50d"] = rrow.get("range_width_pctile_50d")
            rec["range_width_category"]   = rrow.get("range_width_category", "NORMAL")

            all_records.append(rec)

    if not all_records:
        return pd.DataFrame()

    return pd.DataFrame(all_records)


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(
        description="Compute range records (OR, IB, session ranges) for all symbols."
    )
    parser.add_argument("--symbols", type=str, help="Comma-separated symbols (e.g. NQ1,ES1)")
    parser.add_argument("--ranges",  type=str, help="Comma-separated range names (e.g. OR_5,IB_60)")
    parser.add_argument("--start",   type=str, help="Start date YYYY-MM-DD")
    parser.add_argument("--end",     type=str, help="End date YYYY-MM-DD")
    parser.add_argument("--append",  action="store_true",
                        help="Append to existing range_records.parquet instead of overwrite")
    args = parser.parse_args()

    symbols = args.symbols.split(",") if args.symbols else DEFAULT_SYMBOLS
    range_names = args.ranges.split(",") if args.ranges else DEFAULT_RANGES
    rdefs = [RANGE_PRESETS[r] for r in range_names if r in RANGE_PRESETS]

    unknown = [r for r in range_names if r not in RANGE_PRESETS]
    if unknown:
        logger.warning("Unknown range names (skipped): %s", unknown)

    if not rdefs:
        print("No valid ranges specified.")
        return

    print(f"=== Range Records Pipeline ===")
    print(f"Symbols : {symbols}")
    print(f"Ranges  : {[r.name for r in rdefs]}")
    print(f"Dates   : {args.start or 'Full History'} -> {args.end or 'Present'}")

    _DERIVED_DIR.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    all_results: list[pd.DataFrame] = []

    for sym in symbols:
        print(f"\nProcessing {sym}...")
        df = compute_ranges_for_symbol(sym, rdefs, args.start, args.end)
        if not df.empty:
            print(f"  -> {len(df)} records")
            all_results.append(df)
        else:
            print(f"  -> no records")

    if not all_results:
        print("\nNo records generated.")
        return

    final = pd.concat(all_results, ignore_index=True)

    if args.append and _OUTPUT_PATH.exists():
        existing = pd.read_parquet(_OUTPUT_PATH)
        final = pd.concat([existing, final], ignore_index=True)
        final.drop_duplicates(
            subset=["symbol", "range_name", "trading_date"], keep="last", inplace=True)

    print(f"\nSaving {len(final)} records to {_OUTPUT_PATH}...")
    final.to_parquet(_OUTPUT_PATH, index=False)
    print(f"Done in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
