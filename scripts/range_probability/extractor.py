"""
Range Probability Extractor - Batch Feature Extractor for Backtesting
Generates backtest-ready feature datasets (Parquet, CSV, NinjaTrader format) enriched with
empirical probabilities, decile states, directional edges, and realized outcomes.
"""

import os
import sys
import argparse
from typing import List, Optional
import pandas as pd
import numpy as np

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from scripts.range_probability.calculator import build_ranges_from_ohlc, compute_probability_matrix, compute_expanding_probabilities, get_bucket_char
from scripts.range_probability.matrix_store import MatrixStore
from scripts.range_probability.engine import load_ticker_data


def extract_features_for_ticker(
    ticker: str,
    interval_minutes: int = 60,
    anchor_hour: int = 18,
    min_prob: float = 70.0,
    min_sample: int = 20,
    store: Optional[MatrixStore] = None,
) -> Optional[pd.DataFrame]:
    """
    Extracts bar-by-bar range features with pre-computed lookup edges and realized outcomes.
    """
    if store is None:
        store = MatrixStore()

    df = load_ticker_data(ticker)
    if df is None or len(df) == 0:
        print(f"[{ticker}] No data found for feature extraction!")
        return None

    # Detect columns
    cols = {c.lower(): c for c in df.columns}
    time_col = cols.get("time") or cols.get("datetime") or cols.get("timestamp") or "time"
    open_col = cols.get("open") or "open"
    high_col = cols.get("high") or "high"
    low_col = cols.get("low") or "low"
    close_col = cols.get("close") or "close"
    vol_col = cols.get("volume")

    # Build ranges
    ranges = build_ranges_from_ohlc(
        df=df,
        range_minutes=interval_minutes,
        anchor_hour_et=anchor_hour,
        time_col=time_col,
        open_col=open_col,
        high_col=high_col,
        low_col=low_col,
        close_col=close_col,
        volume_col=vol_col,
    )

    # Compute probability matrix (full-sample, for reference fields)
    matrix_res = compute_probability_matrix(
        ranges_df=ranges,
        min_prob_threshold=min_prob,
        min_sample_size=min_sample,
    )

    # Build lookup map: (slot, bucket) -> record (full-sample, for reference)
    lut_map = {}
    for rec in matrix_res["records"]:
        key = (rec["slot"], rec["bucket"])
        lut_map[key] = rec

    # Compute expanding-window probabilities (walk-forward, no look-ahead)
    expanding = compute_expanding_probabilities(ranges)

    # Enrich ranges with lookup stats
    rows = []
    for idx, row in ranges.iterrows():
        slot = row["slot"]
        b = row["bucket"]
        key = (slot, b)

        # Full-sample reference values
        rec = lut_map.get(key)
        if rec is not None:
            ref_direction = rec["direction"]
            p_train = rec["prob_train"]
            p_test = rec["prob_test"]
            ref_n = rec["sample_size"]
            ref_res_rate = rec["resolve_rate"]
            z_score = rec["z_score"]
        else:
            ref_direction = "NONE"
            p_train = np.nan
            p_test = np.nan
            ref_n = 0
            ref_res_rate = np.nan
            z_score = 0.0

        # Expanding-window values (zero look-ahead) -- used for s_prob, s_dir, is_qualified
        exp_row = expanding.loc[idx] if idx in expanding.index else None
        if exp_row is not None and not pd.isna(exp_row["exp_prob"]):
            direction = exp_row["exp_dir"]
            p_prob = exp_row["exp_prob"]
            n_sample = int(exp_row["exp_n"])
            res_rate = exp_row["exp_res_rate"]
            is_qual = bool(
                not pd.isna(p_prob)
                and p_prob >= min_prob
                and n_sample >= min_sample
                and direction in ["U", "D"]
            )
        else:
            direction = "NONE"
            p_prob = np.nan
            n_sample = 0
            res_rate = np.nan
            is_qual = False

        # Compute theoretical unconditional probabilities
        p_up_cond = p_prob if direction == "U" else (100.0 - p_prob) if not pd.isna(p_prob) else 50.0
        u_above = (p_up_cond * res_rate / 100.0) if not pd.isna(res_rate) else np.nan
        u_below = ((100.0 - p_up_cond) * res_rate / 100.0) if not pd.isna(res_rate) else np.nan
        u_inside = (100.0 - res_rate) if not pd.isna(res_rate) else np.nan

        # Signal edge: direction if qualified
        signal = 1 if (is_qual and direction == "U") else -1 if (is_qual and direction == "D") else 0

        # Outcome validation: did the signal win?
        trade_win = 1 if (signal == 1 and row["outcome"] == "UP") or (signal == -1 and row["outcome"] == "DOWN") else 0 if (signal != 0 and row["is_resolved"]) else np.nan

        enriched = {
            "ticker": ticker.upper(),
            "timeframe_min": interval_minutes,
            "start_time_utc": row["start_time_utc"],
            "start_time_ny": row["start_time_ny"],
            "slot": slot,
            "open": row["open"],
            "high": row["high"],
            "low": row["low"],
            "close": row["close"],
            "prior_high": row["prior_high"],
            "prior_low": row["prior_low"],
            "prior_span": row["prior_high"] - row["prior_low"] if not pd.isna(row["prior_high"]) else np.nan,
            "open_pos": row["open_pos"],
            "bucket": b,
            "bucket_char": row["bucket_char"],
            "bucket_name": row["bucket_name"],
            "is_adjacent": row["is_adjacent"],
            "s_dir": direction,
            "s_prob": p_prob,
            "s_train": p_train,
            "s_test": p_test,
            "s_n": n_sample,
            "s_res_rate": res_rate,
            "z_score": z_score,
            "is_qualified": is_qual,
            "signal": signal,
            "u_above_pct": u_above,
            "u_below_pct": u_below,
            "u_inside_pct": u_inside,
            "realized_outcome": row["outcome"],
            "is_resolved": row["is_resolved"],
            "trade_win": trade_win,
        }
        rows.append(enriched)

    feature_df = pd.DataFrame(rows)

    # Save to Parquet and CSV
    parquet_path = os.path.join(store.feeds_dir, f"{ticker.upper()}_{interval_minutes}m_features.parquet")
    csv_path = os.path.join(store.feeds_dir, f"{ticker.upper()}_{interval_minutes}m_features.csv")

    feature_df.to_parquet(parquet_path, index=False)
    feature_df.to_csv(csv_path, index=False)
    print(f"[{ticker.upper()}] {interval_minutes}m Feed Extracted: {len(feature_df):,} rows -> {parquet_path}")

    return feature_df


def main():
    parser = argparse.ArgumentParser(description="Range Probability Batch Feature Extractor")
    parser.add_argument("--tickers", type=str, default="NQ,ES,YM,RTY,CL,GC,SPY,QQQ,AAPL,NVDA,TSLA", help="Comma-separated tickers")
    parser.add_argument("--intervals", type=str, default="15,30,60,120,240", help="Comma-separated intervals")
    parser.add_argument("--anchor", type=int, default=18, help="Anchor hour in ET")
    parser.add_argument("--min-prob", type=float, default=70.0, help="Min prob edge")
    parser.add_argument("--min-sample", type=int, default=20, help="Min sample size")

    args = parser.parse_args()

    ticker_list = [t.strip() for t in args.tickers.split(",") if t.strip()]
    interval_list = [int(i.strip()) for i in args.intervals.split(",") if i.strip()]

    store = MatrixStore()
    print("=" * 70)
    print(f"EXTRACTING RANGE PROBABILITY BACKTEST FEEDS")
    print(f"Tickers: {ticker_list} | Intervals: {interval_list} | Anchor: {args.anchor}:00 ET")
    print("=" * 70)

    for ticker in ticker_list:
        for tf in interval_list:
            extract_features_for_ticker(
                ticker=ticker,
                interval_minutes=tf,
                anchor_hour=args.anchor,
                min_prob=args.min_prob,
                min_sample=args.min_sample,
                store=store,
            )


if __name__ == "__main__":
    main()
