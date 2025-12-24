"""
Run IB Break Strategy Backtest with Multiple Timeframes

This script runs the IB Break strategy across multiple IB durations
(15min, 30min, 45min, 60min) to compare performance and capture
comprehensive statistics.
"""

import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))
sys.path.insert(0, str(Path(__file__).parent))

from backtest_engine import BacktestEngine
from initial_balance_break import IBBreakStrategy
import pandas as pd


def run_multi_timeframe_backtest(
    ticker: str = 'NQ1',
    data_timeframe: str = '5m',
    start_date: str = '2024-01-01',
    end_date: str = '2025-12-31',
    ib_durations: list = [15, 30, 45, 60],
    entry_variant: str = 'breakout',
    use_ict_fvg: bool = True,
    use_ict_killzones: bool = True
):
    """
    Run backtest across multiple IB timeframes
    
    Args:
        ticker: Ticker symbol
        data_timeframe: Data timeframe for loading
        start_date: Backtest start date
        end_date: Backtest end date
        ib_durations: List of IB durations to test (minutes)
        entry_variant: Entry method
        use_ict_fvg: Use ICT Fair Value Gaps
        use_ict_killzones: Use ICT Kill Zones
    """
    
    results = {}
    all_trades = []
    
    for ib_duration in ib_durations:
        print(f"\n{'#'*80}")
        print(f"# Testing IB Duration: {ib_duration} minutes")
        print(f"{'#'*80}\n")
        
        # Create engine
        engine = BacktestEngine(
            ticker=ticker,
            timeframe=data_timeframe,
            start_date=start_date,
            end_date=end_date,
            initial_capital=100000.0,
            commission=2.50,
            slippage_ticks=1
        )
        
        # Create strategy
        strategy = IBBreakStrategy(
            engine=engine,
            ib_duration_minutes=ib_duration,
            entry_variant=entry_variant,
            use_ict_fvg=use_ict_fvg,
            use_ict_killzones=use_ict_killzones,
            min_ib_range_pct=0.3,
            max_ib_range_pct=2.0,
            stop_loss_type='ib_opposite',
            take_profit_r_multiple=2.0
        )
        
        # Run backtest
        metrics = strategy.run()
        results[ib_duration] = metrics
        
        # Export trades
        output_dir = Path(f'docs/strategies/initial_balance_break')
        output_dir.mkdir(parents=True, exist_ok=True)
        
        csv_path = output_dir / f'backtest_results_{ib_duration}min.csv'
        engine.export_trades_to_csv(str(csv_path))
        
        # Collect all trades
        if len(engine.trades) > 0:
            df_trades = pd.DataFrame(engine.trades)
            df_trades['ib_duration'] = ib_duration
            all_trades.append(df_trades)
    
    # Combine all trades
    if len(all_trades) > 0:
        combined_trades = pd.concat(all_trades, ignore_index=True)
        combined_path = Path('docs/strategies/initial_balance_break/backtest_results_all.csv')
        combined_trades.to_csv(combined_path, index=False)
        print(f"\n✓ Combined results saved to: {combined_path}")
    
    # Print comparison
    print(f"\n{'='*80}")
    print(f"MULTI-TIMEFRAME COMPARISON")
    print(f"{'='*80}\n")
    
    comparison_df = pd.DataFrame(results).T
    comparison_df.index.name = 'IB_Duration_Min'
    
    print(comparison_df.to_string())
    
    # Save comparison
    comparison_path = Path('docs/strategies/initial_balance_break/timeframe_comparison.csv')
    comparison_df.to_csv(comparison_path)
    print(f"\n✓ Comparison saved to: {comparison_path}")
    
    # Identify best timeframe
    if len(comparison_df) > 0:
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
    # Run backtest with multiple IB timeframes
    results = run_multi_timeframe_backtest(
        ticker='NQ1',
        data_timeframe='5m',
        start_date='2024-01-01',
        end_date='2025-12-21',
        ib_durations=[15, 30, 45, 60],
        entry_variant='breakout',  # Try: 'breakout', 'pullback'
        use_ict_fvg=True,
        use_ict_killzones=True
    )
    
    print(f"\n{'='*80}")
    print(f"BACKTEST COMPLETE!")
    print(f"{'='*80}")
    print(f"\nResults saved to: docs/strategies/initial_balance_break/")
    print(f"  - backtest_results_15min.csv")
    print(f"  - backtest_results_30min.csv")
    print(f"  - backtest_results_45min.csv")
    print(f"  - backtest_results_60min.csv")
    print(f"  - backtest_results_all.csv (combined)")
    print(f"  - timeframe_comparison.csv (summary)")
