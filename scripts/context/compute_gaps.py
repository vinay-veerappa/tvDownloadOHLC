"""
Gap Records Computation Pipeline  (Module 3 — Phase 4)

Generates ``data/derived/gap_records.parquet`` from daily context parquet files.
One row per (symbol, trading_date).

Usage
-----
python -m scripts.context.compute_gaps
python -m scripts.context.compute_gaps --symbols NQ1,ES1 --start 2025-01-01
python -m scripts.context.compute_gaps --append

Notes
-----
- This pipeline depends on ``data/derived/daily_context_{symbol}.parquet``.
- Generate missing context files via:
    python -m scripts.edgeful.lib.generate_daily_context --symbol NQ1
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import List

import pandas as pd

_REPO_ROOT = Path(__file__).parent.parent.parent
_DERIVED_DIR = _REPO_ROOT / "data" / "derived"
_OUTPUT_PATH = _DERIVED_DIR / "gap_records.parquet"

DEFAULT_SYMBOLS = ["NQ1", "ES1", "YM1", "RTY1", "CL1", "GC1"]

logger = logging.getLogger(__name__)


def _load_context(symbol: str) -> pd.DataFrame:
    path = _DERIVED_DIR / f"daily_context_{symbol}.parquet"
    if not path.exists():
        logger.warning("daily_context missing for %s: %s", symbol, path)
        return pd.DataFrame()

    df = pd.read_parquet(path)
    if df.empty:
        return df

    df["trading_date"] = pd.to_datetime(df["trading_date"]).dt.date
    df["symbol"] = symbol
    return df


def _build_gap_records(df: pd.DataFrame) -> pd.DataFrame:
    required = [
        "symbol",
        "trading_date",
        "day_of_week",
        "session_open",
        "pdc",
        "gap_size_points",
        "gap_size_pct",
        "gap_direction",
        "gap_size_bucket",
        "gap_filled",
        "gap_fill_time_minutes",
        "open_vs_pd_range",
        "open_vs_midnight",
        "is_event_day",
        "event_type",
        "event_types",
        "is_opex_week",
        "session_direction",
        "pdh_broken",
        "pdl_broken",
        "both_pd_broken",
        "atr_14d",
        "atr_usage_pct",
        "vix_regime",
    ]

    for col in required:
        if col not in df.columns:
            df[col] = None

    out = df[required].copy()

    out["gap_abs_points"] = out["gap_size_points"].abs()
    out["gap_abs_pct"] = out["gap_size_pct"].abs()

    out["filled_within_30m"] = out["gap_filled"] & (out["gap_fill_time_minutes"].fillna(1e9) <= 30)
    out["filled_within_60m"] = out["gap_filled"] & (out["gap_fill_time_minutes"].fillna(1e9) <= 60)
    out["filled_by_noon"] = out["gap_filled"] & (out["gap_fill_time_minutes"].fillna(1e9) <= 150)

    out["same_as_session_direction"] = (
        ((out["gap_direction"] == "UP") & (out["session_direction"] == "GREEN"))
        | ((out["gap_direction"] == "DOWN") & (out["session_direction"] == "RED"))
    )

    out["gap_valid"] = out["gap_direction"].isin(["UP", "DOWN"])

    return out.sort_values(["symbol", "trading_date"]).reset_index(drop=True)


def compute_gaps(
    symbols: List[str],
    start: str | None = None,
    end: str | None = None,
) -> pd.DataFrame:
    all_frames: list[pd.DataFrame] = []

    for symbol in symbols:
        ctx = _load_context(symbol)
        if ctx.empty:
            continue

        if start:
            ctx = ctx[ctx["trading_date"] >= pd.to_datetime(start).date()]
        if end:
            ctx = ctx[ctx["trading_date"] <= pd.to_datetime(end).date()]

        if ctx.empty:
            continue

        all_frames.append(_build_gap_records(ctx))

    if not all_frames:
        return pd.DataFrame()

    out = pd.concat(all_frames, ignore_index=True)
    out = out.sort_values(["symbol", "trading_date"]).reset_index(drop=True)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate gap_records.parquet from daily_context parquet files")
    parser.add_argument("--symbols", type=str, default=",".join(DEFAULT_SYMBOLS), help="Comma-separated symbols")
    parser.add_argument("--start", type=str, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", type=str, help="End date YYYY-MM-DD")
    parser.add_argument("--append", action="store_true", help="Append to existing output")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s")

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    logger.info("=== Gap Records Pipeline ===")
    logger.info("Symbols: %s", symbols)
    logger.info("Dates  : %s -> %s", args.start or "ALL", args.end or "ALL")

    df = compute_gaps(symbols, args.start, args.end)
    if df.empty:
        logger.warning("No gap rows produced. Ensure daily_context_{symbol}.parquet exists in data/derived.")
        return 1

    _DERIVED_DIR.mkdir(parents=True, exist_ok=True)

    if args.append and _OUTPUT_PATH.exists():
        old = pd.read_parquet(_OUTPUT_PATH)
        merged = pd.concat([old, df], ignore_index=True)
        merged = merged.drop_duplicates(subset=["symbol", "trading_date"], keep="last")
        merged = merged.sort_values(["symbol", "trading_date"]).reset_index(drop=True)
        merged.to_parquet(_OUTPUT_PATH, index=False)
        logger.info("Appended %d rows; total=%d -> %s", len(df), len(merged), _OUTPUT_PATH)
    else:
        df.to_parquet(_OUTPUT_PATH, index=False)
        logger.info("Saved %d rows -> %s", len(df), _OUTPUT_PATH)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
