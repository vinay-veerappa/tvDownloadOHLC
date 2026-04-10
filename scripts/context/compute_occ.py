"""
Opening Candle Continuation Records Pipeline  (Module 3 — Phase 5)

Generates ``data/derived/occ_records.parquet`` from daily context parquet files
and intraday 1m bars. One row per (symbol, trading_date, candle_duration_minutes).
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path
import sys
from typing import List

import numpy as np
import pandas as pd

_REPO_ROOT = Path(__file__).parent.parent.parent
_DERIVED_DIR = _REPO_ROOT / "data" / "derived"
_OUTPUT_PATH = _DERIVED_DIR / "occ_records.parquet"

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.edgeful.lib.data_loader import DataLoader
from scripts.edgeful.lib.session_tagger import tag_session

DEFAULT_SYMBOLS = ["NQ1", "ES1", "YM1", "RTY1", "CL1", "GC1"]
DEFAULT_DURATIONS = [15, 30, 60]

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


def _build_occ_for_duration(rth: pd.DataFrame, ctx: pd.DataFrame, duration: int) -> pd.DataFrame:
    first = rth[(rth["minutes_into_session"] >= 0) & (rth["minutes_into_session"] < duration)].copy()
    if first.empty:
        return pd.DataFrame()

    first_candle = first.groupby("trading_date", sort=True).agg(
        first_open=("open", "first"),
        first_close=("close", "last"),
        first_high=("high", "max"),
        first_low=("low", "min"),
    )
    first_candle["first_candle_direction"] = np.where(
        first_candle["first_close"] >= first_candle["first_open"],
        "GREEN",
        "RED",
    )
    first_candle["first_candle_range"] = first_candle["first_high"] - first_candle["first_low"]
    first_candle["first_candle_body_pct"] = np.where(
        first_candle["first_candle_range"] > 0,
        ((first_candle["first_close"] - first_candle["first_open"]).abs() / first_candle["first_candle_range"]) * 100.0,
        0.0,
    )

    post = rth[rth["minutes_into_session"] >= duration].copy()
    post_stats = post.groupby("trading_date", sort=True).agg(
        post_high=("high", "max"),
        post_low=("low", "min"),
    ) if not post.empty else pd.DataFrame(columns=["post_high", "post_low"])

    merged = (
        ctx[["symbol", "trading_date", "session_direction"]]
        .merge(first_candle.reset_index(), on="trading_date", how="inner")
        .merge(post_stats.reset_index(), on="trading_date", how="left")
    )
    merged["candle_duration_minutes"] = duration
    merged["continuation"] = merged["first_candle_direction"] == merged["session_direction"]
    merged["max_against"] = np.where(
        merged["first_candle_direction"] == "GREEN",
        (merged["first_close"] - merged["post_low"].fillna(merged["first_close"])).clip(lower=0.0),
        (merged["post_high"].fillna(merged["first_close"]) - merged["first_close"]).clip(lower=0.0),
    )

    out = merged[
        [
            "symbol",
            "trading_date",
            "candle_duration_minutes",
            "first_candle_direction",
            "first_candle_range",
            "first_candle_body_pct",
            "session_direction",
            "continuation",
            "max_against",
        ]
    ].copy()
    out["continuation"] = out["continuation"].fillna(False).astype(bool)
    return out


def compute_occ(symbols: List[str], start: str | None = None, end: str | None = None, durations: List[int] | None = None) -> pd.DataFrame:
    loader = DataLoader()
    durations = durations or DEFAULT_DURATIONS
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

        bars = loader.load_1m(symbol)
        if bars.empty:
            logger.warning("1m bars missing for %s", symbol)
            continue
        tagged = tag_session(bars)
        rth = tagged[tagged["is_rth"]].copy()
        rth = rth[rth["trading_date"].isin(ctx["trading_date"])]
        if rth.empty:
            continue

        for duration in durations:
            out = _build_occ_for_duration(rth, ctx, duration)
            if not out.empty:
                frames.append(out)

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True).sort_values(["symbol", "trading_date", "candle_duration_minutes"]).reset_index(drop=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate occ_records.parquet from daily_context parquet files")
    parser.add_argument("--symbols", type=str, default=",".join(DEFAULT_SYMBOLS), help="Comma-separated symbols")
    parser.add_argument("--start", type=str, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", type=str, help="End date YYYY-MM-DD")
    parser.add_argument("--durations", type=str, default="15,30,60", help="Comma-separated candle durations")
    parser.add_argument("--append", action="store_true", help="Append to existing output")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s")

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    durations = [int(part.strip()) for part in args.durations.split(",") if part.strip()]
    logger.info("=== OCC Records Pipeline ===")
    logger.info("Symbols: %s", symbols)
    logger.info("Durations: %s", durations)
    logger.info("Dates  : %s -> %s", args.start or "ALL", args.end or "ALL")

    df = compute_occ(symbols, args.start, args.end, durations)
    if df.empty:
        logger.warning("No OCC rows produced.")
        return 1

    _DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    key_cols = ["symbol", "trading_date", "candle_duration_minutes"]
    if args.append and _OUTPUT_PATH.exists():
        old = pd.read_parquet(_OUTPUT_PATH)
        merged = pd.concat([old, df], ignore_index=True)
        merged = merged.drop_duplicates(subset=key_cols, keep="last")
        merged = merged.sort_values(key_cols).reset_index(drop=True)
        merged.to_parquet(_OUTPUT_PATH, index=False)
        logger.info("Appended %d rows; total=%d -> %s", len(df), len(merged), _OUTPUT_PATH)
    else:
        df.to_parquet(_OUTPUT_PATH, index=False)
        logger.info("Saved %d rows -> %s", len(df), _OUTPUT_PATH)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())