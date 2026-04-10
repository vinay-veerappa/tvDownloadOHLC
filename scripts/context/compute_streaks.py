"""
Streak Records Computation Pipeline  (Module 3 — Phase 5)

Generates ``data/derived/streak_records.parquet`` from daily context parquet files.
One row per (symbol, trading_date).
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import List

import pandas as pd

_REPO_ROOT = Path(__file__).parent.parent.parent
_DERIVED_DIR = _REPO_ROOT / "data" / "derived"
_OUTPUT_PATH = _DERIVED_DIR / "streak_records.parquet"

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
    return df.sort_values("trading_date").reset_index(drop=True)


def _build_streak_records(ctx: pd.DataFrame) -> pd.DataFrame:
    required = ["symbol", "trading_date", "session_direction", "streak_length", "streak_direction"]
    for col in required:
        if col not in ctx.columns:
            ctx[col] = None

    out = ctx[required].copy()
    out["next_day_continuation"] = out["session_direction"].eq(out["session_direction"].shift(-1))
    out["next_day_continuation"] = out["next_day_continuation"].fillna(False).astype(bool)
    return out.sort_values(["symbol", "trading_date"]).reset_index(drop=True)


def compute_streaks(symbols: List[str], start: str | None = None, end: str | None = None) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
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
        frames.append(_build_streak_records(ctx))

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True).sort_values(["symbol", "trading_date"]).reset_index(drop=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate streak_records.parquet from daily_context parquet files")
    parser.add_argument("--symbols", type=str, default=",".join(DEFAULT_SYMBOLS), help="Comma-separated symbols")
    parser.add_argument("--start", type=str, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", type=str, help="End date YYYY-MM-DD")
    parser.add_argument("--append", action="store_true", help="Append to existing output")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s")
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    logger.info("=== Streak Records Pipeline ===")
    logger.info("Symbols: %s", symbols)
    logger.info("Dates  : %s -> %s", args.start or "ALL", args.end or "ALL")

    df = compute_streaks(symbols, args.start, args.end)
    if df.empty:
        logger.warning("No streak rows produced.")
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