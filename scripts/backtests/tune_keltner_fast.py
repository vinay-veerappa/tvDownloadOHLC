"""
High-Speed Parameter Sweep and Strategy Optimizer for Keltner Channel Bot.
Caches precomputed indicator dataframes for instant grid evaluation on NQ & ES.
"""
from __future__ import annotations

import itertools
from pathlib import Path
import numpy as np
import pandas as pd

from scripts.backtests.keltner_channel_backtest import (
    INSTRUMENT_SPECS,
    StrategyConfig,
    prepare_keltner_dataset,
    run_backtest_simulation,
    calculate_metrics
)

def run_fast_parameter_sweep(symbol: str = "NQ", start_year: int = 2023):
    spec = INSTRUMENT_SPECS[symbol]
    data_path = Path(spec["parquet"])
    print(f"\n[Fast Sweep] Loading {symbol} from {data_path}...")
    df = pd.read_parquet(data_path)
    df['datetime_utc'] = pd.to_datetime(df.index, utc=True)
    df = df.reset_index(drop=True)
    df['datetime'] = df['datetime_utc'].dt.tz_convert('America/New_York')
    df['time'] = df['datetime'].dt.hour * 100 + df['datetime'].dt.minute
    df['date'] = df['datetime'].dt.date
    df = df.drop(columns=['datetime_utc']).sort_values('datetime').reset_index(drop=True)
    df = df[df['datetime'].dt.year >= start_year].reset_index(drop=True)

    grid = {
        "mode": ["TrendPullback", "AdaptiveHybrid", "WaveTrendMeanReversion"],
        "ma_length": [21, 34, 55],
        "target_r_multiple": [1.5, 2.0, 3.0],
        "stop_atr_mult": [1.0, 1.5],
        "earliest_entry_time": [945, 1000],
        "latest_entry_time": [1130, 1500],
    }

    # Pre-cache datasets by ma_length
    cached_dfs = {}
    for ma in grid["ma_length"]:
        cfg_dummy = StrategyConfig(symbol=symbol, ma_length=ma)
        cached_dfs[ma] = prepare_keltner_dataset(df, cfg_dummy)

    keys, values = zip(*grid.items())
    combinations = [dict(zip(keys, v)) for v in itertools.product(*values)]
    print(f"[Fast Sweep] Testing {len(combinations)} configurations on {symbol}...")

    results = []
    for p in combinations:
        cfg = StrategyConfig(
            symbol=symbol,
            point_value=spec["point_value"],
            tick_size=spec["tick_size"],
            slippage_pts=spec["tick_size"] * spec["slippage_ticks"],
            commission_per_contract=spec["commission"],
            max_risk_pts=spec["max_risk_pts"],
            trend_slope_thresh_pts=spec["default_slope_thresh"],
            mode=p["mode"],
            ma_length=p["ma_length"],
            target_r_multiple=p["target_r_multiple"],
            stop_atr_mult=p["stop_atr_mult"],
            earliest_entry_time=p["earliest_entry_time"],
            latest_entry_time=p["latest_entry_time"],
        )
        # Use cached dataframe
        prep_df = cached_dfs[p["ma_length"]]
        trades_df, metrics = run_backtest_simulation(prep_df, cfg)
        if metrics["Total Trades"] >= 50:
            res = {**p, **metrics}
            results.append(res)

    res_df = pd.DataFrame(results)
    if not res_df.empty:
        res_df = res_df.sort_values(by="Profit Factor", ascending=False).reset_index(drop=True)
        print("\n" + "="*115)
        print(f"TOP 10 CONFIGURATIONS FOR {symbol} ({start_year}-2026)")
        print("="*115)
        top_cols = ["mode", "ma_length", "target_r_multiple", "stop_atr_mult", "earliest_entry_time", "latest_entry_time", "Total Trades", "Win Rate (%)", "Profit Factor", "Net PnL ($)", "Max Drawdown ($)", "Sharpe Ratio"]
        print(res_df[top_cols].head(10).to_string(index=False))
        print("="*115)

        out_path = Path(f"results/keltner_backtest/{symbol.lower()}_fast_sweep_{start_year}_2026.csv")
        res_df.to_csv(out_path, index=False)
        print(f"Saved results to {out_path}")
    return res_df

if __name__ == "__main__":
    for sym in ["NQ", "ES"]:
        run_fast_parameter_sweep(sym, start_year=2023)
