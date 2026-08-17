"""
Unified Confluence & Multi-Timeframe Strategy Optimizer
Comprehensive Python benchmarking suite comparing:
1. Base Range Probability (Unfiltered vs Golden Hours Filtered)
2. Base + Candle Science (Sequential State Vectors & Drift Agreement: 55%, 60%, 65%)
3. Quarters Theory 15m Sub-Cycles (Q1 Accumulation, Q2 Sweep, Q3 Expansion, Q4 Resolution)
4. Multi-Timeframe Confluence (60m Directional Anchor + 15m Quarter Execution)
"""

import os
import sys
import argparse
from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np
from tabulate import tabulate

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

from src.range_prob.confluence_engine import ConfluenceFeatureEngine
from src.range_prob.confluence_backtester import ConfluenceBacktester
from scripts.range_probability.engine import DATA_SOURCES

POINT_VALUES = {
    "NQ": 20.0,
    "MNQ": 2.0,
    "ES": 50.0,
    "MES": 5.0,
    "YM": 5.0,
    "MYM": 0.5,
    "RTY": 50.0,
    "M2K": 5.0,
    "CL": 1000.0,
    "MCL": 100.0,
    "GC": 100.0,
    "MGC": 10.0,
}

GOLDEN_HOURS = {
    "NQ": [1, 3, 4, 6, 7, 10, 11, 12, 13, 14, 16, 18, 19, 20, 21, 22, 23],
    "ES": [11, 12, 19],
    "YM": [1, 2, 3, 4, 5, 7, 12, 13, 14, 16, 20, 21, 22, 23],
    "GC": [2, 6, 10, 14, 15, 23],
    "RTY": [11, 12],
    "CL": [4, 5, 10],
}


def load_raw_data(ticker: str) -> Optional[pd.DataFrame]:
    ticker_clean = ticker.upper().replace("/", "").replace("!", "").replace("-", "")
    if ticker_clean in DATA_SOURCES and os.path.exists(DATA_SOURCES[ticker_clean]):
        return pd.read_parquet(DATA_SOURCES[ticker_clean])
    return None


def run_confluence_optimization(ticker: str = "NQ") -> pd.DataFrame:
    print(f"\n==========================================================================================")
    print(f"UNIFIED CONFLUENCE STRATEGY OPTIMIZER: [{ticker}]")
    print(f"Point Value: ${POINT_VALUES.get(ticker, 20.0)}/pt | Golden Hours: {GOLDEN_HOURS.get(ticker, [])}")
    print(f"==========================================================================================")

    raw_df = load_raw_data(ticker)
    if raw_df is None:
        print(f"[ERROR] Could not load raw data for {ticker}")
        return pd.DataFrame()

    engine = ConfluenceFeatureEngine()
    pt_val = POINT_VALUES.get(ticker, 20.0)
    golden_hrs = GOLDEN_HOURS.get(ticker, None)

    # 1. Build 60m and 15m Datasets
    print(f"Building 60m and 15m confluence feature sets...")
    df_60m = engine.build_confluence_dataset(raw_df, ticker=ticker, range_minutes=60)
    df_15m = engine.build_confluence_dataset(raw_df, ticker=ticker, range_minutes=15)

    results = []

    # Model Suite to Evaluate
    models = [
        # --- 60-Minute Hourly Framework ---
        ("60m", "1. Base Range Prob (Unfiltered)", df_60m, 70.0, 10, "range_open", "none", 50.0, None, "range_close", "prior_opposite"),
        ("60m", "2. Base Range Prob (Golden Hours Filtered)", df_60m, 70.0, 10, "range_open", "none", 50.0, golden_hrs, "range_close", "prior_opposite"),
        ("60m", "3. Base + Candle Science (Dir >= 60%)", df_60m, 70.0, 10, "range_open", "directional_agreement", 60.0, None, "range_close", "prior_opposite"),
        ("60m", "4. Base + Candle Science (Dir >= 65%)", df_60m, 70.0, 10, "range_open", "directional_agreement", 65.0, None, "range_close", "prior_opposite"),
        ("60m", "5. Base + CS + Golden Hours (Optimal Confluence)", df_60m, 70.0, 10, "range_open", "directional_agreement", 60.0, golden_hrs, "range_close", "prior_opposite"),
        ("60m", "6. Quarters Theory (Q2 Valid H/L Sweep)", df_60m, 70.0, 10, "q2_sweep_entry", "none", 50.0, golden_hrs, "range_close", "prior_opposite"),

        # --- 15-Minute Quarters Framework ---
        ("15m", "7. 15m Quarters Base (Unfiltered)", df_15m, 70.0, 10, "range_open", "none", 50.0, None, "range_close", "prior_opposite"),
        ("15m", "8. 15m Quarters (Golden Hours Filtered)", df_15m, 70.0, 10, "range_open", "none", 50.0, golden_hrs, "range_close", "prior_opposite"),
        ("15m", "9. 15m Quarters + Candle Science (Dir >= 60%)", df_15m, 70.0, 10, "range_open", "directional_agreement", 60.0, golden_hrs, "range_close", "prior_opposite"),
        ("15m", "10. 15m Quarters + Candle Science (Dir >= 65%)", df_15m, 70.0, 10, "range_open", "directional_agreement", 65.0, golden_hrs, "range_close", "prior_opposite"),
    ]

    for tf_label, m_name, feat_df, m_prob, m_n, e_timing, cs_mode, cs_thr, h_filter, tgt_m, stp_m in models:
        bt = ConfluenceBacktester(
            min_prob=m_prob,
            min_sample_size=m_n,
            entry_timing=e_timing,
            cs_filter_mode=cs_mode,
            cs_threshold=cs_thr,
            target_mode=tgt_m,
            stop_mode=stp_m,
            point_value=pt_val,
            allowed_hours=h_filter,
        )
        r = bt.run_backtest(feat_df)
        results.append({
            "Ticker": ticker,
            "TF": tf_label,
            "Strategy Model": m_name,
            "Trades": r["total_trades"],
            "WinRate%": r["win_rate"],
            "ProfitFactor": r["profit_factor"],
            "NetProfit$": r["net_pnl"],
            "AvgTrade$": r["avg_trade"],
            "MaxDD$": r["max_drawdown"],
            "Sharpe": r["sharpe_ratio"],
        })

    res_df = pd.DataFrame(results)

    print("\n" + tabulate(
        res_df[["TF", "Strategy Model", "Trades", "WinRate%", "ProfitFactor", "NetProfit$", "AvgTrade$", "MaxDD$", "Sharpe"]],
        headers="keys",
        tablefmt="github",
        showindex=False,
    ))

    # Save to reports
    out_dir = "data/range_prob/reports"
    os.makedirs(out_dir, exist_ok=True)
    out_csv = os.path.join(out_dir, f"{ticker}_confluence_optimization.csv")
    res_df.to_csv(out_csv, index=False)
    print(f"\n[REPORT SAVED] {out_csv}")

    return res_df


def main():
    parser = argparse.ArgumentParser(description="Unified Confluence & Timeframe Optimizer")
    parser.add_argument("--tickers", type=str, default="NQ,ES,YM,GC,RTY,CL", help="Comma-separated tickers")
    args = parser.parse_args()

    tickers = [t.strip().upper() for t in args.tickers.split(",")]

    all_dfs = []
    for ticker in tickers:
        df = run_confluence_optimization(ticker=ticker)
        if not df.empty:
            all_dfs.append(df)

    if all_dfs:
        combined = pd.concat(all_dfs, ignore_index=True)
        combined.to_csv("data/range_prob/reports/consolidated_confluence_matrix.csv", index=False)
        print(f"\n==========================================================================================")
        print("CONSOLIDATED CONFLUENCE OPTIMIZATION MATRIX COMPLETE!")
        print("Report File: data/range_prob/reports/consolidated_confluence_matrix.csv")
        print(f"==========================================================================================")


if __name__ == "__main__":
    main()
