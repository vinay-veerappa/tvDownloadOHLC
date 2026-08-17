"""
Range Probability Backtest CLI Runner
Executes backtests on extracted feature feeds or on-the-fly datasets across multiple tickers and configurations.
"""

import os
import sys
import argparse
import pandas as pd
import numpy as np

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.range_prob.backtest_adapter import RangeProbBacktester
from scripts.range_probability.extractor import extract_features_for_ticker
from src.range_prob.matrix_store import MatrixStore

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
    "SPY": 1.0,
    "QQQ": 1.0,
    "AAPL": 1.0,
    "NVDA": 1.0,
    "TSLA": 1.0,
}


def main():
    parser = argparse.ArgumentParser(description="Range Probability Python Backtester")
    parser.add_argument("--tickers", type=str, default="NQ,ES,YM,RTY", help="Tickers to backtest")
    parser.add_argument("--intervals", type=str, default="60,15,30,120,240", help="Range intervals in minutes")
    parser.add_argument("--min-prob", type=float, default=70.0, help="Min directional probability threshold")
    parser.add_argument("--min-resolve", type=float, default=40.0, help="Min resolve rate threshold")
    parser.add_argument("--min-sample", type=int, default=20, help="Min sample size threshold")
    parser.add_argument("--target-mode", type=str, default="prior_boundary", choices=["prior_boundary", "fixed_rr", "range_close"])
    parser.add_argument("--stop-mode", type=str, default="prior_midpoint", choices=["prior_midpoint", "prior_opposite", "fixed_pts"])
    parser.add_argument("--risk-reward", type=float, default=1.5, help="Risk:Reward ratio for fixed_rr target mode")
    parser.add_argument("--output-dir", type=str, default="results/range_prob_backtests")

    args = parser.parse_args()

    ticker_list = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    interval_list = [int(i.strip()) for i in args.intervals.split(",") if i.strip()]
    os.makedirs(args.output_dir, exist_ok=True)

    store = MatrixStore()
    results_summary = []

    print("=" * 80)
    print("RANGE PROBABILITY BACKTEST RUNNER (PYTHON)")
    print(f"Tickers: {ticker_list} | Intervals: {interval_list}")
    print(f"Strategy Edge Filter: Prob >= {args.min_prob}% | Resolve >= {args.min_resolve}% | N >= {args.min_sample}")
    print(f"Execution: Target = {args.target_mode} (RR: {args.risk_reward}) | Stop = {args.stop_mode}")
    print("=" * 80)

    for ticker in ticker_list:
        pt_val = POINT_VALUES.get(ticker, 1.0)
        for tf in interval_list:
            feed_path = os.path.join(store.feeds_dir, f"{ticker}_{tf}m_features.parquet")
            if os.path.exists(feed_path):
                feature_df = pd.read_parquet(feed_path)
            else:
                print(f"[{ticker}] Extracting {tf}m features on-the-fly...")
                feature_df = extract_features_for_ticker(
                    ticker=ticker,
                    interval_minutes=tf,
                    min_prob=args.min_prob,
                    min_sample=args.min_sample,
                    store=store,
                )

            if feature_df is None or len(feature_df) == 0:
                continue

            tester = RangeProbBacktester(
                min_prob=args.min_prob,
                min_resolve_rate=args.min_resolve,
                min_sample_size=args.min_sample,
                target_mode=args.target_mode,
                stop_mode=args.stop_mode,
                risk_reward=args.risk_reward,
                point_value=pt_val,
            )

            res = tester.run_backtest(feature_df)

            # Export trade list
            if len(res["trades"]) > 0:
                trades_path = os.path.join(args.output_dir, f"{ticker}_{tf}m_trades.csv")
                res["trades"].to_csv(trades_path, index=False)

            summary_item = {
                "Ticker": ticker,
                "Interval": f"{tf}m",
                "Total Trades": res["total_trades"],
                "Win Rate (%)": f"{res['win_rate']:.1f}%",
                "Net Profit ($)": f"${res['net_profit']:,.2f}",
                "Profit Factor": f"{res['profit_factor']:.2f}",
                "Max Drawdown ($)": f"${res['max_drawdown']:,.2f}",
                "Sharpe Ratio": f"{res['sharpe_ratio']:.2f}",
                "Avg Win ($)": f"${res['avg_win']:,.2f}",
                "Avg Loss ($)": f"${res['avg_loss']:,.2f}",
            }
            results_summary.append(summary_item)

    if results_summary:
        summary_df = pd.DataFrame(results_summary)
        print("\n" + "=" * 80)
        print("CONSOLIDATED BACKTEST RESULTS SUMMARY")
        print("=" * 80)
        print(summary_df.to_string(index=False))

        summary_csv = os.path.join(args.output_dir, "backtest_summary.csv")
        summary_df.to_csv(summary_csv, index=False)
        print(f"\nSaved consolidated summary to {summary_csv}")


if __name__ == "__main__":
    main()
