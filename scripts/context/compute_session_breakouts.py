"""
Session Breakout Records Computation Pipeline  (Module 3 — Phase 6)

Generates ``data/derived/session_breakout_records.parquet`` by combining
intraday session structure (London to NY) with daily context fields.
One row per (symbol, trading_date).
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
_OUTPUT_PATH = _DERIVED_DIR / "session_breakout_records.parquet"

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
    df = df.sort_values("trading_date")
    # Keep the latest row per trading day to prevent ambiguous lookups downstream.
    df = df.drop_duplicates(subset=["trading_date"], keep="last")
    return df.reset_index(drop=True)


def _get_first_break(ny_bars: pd.DataFrame, london_high: float, london_low: float) -> tuple[str, float | None]:
    if ny_bars.empty or pd.isna(london_high) or pd.isna(london_low):
        return "NONE", None

    hits = ny_bars[(ny_bars["high"] >= london_high) | (ny_bars["low"] <= london_low)]
    if hits.empty:
        return "NONE", None

    first = hits.iloc[0]
    up_hit = bool(first["high"] >= london_high)
    down_hit = bool(first["low"] <= london_low)
    if up_hit and not down_hit:
        direction = "UP"
    elif down_hit and not up_hit:
        direction = "DOWN"
    else:
        # If both boundaries were touched in one bar, use close location as tie-break.
        direction = "UP" if first["close"] >= first["open"] else "DOWN"

    return direction, float(first["minutes_into_session"])


def _close_location(close_value: float, london_high: float, london_low: float) -> str:
    if pd.isna(close_value) or pd.isna(london_high) or pd.isna(london_low):
        return "UNKNOWN"
    if close_value > london_high:
        return "ABOVE"
    if close_value < london_low:
        return "BELOW"
    return "INSIDE"


def _build_symbol_records(symbol: str, ctx: pd.DataFrame, tagged: pd.DataFrame) -> pd.DataFrame:
    if tagged.empty or ctx.empty:
        return pd.DataFrame()

    keep_cols = [
        "symbol",
        "trading_date",
        "day_of_week",
        "is_event_day",
        "event_type",
        "event_types",
        "is_opex_week",
        "session_direction",
        "vix_regime",
    ]
    for col in keep_cols:
        if col not in ctx.columns:
            ctx[col] = None
    base_ctx = (
        ctx[keep_cols]
        .copy()
        .sort_values("trading_date")
        .drop_duplicates(subset=["trading_date"], keep="last")
        .set_index("trading_date")
    )

    rows: list[dict] = []
    for td, day in tagged.groupby("trading_date"):
        if td not in base_ctx.index:
            continue

        london = day[day["session"] == "LONDON"]
        ny = day[day["session"].isin(["NY_AM", "NY_LUNCH", "NY_PM"])]
        ny_open_slice = day[(day["session"] == "NY_AM") & (day["minutes_into_session"] >= 0)]
        if london.empty or ny.empty or ny_open_slice.empty:
            continue

        london_high = float(london["high"].max())
        london_low = float(london["low"].min())
        ny_high = float(ny["high"].max())
        ny_low = float(ny["low"].min())
        ny_open = float(ny_open_slice.iloc[0]["open"])
        ny_close = float(ny.iloc[-1]["close"])

        first_dir, first_min = _get_first_break(ny, london_high, london_low)
        broke_up = bool(ny_high >= london_high)
        broke_down = bool(ny_low <= london_low)
        both_sides = broke_up and broke_down

        continuation = (
            (first_dir == "UP" and ny_close > london_high)
            or (first_dir == "DOWN" and ny_close < london_low)
        )
        reversal = (
            (first_dir == "UP" and ny_close < london_low)
            or (first_dir == "DOWN" and ny_close > london_high)
        )

        ctx_row = base_ctx.loc[td]
        rows.append(
            {
                "symbol": symbol,
                "trading_date": td,
                "day_of_week": ctx_row["day_of_week"],
                "is_event_day": bool(ctx_row["is_event_day"]) if pd.notna(ctx_row["is_event_day"]) else False,
                "event_type": ctx_row["event_type"],
                "event_types": ctx_row["event_types"],
                "is_opex_week": bool(ctx_row["is_opex_week"]) if pd.notna(ctx_row["is_opex_week"]) else False,
                "session_direction": ctx_row["session_direction"],
                "vix_regime": ctx_row["vix_regime"],
                "london_high": london_high,
                "london_low": london_low,
                "london_range": london_high - london_low,
                "ny_open": ny_open,
                "ny_close": ny_close,
                "opened_inside_london": bool((ny_open >= london_low) and (ny_open <= london_high)),
                "first_break_direction": first_dir,
                "first_break_time_minutes": first_min,
                "london_high_broken_in_ny": broke_up,
                "london_low_broken_in_ny": broke_down,
                "both_sides_broken_in_ny": both_sides,
                "london_held_in_ny": not (broke_up or broke_down),
                "continuation_after_first_break": bool(continuation),
                "reversal_after_first_break": bool(reversal),
                "ny_close_location_vs_london": _close_location(ny_close, london_high, london_low),
            }
        )

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(["symbol", "trading_date"]).reset_index(drop=True)


def compute_session_breakouts(symbols: List[str], start: str | None = None, end: str | None = None) -> pd.DataFrame:
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
        if bars is None or bars.empty:
            logger.warning("1m bars missing for %s", symbol)
            continue

        tagged = tag_session(bars)
        tagged = tagged[tagged["trading_date"].isin(ctx["trading_date"])].copy()
        sym_records = _build_symbol_records(symbol, ctx, tagged)
        if not sym_records.empty:
            frames.append(sym_records)

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True).sort_values(["symbol", "trading_date"]).reset_index(drop=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate session_breakout_records.parquet from intraday session structure")
    parser.add_argument("--symbols", type=str, default=",".join(DEFAULT_SYMBOLS), help="Comma-separated symbols")
    parser.add_argument("--start", type=str, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", type=str, help="End date YYYY-MM-DD")
    parser.add_argument("--append", action="store_true", help="Append to existing output")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s")

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    logger.info("=== Session Breakout Records Pipeline ===")
    logger.info("Symbols: %s", symbols)
    logger.info("Dates  : %s -> %s", args.start or "ALL", args.end or "ALL")

    df = compute_session_breakouts(symbols, args.start, args.end)
    if df.empty:
        logger.warning("No session breakout rows produced.")
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
