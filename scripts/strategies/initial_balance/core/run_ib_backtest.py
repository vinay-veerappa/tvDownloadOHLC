"""
Run IB Break Strategy Backtest with Vectorized Alignment
Runs the Initial Balance strategy across multiple configurations and timeframes.
"""

import sys
import os
from pathlib import Path
import pandas as pd
import numpy as np

# Add project root to path
project_root = str(Path(__file__).parent.parent.parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)
core_dir = str(Path(__file__).parent)
if core_dir not in sys.path:
    sys.path.insert(0, core_dir)

from scripts.trading_framework.core.backtest_engine import VectorizedBacktester
from initial_balance_break import IBBreakStrategy

def run_multi_timeframe_backtest(
    ticker: str = 'NQ1',
    start_date: str = '2024-01-01',
    end_date: str = '2025-12-21',
    ib_durations: list = [15, 30, 45, 60],
    entry_variant: str = 'play1',                   # 'play1', 'play2', 'play3'
    breakout_confirmation_type: str = 'touch'       # 'touch', '1m_close', '5m_close'
):
    """
    Run Initial Balance backtests across multiple durations.
    """
    # 1. Load Data
    data_path = Path(f"data/{ticker}_1m.parquet")
    if not data_path.exists():
        # Fallback to 5m if 1m is not found
        data_path = Path(f"data/{ticker}_5m.parquet")
        if not data_path.exists():
            raise FileNotFoundError(f"Historical data for {ticker} not found.")
            
    print(f"[INFO] Loading data from {data_path}...")
    df = pd.read_parquet(data_path)
    df = df.sort_index()
    
    # Standardize timezones to US/Eastern
    if df.index.tz is None:
        df.index = df.index.tz_localize('UTC').tz_convert('America/New_York')
    else:
        df.index = df.index.tz_convert('America/New_York')
        
    df_test = df[(df.index >= start_date) & (df.index <= end_date)].copy()
    print(f"[INFO] Test range: {start_date} to {end_date} ({len(df_test)} bars).")
    
    results = {}
    all_trades = []
    engine = VectorizedBacktester(slippage_pct=0.0001)
    
    for ib_duration in ib_durations:
        print(f"\n{'#'*80}")
        print(f"# Testing IB Duration: {ib_duration} minutes | Play: {entry_variant} | Confirm: {breakout_confirmation_type}")
        print(f"{'#'*80}\n")
        
        # Instantiate strategy
        strategy = IBBreakStrategy(
            ticker=ticker,
            ib_duration_minutes=ib_duration,
            entry_variant=entry_variant,
            breakout_confirmation_type=breakout_confirmation_type,
            take_profit_r_multiple=2.0
        )
        
        # Generate signals
        signals = strategy.hunt(df_test)
        
        # Execute backtester
        metrics = engine.run(signals, df_test, {'ticker': ticker})
        
        # Post-process metrics
        trades_detailed = metrics.get('trades_detailed', pd.DataFrame())
        if not trades_detailed.empty:
            extra_cols = [c for c in signals.columns if c not in trades_detailed.columns]
            trades_detailed = trades_detailed.join(signals[extra_cols])
        pnl = trades_detailed['pnl_pct'].values if not trades_detailed.empty else np.array([])
        
        wins = pnl[pnl > 0]
        losses = pnl[pnl < 0]
        profit_factor = wins.sum() / abs(losses.sum()) if len(losses) > 0 else (np.inf if len(wins) > 0 else 1.0)
        
        summary = {
            'trades': metrics['num_trades'],
            'win_rate': metrics['win_rate_%'],
            'profit_factor': profit_factor,
            'total_return_pct': metrics['total_return_%'],
            'max_drawdown_pct': metrics['max_drawdown_%'],
            'avg_mae_pct': metrics['avg_mae_%']
        }
        results[ib_duration] = summary
        
        # Save detailed trades to disk
        output_dir = Path('scripts/strategies/initial_balance/data')
        output_dir.mkdir(parents=True, exist_ok=True)
        
        csv_path = output_dir / f'backtest_results_{ib_duration}min.csv'
        trades_detailed.to_csv(csv_path, index=True)
        print(f"[SUCCESS] Detailed trades exported to: {csv_path}")
        
        if not trades_detailed.empty:
            trades_detailed['ib_duration'] = ib_duration
            all_trades.append(trades_detailed)
            
    # Combine all trades
    if len(all_trades) > 0:
        combined_trades = pd.concat(all_trades, ignore_index=False)
        combined_path = output_dir / 'backtest_results_all.csv'
        combined_trades.to_csv(combined_path, index=True)
        print(f"\n[SUCCESS] Combined results saved to: {combined_path}")
        
    # Print comparison
    print(f"\n{'='*80}")
    print(f"MULTI-TIMEFRAME COMPARISON")
    print(f"{'='*80}\n")
    
    comparison_df = pd.DataFrame(results).T
    comparison_df.index.name = 'IB_Duration_Min'
    print(comparison_df.to_string())
    
    comparison_path = output_dir / 'timeframe_comparison.csv'
    comparison_df.to_csv(comparison_path)
    print(f"\n[SUCCESS] Comparison summary saved to: {comparison_path}")
    
    # Identify best timeframe
    if len(comparison_df) > 0 and comparison_df['trades'].sum() > 0:
        best_pf = comparison_df['profit_factor'].idxmax()
        best_wr = comparison_df['win_rate'].idxmax()
        best_return = comparison_df['total_return_pct'].idxmax()
        
        print(f"\n{'='*80}")
        print(f"BEST PERFORMERS")
        print(f"{'='*80}")
        print(f"  Best Profit Factor: {best_pf} min (PF: {comparison_df.loc[best_pf, 'profit_factor']:.2f})")
        print(f"  Best Win Rate: {best_wr} min (WR: {comparison_df.loc[best_wr, 'win_rate']:.2f}%)")
        print(f"  Best Return: {best_return} min (Return: {comparison_df.loc[best_return, 'total_return_pct']:.2f}%)")
        
    return results

if __name__ == '__main__':
    # Default execution run
    run_multi_timeframe_backtest(
        ticker='NQ1',
        start_date='2024-01-01',
        end_date='2025-12-21',
        ib_durations=[15, 30, 45, 60],
        entry_variant='play1',
        breakout_confirmation_type='touch'
    )
