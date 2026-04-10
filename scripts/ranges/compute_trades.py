"""Compute strategy trades from range records (Phase 4)."""
from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path
from typing import Optional

import pandas as pd

import sys

_REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from scripts.edgeful.lib.data_loader import DataLoader
from scripts.edgeful.lib.session_tagger import tag_session
from scripts.edgeful.lib.trade_simulator import (
    STRATEGY_PRESETS,
    no_entry_record,
    simulate_strategy,
    to_record,
)
from scripts.ranges.range_definitions import RANGE_PRESETS

logger = logging.getLogger(__name__)

_DATA_DIR = _REPO_ROOT / "data"
_DERIVED_DIR = _DATA_DIR / "derived"
_RANGE_PATH = _DERIVED_DIR / "range_records.parquet"
_OUTPUT_PATH = _DERIVED_DIR / "range_trades.parquet"


def _parse_hhmm_local(value: str) -> int:
    h, m = value.split(":")
    return int(h) * 60 + int(m)


def _get_post_bars_for_trade(day_bars: pd.DataFrame, range_name: str) -> tuple[pd.DataFrame, Optional[pd.Timestamp]]:
    rdef = RANGE_PRESETS.get(range_name)
    if rdef is None:
        return pd.DataFrame(), None

    end_min = _parse_hhmm_local(rdef.end_time)
    bmin = day_bars.index.hour * 60 + day_bars.index.minute

    stop_min = _parse_hhmm_local(rdef.observe_until) if rdef.observe_until else 16 * 60
    post = day_bars[(bmin >= end_min) & (bmin < stop_min)].copy()

    end_idx = day_bars[bmin == end_min].index
    end_ts = end_idx[0] if len(end_idx) else (post.index[0] if not post.empty else None)

    return post, end_ts


def _load_symbol_bars(symbol: str, start: Optional[str], end: Optional[str]) -> pd.DataFrame:
    loader = DataLoader()
    bars = loader.load_1m(symbol, start, end)
    if bars is None or bars.empty:
        return pd.DataFrame()
    return tag_session(bars)


def compute_trades(
    symbols: list[str],
    ranges: list[str],
    strategies: list[str],
    start: Optional[str],
    end: Optional[str],
) -> pd.DataFrame:
    if not _RANGE_PATH.exists():
        raise FileNotFoundError(f"Missing range records: {_RANGE_PATH}")

    rr = pd.read_parquet(_RANGE_PATH)
    rr["trading_date"] = pd.to_datetime(rr["trading_date"]).dt.strftime("%Y-%m-%d")

    if symbols:
        rr = rr[rr["symbol"].isin(symbols)]
    if ranges:
        rr = rr[rr["range_name"].isin(ranges)]
    if start:
        rr = rr[rr["trading_date"] >= start]
    if end:
        rr = rr[rr["trading_date"] <= end]

    if rr.empty:
        return pd.DataFrame()

    all_rows: list[dict] = []

    for symbol in sorted(rr["symbol"].unique()):
        sym_rr = rr[rr["symbol"] == symbol].copy()
        bars = _load_symbol_bars(symbol, start, end)
        if bars.empty:
            logger.warning("No bars for %s", symbol)
            continue

        day_groups = {str(td): grp for td, grp in bars.groupby("trading_date")}
        logger.info("[%s] processing %d range rows", symbol, len(sym_rr))

        for _, row in sym_rr.iterrows():
            date_key = str(row["trading_date"])
            day_bars = day_groups.get(date_key)
            if day_bars is None or day_bars.empty:
                continue

            post_bars, range_end_ts = _get_post_bars_for_trade(day_bars, str(row["range_name"]))
            if range_end_ts is None:
                continue

            row_dict = row.to_dict()

            for sname in strategies:
                sdef = STRATEGY_PRESETS.get(sname)
                if sdef is None:
                    continue

                trade = simulate_strategy(post_bars, row_dict, sdef, range_end_ts)
                if trade is None:
                    out = no_entry_record(row_dict, sdef)
                else:
                    out = to_record(trade)

                all_rows.append(out)

    if not all_rows:
        return pd.DataFrame()

    return pd.DataFrame(all_rows)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="Compute range strategy trades")
    parser.add_argument("--symbols", type=str, default="NQ1,ES1,YM1,RTY1,CL1,GC1")
    parser.add_argument("--ranges", type=str, default="OR_5,OR_15,OR_30,IB_60")
    parser.add_argument("--strategies", type=str, default="MR_TO_MID,BO_1X,BO_PULLBACK_1X")
    parser.add_argument("--start", type=str)
    parser.add_argument("--end", type=str)
    parser.add_argument("--append", action="store_true")
    args = parser.parse_args()

    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    ranges = [r.strip() for r in args.ranges.split(",") if r.strip()]
    strategies = [s.strip() for s in args.strategies.split(",") if s.strip()]

    print("=== Range Trades Pipeline ===")
    print(f"Symbols   : {symbols}")
    print(f"Ranges    : {ranges}")
    print(f"Strategies: {strategies}")
    print(f"Dates     : {args.start or 'Full History'} -> {args.end or 'Present'}")

    t0 = time.time()
    out = compute_trades(symbols, ranges, strategies, args.start, args.end)

    if out.empty:
        print("No trades generated.")
        return

    if args.append and _OUTPUT_PATH.exists():
        existing = pd.read_parquet(_OUTPUT_PATH)
        out = pd.concat([existing, out], ignore_index=True)
        out.drop_duplicates(
            subset=["symbol", "range_name", "strategy_name", "trading_date"],
            keep="last",
            inplace=True,
        )

    _DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    out.to_parquet(_OUTPUT_PATH, index=False)

    print(f"Saved {len(out)} rows to {_OUTPUT_PATH}")
    print(f"Done in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
