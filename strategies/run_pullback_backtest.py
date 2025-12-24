"""
Run IB Pullback Strategy Backtest

Tests the pullback entry strategy with optimized parameters from MAE/MFE analysis
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))
sys.path.insert(0, str(Path(__file__).parent))

from enhanced_backtest_engine import EnhancedBacktestEngine
from initial_balance_pullback import IBPullbackStrategy
import pandas as pd


def run_pullback_backtest(
    ticker: str = 'NQ1',
    data_timeframe: str = '5m',
    start_date: str = '2024-01-01',
    end_date: str = '2025-12-21',
    ib_duration: int = 45,  # Best performer from previous analysis
    fib_entry_type: str = 'standard',  # 50% retracement
    min_confluence: int = 1
):
    """
    Run pullback strategy backtest
    
    Args:
        ticker: Ticker symbol
        data_timeframe: Data timeframe
        start_date: Start date
        end_date: End date
        ib_duration: IB duration in minutes
        fib_entry_type: 'aggressive' (38.2%), 'standard' (50%), 'conservative' (61.8%)
        min_confluence: Minimum confluence score (1-3)
    """
    
    print(f"\n{'#'*80}")
    print(f"# IB PULLBACK STRATEGY BACKTEST")
    print(f"# Based on MAE/MFE Analysis Optimization")
    print(f"{'#'*80}\n")
    
    # Create enhanced engine
    engine = EnhancedBacktestEngine(
        ticker=ticker,
        timeframe=data_timeframe,
        start_date=start_date,
        end_date=end_date,
        initial_capital=100000.0,
        commission=2.50,
        slippage_ticks=1
    )
    
    # Create pullback strategy
    strategy = IBPullbackStrategy(
        engine=engine,
        ib_duration_minutes=ib_duration,
        pullback_mechanisms=['fvg', 'fibonacci'],
        fvg_timeframes=['5m', '15m'],
        fib_entry_type=fib_entry_type,
        min_confluence_score=min_confluence,
        tp_r_multiples=[0.5, 1.0],  # Based on MAE/MFE analysis
        position_tiers=[0.5, 0.5],  # 50% at each TP
        use_optimized_stop=True  # Use -0.253% from MAE analysis
    )
    
    # Run backtest
    metrics = strategy.run()
    
    # Export results
    output_dir = Path('docs/strategies/initial_balance_break')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    csv_path = output_dir / f'pullback_results_{ib_duration}min.csv'
    engine.export_trades_to_csv(str(csv_path))
    
    print(f"\n✓ Results saved to: {csv_path}")
    
    # Compare with breakout results
    print(f"\n{'='*80}")
    print(f"COMPARISON: PULLBACK vs BREAKOUT")
    print(f"{'='*80}\n")
    
    # Load breakout results for comparison
    breakout_csv = output_dir / f'backtest_results_{ib_duration}min.csv'
    if breakout_csv.exists():
        df_breakout = pd.read_csv(breakout_csv)
        df_pullback = pd.read_csv(csv_path)
        
        print(f"{'Metric':<25} {'Breakout':<15} {'Pullback':<15} {'Change'}")
        print("-" * 70)
        
        # Total trades
        b_trades = len(df_breakout)
        p_trades = len(df_pullback)
        print(f"{'Total Trades':<25} {b_trades:<15} {p_trades:<15} {p_trades-b_trades:+d}")
        
        # Win rate
        b_wr = (df_breakout['result'] == 'WIN').sum() / len(df_breakout) * 100
        p_wr = (df_pullback['result'] == 'WIN').sum() / len(df_pullback) * 100 if len(df_pullback) > 0 else 0
        print(f"{'Win Rate':<25} {b_wr:<14.1f}% {p_wr:<14.1f}% {p_wr-b_wr:+.1f}%")
        
        # Avg MAE
        b_mae = df_breakout['mae_pct'].mean()
        p_mae = df_pullback['mae_pct'].mean() if len(df_pullback) > 0 else 0
        print(f"{'Avg MAE':<25} {b_mae:<14.2f}% {p_mae:<14.2f}% {p_mae-b_mae:+.2f}%")
        
        # Avg MFE
        b_mfe = df_breakout['mfe_pct'].mean()
        p_mfe = df_pullback['mfe_pct'].mean() if len(df_pullback) > 0 else 0
        print(f"{'Avg MFE':<25} {b_mfe:<14.2f}% {p_mfe:<14.2f}% {p_mfe-b_mfe:+.2f}%")
        
        # Total PnL
        b_pnl = df_breakout['pnl_pct'].sum()
        p_pnl = df_pullback['pnl_pct'].sum() if len(df_pullback) > 0 else 0
        print(f"{'Total PnL':<25} {b_pnl:<14.2f}% {p_pnl:<14.2f}% {p_pnl-b_pnl:+.2f}%")
        
        # Analyze MFE reach probability
        if len(df_pullback) > 0:
            print(f"\n{'='*80}")
            print(f"MFE REACH PROBABILITY (Target: Improve from 12.5% to 40-50%)")
            print(f"{'='*80}\n")
            
            for r_mult in [0.5, 1.0, 1.5, 2.0]:
                b_reach = (df_breakout['mfe_pct'] >= r_mult).sum() / len(df_breakout) * 100
                p_reach = (df_pullback['mfe_pct'] >= r_mult).sum() / len(df_pullback) * 100
                improvement = p_reach - b_reach
                status = "✓" if improvement > 0 else "✗"
                print(f"{r_mult}R: Breakout {b_reach:5.1f}% → Pullback {p_reach:5.1f}% ({improvement:+.1f}%) {status}")
    
    return metrics


if __name__ == '__main__':
    # Run pullback strategy backtest
    metrics = run_pullback_backtest(
        ticker='NQ1',
        data_timeframe='5m',
        start_date='2024-01-01',
        end_date='2025-12-21',
        ib_duration=45,  # Best from previous analysis
        fib_entry_type='standard',  # 50% Fibonacci retracement
        min_confluence=1  # Require at least 1 confluence factor
    )
    
    print(f"\n{'='*80}")
    print(f"PULLBACK STRATEGY BACKTEST COMPLETE!")
    print(f"{'='*80}")
