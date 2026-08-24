"""Comprehensive Strat Strategy Backtest Runner.

Executes and benchmarks:
  1. Pure 2-1-2 Continuation Strategy
  2. 2-1-2 Continuation + FTFC Trend Alignment Filter
  3. 2-2 Momentum Reversal / RevStrat Strategy
  4. 3-1-2 Broadening Expansion Breakout Strategy
  5. Multi-Setup Strat Portfolio

Outputs trade-by-trade logs, win rates, profit factors, drawdown, and R-multiples.
"""

from __future__ import annotations

import sys
from pathlib import Path
from datetime import time
import pandas as pd
import numpy as np

# Add project root to sys.path
_project_root = Path(__file__).resolve().parent
while _project_root.name and _project_root.name != "scripts":
    _project_root = _project_root.parent
if _project_root.name == "scripts":
    _project_root = _project_root.parent

if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from scripts.libs_py.the_strat.taxonomy import classify_bars_df
from scripts.libs_py.the_strat.combos import ComboType, StratComboDetector, TradeDirection
from scripts.libs_py.the_strat.strategy import StratBacktester


def run_strat_backtest_suite(
    ticker: str = "NQ1",
    timeframe: str = "5min",
    start_date: str = "2024-01-01",
    end_date: str = "2025-12-31",
    point_value: float = 20.0,
    commission_per_contract: float = 2.05,
    slippage_ticks: int = 1,
):
    print("=" * 80)
    print(f"THE STRAT STRATEGY BENCHMARK SUITE - {ticker} ({timeframe})")
    print(f"Period: {start_date} to {end_date} | Point Value: ${point_value} | Slip: {slippage_ticks} tick | Comm: ${commission_per_contract}/contract")
    print("=" * 80)

    # 1. Load Data
    data_file = _project_root / "data" / f"{ticker}_1m.parquet"
    if not data_file.exists():
        data_file = _project_root / "data" / f"{ticker.replace('1', '')}_1m.parquet"
    if not data_file.exists():
        raise FileNotFoundError(f"Data file not found for {ticker}")

    print(f"\n[1/4] Loading and normalizing 1-minute data from {data_file.name}...")
    df_1m = pd.read_parquet(data_file)
    if df_1m.index.tz is None:
        df_1m.index = df_1m.index.tz_localize("UTC").tz_convert("America/New_York")
    else:
        df_1m.index = df_1m.index.tz_convert("America/New_York")

    df_1m = df_1m.sort_index()
    df_filtered = df_1m[(df_1m.index >= start_date) & (df_1m.index <= end_date)]

    print(f"[2/4] Resampling to {timeframe} timeframe...")
    df_tf = df_filtered[["open", "high", "low", "close"]].resample(timeframe, origin="start_day").agg({
        "open": "first", "high": "max", "low": "min", "close": "last"
    }).dropna()

    print(f"Dataset contains {len(df_tf):,} bars from {df_tf.index[0].strftime('%Y-%m-%d')} to {df_tf.index[-1].strftime('%Y-%m-%d')}.")

    # 2. Initialize Backtester
    backtester = StratBacktester(
        point_value=point_value,
        commission_per_contract=commission_per_contract,
        slippage_ticks=slippage_ticks,
        tick_size=0.25,
    )

    # 3. Define Strategy Configurations to Compare
    configs = [
        {
            "name": "1. Pure 2-1-2 Continuation (Any R:R)",
            "allowed": {ComboType.BULLISH_212_CONT, ComboType.BEARISH_212_CONT},
            "min_rr": 0.0,
            "max_hold": 15,
        },
        {
            "name": "2. High-Conviction 2-1-2 Continuation (R:R >= 1.0)",
            "allowed": {ComboType.BULLISH_212_CONT, ComboType.BEARISH_212_CONT},
            "min_rr": 1.0,
            "max_hold": 15,
        },
        {
            "name": "3. 2-2 Momentum Reversals (RevStrat Traps)",
            "allowed": {ComboType.BULLISH_22_REV, ComboType.BEARISH_22_REV},
            "min_rr": 0.5,
            "max_hold": 15,
        },
        {
            "name": "4. 3-1-2 Broadening Expansion Breakouts",
            "allowed": {ComboType.BULLISH_312, ComboType.BEARISH_312},
            "min_rr": 0.8,
            "max_hold": 20,
        },
        {
            "name": "5. All Strat Core Setups (Portfolio)",
            "allowed": {
                ComboType.BULLISH_212_CONT,
                ComboType.BEARISH_212_CONT,
                ComboType.BULLISH_22_REV,
                ComboType.BEARISH_22_REV,
                ComboType.BULLISH_312,
                ComboType.BEARISH_312,
            },
            "min_rr": 0.8,
            "max_hold": 15,
        },
    ]

    print("\n[3/4] Running Simulations across configurations...\n")
    results = []

    for cfg in configs:
        summary = backtester.run_backtest(
            df_tf,
            allowed_combos=cfg["allowed"],
            min_rr_ratio=cfg["min_rr"],
            max_holding_bars=cfg["max_hold"],
            start_time_et=time(9, 30),
            end_time_et=time(15, 30),
        )
        results.append((cfg["name"], summary))

    # 4. Print Comparison Table
    print("-" * 110)
    print(f"{'Strategy Variant':<45} | {'Trades':<7} | {'Win Rate':<9} | {'PF':<6} | {'Net PnL ($)':<14} | {'Max DD ($)':<12} | {'Avg Trade':<10}")
    print("-" * 110)

    for name, s in results:
        wr_str = f"{s.win_rate * 100:.1f}%"
        pf_str = f"{s.profit_factor:.2f}" if s.profit_factor < 100 else "N/A"
        pnl_str = f"${s.net_pnl_dollars:+,.2f}"
        dd_str = f"${s.max_drawdown_dollars:,.2f}"
        avg_str = f"{s.avg_trade_points:+.2f} pts"
        print(f"{name:<45} | {s.total_trades:<7} | {wr_str:<9} | {pf_str:<6} | {pnl_str:<14} | {dd_str:<12} | {avg_str:<10}")

    print("-" * 110)

    # Detailed inspection of the top strategy
    best_name, best_summary = max(results, key=lambda x: x[1].net_pnl_dollars)
    print(f"\n[4/4] Top Performing Strategy: {best_name}")
    print(f"Total Trades: {best_summary.total_trades} (Wins: {best_summary.winning_trades}, Losses: {best_summary.losing_trades})")
    print(f"Win Rate: {best_summary.win_rate * 100:.2f}% | Profit Factor: {best_summary.profit_factor:.2f}")
    print(f"Net Points: {best_summary.net_pnl_points:+,.2f} pts (${best_summary.net_pnl_dollars:+,.2f})")
    print(f"Avg Win: {best_summary.avg_win_points:+.2f} pts | Avg Loss: {best_summary.avg_loss_points:+.2f} pts | Win/Loss Ratio: {abs(best_summary.avg_win_points / best_summary.avg_loss_points):.2f}" if best_summary.avg_loss_points != 0 else "")

    if best_summary.trades:
        print("\nSample 5 Recent Trades:")
        for t in best_summary.trades[-5:]:
            print(f"  {t.entry_time.strftime('%Y-%m-%d %H:%M')}: {t.direction.value} {t.combo_type.value} @ {t.entry_price:.2f} -> Exit @ {t.exit_price:.2f} ({t.exit_reason}) | PnL: {t.pnl_points:+.2f} pts (${t.pnl_dollars:+.2f})")


if __name__ == "__main__":
    run_strat_backtest_suite()
