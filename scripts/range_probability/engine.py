"""
Range Probability Engine - Multi-Ticker Batch Generator
Generates probability matrices, train/test statistical validation, and Pine Script LUT constants
for any ticker from 1m/5m/15m OHLC data.
"""

import os
import sys
import glob
import argparse
from typing import Dict, List, Optional, Any
import pandas as pd
import numpy as np

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from scripts.range_probability.calculator import build_ranges_from_ohlc, compute_probability_matrix
from scripts.range_probability.matrix_store import MatrixStore

DATA_SOURCES = {
    # Futures (1m live storage)
    "NQ": "data/live/live_storage_-NQ.parquet",
    "ES": "data/live/live_storage_-ES.parquet",
    "YM": "data/live/live_storage_-YM.parquet",
    "RTY": "data/live/live_storage_-RTY.parquet",
    "CL": "data/live/live_storage_-CL.parquet",
    "GC": "data/live/live_storage_-GC.parquet",
    # ETFs and Equities
    "SPY": "data/live/live_storage_SPY.parquet",
    "QQQ": "data/live/live_storage_QQQ.parquet",
    "AAPL": "data/live/live_storage_AAPL.parquet",
    "NVDA": "data/live/live_storage_NVDA.parquet",
    "TSLA": "data/live/live_storage_TSLA.parquet",
    "AMZN": "data/live/live_storage_AMZN.parquet",
    "MSFT": "data/live/live_storage_MSFT.parquet",
    "META": "data/live/live_storage_META.parquet",
    "GOOGL": "data/live/live_storage_GOOGL.parquet",
    "NFLX": "data/live/live_storage_NFLX.parquet",
}


def load_ticker_data(ticker: str) -> Optional[pd.DataFrame]:
    """Loads 1m or 5m OHLC data for a ticker from available parquet or CSV files."""
    ticker_clean = ticker.upper().replace("/", "").replace("!", "").replace("-", "")

    # Check known paths
    if ticker_clean in DATA_SOURCES and os.path.exists(DATA_SOURCES[ticker_clean]):
        path = DATA_SOURCES[ticker_clean]
        print(f"[{ticker_clean}] Loading from {path}...")
        df = pd.read_parquet(path)
        return df

    # Search in data/live/
    live_matches = glob.glob(f"data/live/*{ticker_clean}*.parquet")
    if live_matches:
        print(f"[{ticker_clean}] Found live storage file: {live_matches[0]}")
        return pd.read_parquet(live_matches[0])

    # Search in data/TV_OHLC/
    tv_csv_matches = glob.glob(f"data/TV_OHLC/**/*{ticker_clean}*.csv", recursive=True)
    if tv_csv_matches:
        print(f"[{ticker_clean}] Found TV CSV file: {tv_csv_matches[0]}")
        return pd.read_csv(tv_csv_matches[0])

    print(f"[{ticker_clean}] No local data file found!")
    return None


def process_ticker(
    ticker: str,
    intervals: List[int] = [15, 30, 60, 120, 240],
    anchor_hour: int = 18,
    min_prob: float = 70.0,
    min_sample: int = 20,
    store: Optional[MatrixStore] = None,
) -> Dict[str, Any]:
    """Processes all intervals for a given ticker and returns comprehensive matrix data."""
    if store is None:
        store = MatrixStore()

    df = load_ticker_data(ticker)
    if df is None or len(df) == 0:
        return {"ticker": ticker, "status": "ERROR_NO_DATA"}

    print(f"[{ticker}] Processing {len(df):,} bars across intervals: {intervals} (Anchor: {anchor_hour:02d}:00 ET)...")

    # Detect time and ohlc columns
    cols = {c.lower(): c for c in df.columns}
    time_col = cols.get("time") or cols.get("datetime") or cols.get("timestamp") or "time"
    open_col = cols.get("open") or "open"
    high_col = cols.get("high") or "high"
    low_col = cols.get("low") or "low"
    close_col = cols.get("close") or "close"
    vol_col = cols.get("volume")

    ticker_results = {
        "ticker": ticker.upper(),
        "anchor_hour_et": anchor_hour,
        "min_prob_threshold": min_prob,
        "min_sample_size": min_sample,
        "intervals": {},
    }

    summaries = []

    for tf in intervals:
        ranges = build_ranges_from_ohlc(
            df=df,
            range_minutes=tf,
            anchor_hour_et=anchor_hour,
            time_col=time_col,
            open_col=open_col,
            high_col=high_col,
            low_col=low_col,
            close_col=close_col,
            volume_col=vol_col,
        )

        matrix = compute_probability_matrix(
            ranges_df=ranges,
            min_prob_threshold=min_prob,
            min_sample_size=min_sample,
        )

        ticker_results["intervals"][tf] = matrix

        summary_row = {
            "ticker": ticker.upper(),
            "interval_min": tf,
            "total_ranges": matrix["total_ranges"],
            "valid_ranges": matrix["valid_ranges"],
            "qualified_cells": matrix["qualified_count"],
            "lut_length": len(matrix["pine_lut_string"]),
        }
        summaries.append(summary_row)
        print(f"  -> {tf}m: {matrix['valid_ranges']} valid ranges, {matrix['qualified_count']} qualified >= {min_prob}% edge cells")

    # Save JSON matrix
    matrix_file = store.save_matrix(ticker, ticker_results)
    print(f"[{ticker}] Saved matrix JSON to {matrix_file}")

    # Generate Pine Script LUT string block
    pine_file = store.export_pine_script_luts(ticker, ticker_results["intervals"])
    print(f"[{ticker}] Saved Pine LUT code to {pine_file}")

    return {
        "ticker": ticker.upper(),
        "status": "SUCCESS",
        "matrix_file": matrix_file,
        "pine_file": pine_file,
        "summaries": summaries,
    }


def main():
    parser = argparse.ArgumentParser(description="Range Probability Matrix Engine")
    parser.add_argument("--tickers", type=str, default="NQ,ES,YM,RTY,CL,GC,SPY,QQQ,AAPL,NVDA,TSLA", help="Comma-separated ticker list")
    parser.add_argument("--intervals", type=str, default="15,30,60,120,240", help="Comma-separated range minutes")
    parser.add_argument("--anchor", type=int, default=18, help="Anchor hour in ET (default: 18 for futures/crypto, 9 for equities)")
    parser.add_argument("--min-prob", type=float, default=70.0, help="Min probability threshold for Pine LUT filter")
    parser.add_argument("--min-sample", type=int, default=20, help="Min sample size for Pine LUT filter")

    args = parser.parse_args()

    ticker_list = [t.strip() for t in args.tickers.split(",") if t.strip()]
    interval_list = [int(i.strip()) for i in args.intervals.split(",") if i.strip()]

    store = MatrixStore()
    all_summaries = []

    print("=" * 70)
    print(f"Starting Range Probability Engine for {len(ticker_list)} tickers...")
    print(f"Intervals: {interval_list} | Anchor: {args.anchor}:00 ET | Min Prob: {args.min_prob}%")
    print("=" * 70)

    for ticker in ticker_list:
        res = process_ticker(
            ticker=ticker,
            intervals=interval_list,
            anchor_hour=args.anchor,
            min_prob=args.min_prob,
            min_sample=args.min_sample,
            store=store,
        )
        if res.get("status") == "SUCCESS":
            all_summaries.extend(res["summaries"])

    # Export consolidated summary CSV
    if all_summaries:
        summary_path = store.export_summary_report(all_summaries)
        print("\n" + "=" * 70)
        print(f"CONSOLIDATED REPORT GENERATED: {summary_path}")
        print("=" * 70)
        df_summary = pd.DataFrame(all_summaries)
        print(df_summary.to_string(index=False))


if __name__ == "__main__":
    main()
