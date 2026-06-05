"""
Run IB Pullback Strategy Backtest
Vectorized and aligned with IBPullbackStrategy signature.
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Project root-based imports
project_root = str(Path(__file__).parent.parent.parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)
core_dir = str(Path(__file__).parent)
if core_dir not in sys.path:
    sys.path.insert(0, core_dir)

from scripts.trading_framework.core.backtest_engine import VectorizedBacktester as EnhancedBacktestEngine
from scripts.strategies.initial_balance.core.initial_balance_pullback import IBPullbackStrategy

def run_pullback_backtest(
    ticker: str = 'NQ1',
    start_date: str = '2024-01-01',
    end_date: str = '2025-12-21',
    ib_duration: int = 45,
    pullback_level: str = 'fib_50',
    entry_variant: str = 'post_break',
    bias_source: str = 'ib_close'
):
    """
    Run pullback strategy backtest.
    """
    print(f"\n{'#'*80}")
    print(f"# IB PULLBACK STRATEGY BACKTEST")
    print(f"# Dynamic parameter configurations")
    print(f"{'#'*80}\n")
    
    # Load data
    data_path = Path(f"data/{ticker}_1m.parquet")
    if not data_path.exists():
        data_path = Path(f"data/{ticker}_5m.parquet")
        if not data_path.exists():
            raise FileNotFoundError(f"Data for {ticker} not found.")
            
    print(f"[INFO] Loading data from {data_path}...")
    df = pd.read_parquet(data_path)
    df = df.sort_index()
    
    if df.index.tz is None:
        df.index = df.index.tz_localize('UTC').tz_convert('America/New_York')
    else:
        df.index = df.index.tz_convert('America/New_York')
        
    df_test = df[(df.index >= start_date) & (df.index <= end_date)].copy()
    
    # Create engine
    engine = EnhancedBacktestEngine(slippage_pct=0.0001)
    
    # Create pullback strategy
    strategy = IBPullbackStrategy(
        ticker=ticker,
        session_preset="RTH",
        ib_duration_min=ib_duration,
        entry_variant=entry_variant,
        pullback_level=pullback_level,
        stop_loss_type="ib_opposite",
        bias_source=bias_source,
        tp_r_mult=1.0
    )
    
    # Hunt signals
    signals = strategy.hunt(df_test)
    
    # Run backtest
    metrics = engine.run(signals, df_test, {'ticker': ticker})
    
    # Export results
    output_dir = Path('scripts/strategies/initial_balance/data')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    csv_path = output_dir / f'pullback_results_{ib_duration}min.csv'
    trades_detailed = metrics.get('trades_detailed', pd.DataFrame())
    if not trades_detailed.empty:
        extra_cols = [c for c in signals.columns if c not in trades_detailed.columns]
        trades_detailed = trades_detailed.join(signals[extra_cols])
    trades_detailed.to_csv(csv_path, index=True)
    
    print(f"\n[SUCCESS] Detailed pullback trades exported to: {csv_path}")
    
    # Compare with breakout results
    print(f"\n{'='*80}")
    print(f"COMPARISON: PULLBACK vs BREAKOUT")
    print(f"{'='*80}\n")
    
    breakout_csv = output_dir / f'backtest_results_{ib_duration}min.csv'
    if breakout_csv.exists() and not trades_detailed.empty:
        df_breakout = pd.read_csv(breakout_csv)
        df_pullback = trades_detailed
        
        print(f"{'Metric':<25} {'Breakout':<15} {'Pullback':<15} {'Change'}")
        print("-" * 70)
        
        b_trades = len(df_breakout)
        p_trades = len(df_pullback)
        print(f"{'Total Trades':<25} {b_trades:<15} {p_trades:<15} {p_trades-b_trades:+d}")
        
        # Guard against zero-trade edge case
        b_wins = (df_breakout['pnl_pct'] > 0).sum() if 'pnl_pct' in df_breakout.columns else 0
        b_wr = b_wins / b_trades * 100 if b_trades > 0 else 0
        p_wr = (df_pullback['pnl_pct'] > 0).sum() / p_trades * 100 if p_trades > 0 else 0
        print(f"{'Win Rate':<25} {b_wr:<14.1f}% {p_wr:<14.1f}% {p_wr-b_wr:+.1f}%")
        
        b_mae = df_breakout['mae_pct'].mean() if 'mae_pct' in df_breakout.columns else 0
        p_mae = df_pullback['mae_pct'].mean()
        print(f"{'Avg MAE':<25} {b_mae:<14.2f}% {p_mae:<14.2f}% {p_mae-b_mae:+.2f}%")
        
        b_mfe = df_breakout['mfe_pct'].mean() if 'mfe_pct' in df_breakout.columns else 0
        p_mfe = df_pullback['mfe_pct'].mean()
        print(f"{'Avg MFE':<25} {b_mfe:<14.2f}% {p_mfe:<14.2f}% {p_mfe-b_mfe:+.2f}%")
        
        b_pnl = df_breakout['pnl_pct'].sum() if 'pnl_pct' in df_breakout.columns else 0
        p_pnl = df_pullback['pnl_pct'].sum()
        print(f"{'Total PnL':<25} {b_pnl:<14.2f}% {p_pnl:<14.2f}% {p_pnl-b_pnl:+.2f}%")
        
    return metrics

if __name__ == '__main__':
    run_pullback_backtest(
        ticker='NQ1',
        start_date='2024-01-01',
        end_date='2025-12-21',
        ib_duration=45,
        pullback_level='fib_50',
        entry_variant='post_break',
        bias_source='ib_close'
    )
