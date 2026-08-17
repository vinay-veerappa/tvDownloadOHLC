"""
Range Probability Hourly Strategy Evaluator
Evaluates trade performance broken down by each individual hour of the day (ET)
to discover the most profitable session windows and construct filtered time-of-day portfolios.
"""

import os
import sys
import argparse
from typing import Dict, List, Any, Optional
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
    "NVDA": 1.0,
    "TSLA": 1.0,
}


def evaluate_hourly_breakdown(
    df_features: pd.DataFrame,
    ticker: str,
    interval_min: int = 60,
    min_prob: float = 70.0,
    min_resolve: float = 40.0,
    min_sample: int = 20,
    target_mode: str = "range_close",
    stop_mode: str = "prior_opposite",
    point_value: float = 20.0,
    slippage_pts: float = 0.5,
    commission: float = 2.0,
) -> Dict[str, Any]:
    """
    Simulates the strategy across all bars and groups performance metrics by each hour (slot) of the day.
    """
    tester = RangeProbBacktester(
        min_prob=min_prob,
        min_resolve_rate=min_resolve,
        min_sample_size=min_sample,
        target_mode=target_mode,
        stop_mode=stop_mode,
        point_value=point_value,
        slippage_pts=slippage_pts,
        commission_per_contract=commission,
    )

    full_results = tester.run_backtest(df_features)
    trades_df = full_results["trades"]

    if len(trades_df) == 0:
        return {"summary": {}, "hourly_table": pd.DataFrame(), "trades": trades_df}

    # Group trades by slot (e.g. '0900', '1000', '1400', '1800')
    hourly_rows = []
    unique_slots = sorted(trades_df["slot"].unique())

    for slot in unique_slots:
        sub = trades_df[trades_df["slot"] == slot]
        n_trades = len(sub)
        wins = len(sub[sub["is_win"] == 1])
        losses = len(sub[sub["is_win"] == 0])
        win_rate = (wins / n_trades * 100.0) if n_trades > 0 else 0.0

        gross_profit = sub[sub["net_pnl"] > 0]["net_pnl"].sum()
        gross_loss = abs(sub[sub["net_pnl"] < 0]["net_pnl"].sum())
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)

        net_profit = sub["net_pnl"].sum()
        avg_trade = sub["net_pnl"].mean() if n_trades > 0 else 0.0
        avg_win = sub[sub["net_pnl"] > 0]["net_pnl"].mean() if wins > 0 else 0.0
        avg_loss = sub[sub["net_pnl"] < 0]["net_pnl"].mean() if losses > 0 else 0.0

        # Drawdown calculation for this slot
        equity = sub["net_pnl"].cumsum()
        peak = equity.cummax()
        dd = (peak - equity).max() if len(equity) > 0 else 0.0

        # Sharpe ratio (annualized approximation)
        returns = sub["net_pnl"]
        sharpe = (returns.mean() / returns.std() * np.sqrt(252)) if (len(returns) > 1 and returns.std() > 0) else 0.0

        # Session Label
        hour_int = int(slot[:2])
        session = (
            "Asia" if (hour_int >= 18 or hour_int < 3) else
            "London" if (3 <= hour_int < 9) else
            "NY Open" if (hour_int in [9, 10]) else
            "NY Midday" if (11 <= hour_int < 14) else
            "NY Afternoon"
        )

        hourly_rows.append({
            "Slot": slot,
            "Hour_ET": f"{slot[:2]}:{slot[2:]}",
            "Session": session,
            "Trades": n_trades,
            "WinRate%": round(win_rate, 1),
            "NetProfit$": round(net_profit, 2),
            "ProfitFactor": round(profit_factor, 2),
            "AvgTrade$": round(avg_trade, 2),
            "AvgWin$": round(avg_win, 2),
            "AvgLoss$": round(avg_loss, 2),
            "MaxDD$": round(dd, 2),
            "Sharpe": round(sharpe, 2),
            "IsProfitable": net_profit > 0,
        })

    hourly_df = pd.DataFrame(hourly_rows)
    return {
        "overall": full_results,
        "hourly_table": hourly_df,
        "trades": trades_df,
    }


def main():
    parser = argparse.ArgumentParser(description="Range Probability Hourly Strategy Evaluator")
    parser.add_argument("--tickers", type=str, default="NQ,ES,YM", help="Comma-separated tickers")
    parser.add_argument("--interval", type=int, default=60, help="Range interval in minutes (default: 60)")
    parser.add_argument("--min-prob", type=float, default=75.0, help="Min directional edge prob threshold (default: 75.0 pct)")
    parser.add_argument("--min-resolve", type=float, default=45.0, help="Min range resolve rate threshold (default: 45.0 pct)")
    parser.add_argument("--min-sample", type=int, default=25, help="Min sample size (default: 25)")
    parser.add_argument("--target-mode", type=str, default="range_close", choices=["prior_boundary", "range_close", "fixed_rr"])
    parser.add_argument("--stop-mode", type=str, default="prior_opposite", choices=["prior_midpoint", "prior_opposite", "fixed_pts"])
    parser.add_argument("--out-dir", type=str, default="results/range_prob_strategies")

    args = parser.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    store = MatrixStore()

    ticker_list = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]

    print("=" * 90)
    print("RANGE PROBABILITY HOURLY STRATEGY EVALUATOR")
    print(f"Tickers: {ticker_list} | Interval: {args.interval}m")
    print(f"Edge Filter: Prob >= {args.min_prob}% | Resolve Rate >= {args.min_resolve}% | N >= {args.min_sample}")
    print(f"Execution: Target = {args.target_mode} | Stop = {args.stop_mode}")
    print("=" * 90)

    for ticker in ticker_list:
        pt_val = POINT_VALUES.get(ticker, 1.0)
        feed_path = os.path.join(store.feeds_dir, f"{ticker}_{args.interval}m_features.parquet")

        if os.path.exists(feed_path):
            df_features = pd.read_parquet(feed_path)
        else:
            print(f"[{ticker}] Extracting {args.interval}m feature feed...")
            df_features = extract_features_for_ticker(
                ticker=ticker,
                interval_minutes=args.interval,
                min_prob=args.min_prob,
                min_sample=args.min_sample,
                store=store,
            )

        if df_features is None or len(df_features) == 0:
            print(f"[{ticker}] No feature data available!")
            continue

        res = evaluate_hourly_breakdown(
            df_features=df_features,
            ticker=ticker,
            interval_min=args.interval,
            min_prob=args.min_prob,
            min_resolve=args.min_resolve,
            min_sample=args.min_sample,
            target_mode=args.target_mode,
            stop_mode=args.stop_mode,
            point_value=pt_val,
        )

        hourly_df = res["hourly_table"]
        if len(hourly_df) == 0:
            print(f"[{ticker}] No qualifying trades generated.")
            continue

        print(f"\n[{ticker} - {args.interval}m HOURLY PERFORMANCE BREAKDOWN]")
        print("-" * 90)
        print(hourly_df[[
            "Hour_ET", "Session", "Trades", "WinRate%", "ProfitFactor", "NetProfit$", "AvgTrade$", "Sharpe"
        ]].to_string(index=False))

        # Save hourly breakdown
        csv_path = os.path.join(args.out_dir, f"{ticker}_{args.interval}m_hourly_breakdown.csv")
        hourly_df.to_csv(csv_path, index=False)

        # Compute "All Hours" vs "Profitable Hours Only" comparison
        profitable_slots = hourly_df[hourly_df["IsProfitable"]]["Slot"].tolist()
        trades_all = res["trades"]
        trades_filtered = trades_all[trades_all["slot"].isin(profitable_slots)]

        all_pnl = trades_all["net_pnl"].sum()
        all_pf = (trades_all[trades_all["net_pnl"] > 0]["net_pnl"].sum() / abs(trades_all[trades_all["net_pnl"] < 0]["net_pnl"].sum())) if len(trades_all[trades_all["net_pnl"] < 0]) > 0 else 0.0
        all_wr = len(trades_all[trades_all["is_win"] == 1]) / len(trades_all) * 100.0

        filt_pnl = trades_filtered["net_pnl"].sum()
        filt_pf = (trades_filtered[trades_filtered["net_pnl"] > 0]["net_pnl"].sum() / abs(trades_filtered[trades_filtered["net_pnl"] < 0]["net_pnl"].sum())) if len(trades_filtered[trades_filtered["net_pnl"] < 0]) > 0 else 0.0
        filt_wr = len(trades_filtered[trades_filtered["is_win"] == 1]) / len(trades_filtered) * 100.0 if len(trades_filtered) > 0 else 0.0

        print("\n" + "=" * 65)
        print(f"[{ticker}] ALL HOURS vs. TIME-OF-DAY FILTERED PORTFOLIO")
        print("=" * 65)
        print(f"  • ALL HOURS ({len(hourly_df)} slots):")
        print(f"      Trades: {len(trades_all):,} | Win Rate: {all_wr:.1f}% | Net PnL: ${all_pnl:,.2f} | PF: {all_pf:.2f}")
        print(f"  • FILTERED GOLDEN HOURS ({len(profitable_slots)} slots: {profitable_slots}):")
        print(f"      Trades: {len(trades_filtered):,} | Win Rate: {filt_wr:.1f}% | Net PnL: ${filt_pnl:,.2f} | PF: {filt_pf:.2f}")
        print(f"      PnL Improvement: +${(filt_pnl - all_pnl):,.2f} (+{((filt_pnl/all_pnl - 1)*100 if all_pnl > 0 else 0):.1f}%)")
        print("=" * 65)


if __name__ == "__main__":
    main()
