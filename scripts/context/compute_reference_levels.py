"""
Reference Level Records Computation Pipeline  (Module 3 — Phase 5)

Generates ``data/derived/reference_levels.parquet`` from daily context parquet files
and intraday 1m bars. One row per (symbol, trading_date).
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path
import sys
from typing import List

import pandas as pd

_REPO_ROOT = Path(__file__).parent.parent.parent
_DERIVED_DIR = _REPO_ROOT / "data" / "derived"
_OUTPUT_PATH = _DERIVED_DIR / "reference_levels.parquet"

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.edgeful.lib.data_loader import DataLoader
from scripts.edgeful.lib.session_tagger import tag_session

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


def _first_touch_minutes(rth: pd.DataFrame, levels: pd.DataFrame, level_col: str) -> pd.Series:
    merged = rth.reset_index().merge(
        levels[["trading_date", level_col]],
        on="trading_date",
        how="left",
    )
    cond = (
        merged[level_col].notna()
        & (merged[level_col] != 0)
        & (merged["low"] <= merged[level_col])
        & (merged["high"] >= merged[level_col])
    )
    hits = merged.loc[cond, ["trading_date", "minutes_into_session"]]
    if hits.empty:
        return pd.Series(dtype="float64")
    return hits.groupby("trading_date")["minutes_into_session"].min().astype(float)


def _build_reference_levels(ctx: pd.DataFrame, rth: pd.DataFrame) -> pd.DataFrame:
    rth_daily = pd.DataFrame(columns=["trading_date", "session_high", "session_low"])
    if not rth.empty:
        rth_daily = (
            rth.groupby("trading_date", sort=True)
            .agg(
                session_high=("high", "max"),
                session_low=("low", "min"),
            )
            .reset_index()
        )

    required = [
        "symbol",
        "trading_date",
        "midnight_open",
        "open_vs_midnight",
        "pdh",
        "pdl",
        "pdh_broken",
        "pdl_broken",
        "pdh_break_time_minutes",
        "pdl_break_time_minutes",
        "session_direction",
        "is_inside_day",
        "is_outside_day",
        "open_vs_pd_range",
        "weekly_open",
        "prior_week_high",
        "prior_week_low",
    ]
    for col in required:
        if col not in ctx.columns:
            ctx[col] = None

    out = ctx[required].copy().merge(rth_daily, on="trading_date", how="left")
    out["mop_retrace"] = (
        out["midnight_open"].notna()
        & (out["midnight_open"] != 0)
        & (out["session_low"] <= out["midnight_open"])
        & (out["session_high"] >= out["midnight_open"])
    )
    out["mop_retrace_from"] = out["open_vs_midnight"].fillna("ABOVE")

    mop_time = _first_touch_minutes(rth, out[["trading_date", "midnight_open"]], "midnight_open")
    out["mop_retrace_time_minutes"] = out["trading_date"].map(mop_time)

    out["pdh_break_continuation"] = out["pdh_broken"] & out["session_direction"].eq("GREEN")
    out["pdl_break_continuation"] = out["pdl_broken"] & out["session_direction"].eq("RED")
    out["outside_day_reversal"] = (
        (out["open_vs_pd_range"].eq("ABOVE_PDH") & out["pdh"].notna() & (out["session_low"] <= out["pdh"]))
        | (out["open_vs_pd_range"].eq("BELOW_PDL") & out["pdl"].notna() & (out["session_high"] >= out["pdl"]))
    )
    out["weekly_open_retrace"] = (
        out["weekly_open"].notna()
        & (out["weekly_open"] != 0)
        & (out["session_low"] <= out["weekly_open"])
        & (out["session_high"] >= out["weekly_open"])
    )
    out["prior_week_high_broken"] = out["prior_week_high"].notna() & (out["session_high"] > out["prior_week_high"])
    out["prior_week_low_broken"] = out["prior_week_low"].notna() & (out["session_low"] < out["prior_week_low"])

    out = out.rename(
        columns={
            "pdh_break_time_minutes": "pdh_break_time",
            "pdl_break_time_minutes": "pdl_break_time",
        }
    )

    keep = [
        "symbol",
        "trading_date",
        "mop_retrace",
        "mop_retrace_time_minutes",
        "mop_retrace_from",
        "pdh_broken",
        "pdl_broken",
        "pdh_break_continuation",
        "pdl_break_continuation",
        "pdh_break_time",
        "pdl_break_time",
        "is_inside_day",
        "is_outside_day",
        "outside_day_reversal",
        "weekly_open_retrace",
        "prior_week_high_broken",
        "prior_week_low_broken",
    ]
    out = out[keep].copy()

    bool_cols = [
        "mop_retrace",
        "pdh_broken",
        "pdl_broken",
        "pdh_break_continuation",
        "pdl_break_continuation",
        "is_inside_day",
        "is_outside_day",
        "outside_day_reversal",
        "weekly_open_retrace",
        "prior_week_high_broken",
        "prior_week_low_broken",
    ]
    for col in bool_cols:
        out[col] = out[col].fillna(False).astype(bool)

    return out.sort_values(["symbol", "trading_date"]).reset_index(drop=True)


def compute_reference_levels(symbols: List[str], start: str | None = None, end: str | None = None) -> pd.DataFrame:
    loader = DataLoader()
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
            logger.warning("1m bars missing for %s; reference timing fields may be incomplete", symbol)
            rth = pd.DataFrame(columns=["trading_date", "minutes_into_session", "high", "low"])
        else:
            tagged = tag_session(bars)
            rth = tagged[tagged["is_rth"]].copy()
            rth = rth[rth["trading_date"].isin(ctx["trading_date"])]

        frames.append(_build_reference_levels(ctx, rth))

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True).sort_values(["symbol", "trading_date"]).reset_index(drop=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate reference_levels.parquet from daily_context parquet files")
    parser.add_argument("--symbols", type=str, default=",".join(DEFAULT_SYMBOLS), help="Comma-separated symbols")
    parser.add_argument("--start", type=str, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", type=str, help="End date YYYY-MM-DD")
    parser.add_argument("--append", action="store_true", help="Append to existing output")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s")

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    logger.info("=== Reference Levels Pipeline ===")
    logger.info("Symbols: %s", symbols)
    logger.info("Dates  : %s -> %s", args.start or "ALL", args.end or "ALL")

    df = compute_reference_levels(symbols, args.start, args.end)
    if df.empty:
        logger.warning("No reference level rows produced.")
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