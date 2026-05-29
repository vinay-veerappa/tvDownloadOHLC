import pandas as pd
import numpy as np
import os
from datetime import time
from pathlib import Path
import sys

# Standard Path Resolution
project_root = str(Path(__file__).parent.parent.parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)
core_dir = str(Path(__file__).parent.parent / 'core')
if core_dir not in sys.path:
    sys.path.insert(0, core_dir)

from scripts.strategies.initial_balance.core.initial_balance_pullback import IBPullbackStrategy
from scripts.trading_framework.core.backtest_engine import VectorizedBacktester

def run_multi_asset_sweep():
    print("=" * 120)
    print("MULTI-ASSET COMPREHENSIVE STRATEGY MATRIX SWEEP (NQ1, ES1, RTY1, YM1, GC1, CL1)")
    print("=" * 120 + "\n")
    
    tickers = ['NQ1', 'ES1', 'RTY1', 'YM1', 'GC1', 'CL1']
    
    # Define our 4 core high-expectancy configurations
    configs = [
        {
            'name': 'RTH_45m_PreBreak_Q25',
            'session_preset': 'RTH',
            'ib_duration_min': 45,
            'entry_variant': 'pre_break',
            'pullback_level': 'q_25',
            'stop_loss_type': 'ib_opposite',
            'bias_source': 'ib_close'
        },
        {
            'name': 'RTH_30m_PreBreak_Fib50',
            'session_preset': 'RTH',
            'ib_duration_min': 30,
            'entry_variant': 'pre_break',
            'pullback_level': 'fib_50',
            'stop_loss_type': 'ib_opposite',
            'bias_source': 'ib_close'
        },
        {
            'name': 'Globex_45m_PostBreak_Edge_FVG_Inversion',
            'session_preset': 'Globex',
            'ib_duration_min': 45,
            'entry_variant': 'post_break',
            'pullback_level': 'ib_edge',
            'stop_loss_type': 'ib_opposite',
            'bias_source': 'fvg_inversion'
        },
        {
            'name': 'Tokyo_60m_PostBreak_Fib618',
            'session_preset': 'Tokyo',
            'ib_duration_min': 60,
            'entry_variant': 'post_break',
            'pullback_level': 'fib_618',
            'stop_loss_type': 'ib_opposite',
            'bias_source': 'ib_close'
        }
    ]
    
    results = []
    engine = VectorizedBacktester(slippage_pct=0.0001)
    
    # We will test on NQ1, ES1, YM1, RTY1, GC1, CL1 from 2021-01-01 to 2025-12-31
    start_date = '2021-01-01'
    end_date = '2025-12-31'
    
    for ticker in tickers:
        DATA_PATH = f"data/{ticker}_5m.parquet"
        if not os.path.exists(DATA_PATH):
            print(f"[WARNING] Data file not found for {ticker} at {DATA_PATH}, skipping...")
            continue
            
        print(f"[INFO] Loading {ticker} data...")
        df = pd.read_parquet(DATA_PATH)
        df = df.sort_index()
        
        # Localize timezone to America/New_York
        if df.index.tz is None:
            df.index = df.index.tz_localize('UTC').tz_convert('America/New_York')
        else:
            df.index = df.index.tz_convert('America/New_York')
            
        df_test = df[(df.index >= start_date) & (df.index <= end_date)].copy()
        print(f"   Successfully loaded {len(df_test)} bars.")
        
        for cfg in configs:
            print(f"   [RUNNING] {cfg['name']} on {ticker}...")
            
            strategy = IBPullbackStrategy(
                ticker=ticker,
                session_preset=cfg['session_preset'],
                ib_duration_min=cfg['ib_duration_min'],
                entry_variant=cfg['entry_variant'],
                pullback_level=cfg['pullback_level'],
                stop_loss_type=cfg['stop_loss_type'],
                bias_source=cfg['bias_source']
            )
            
            signals = strategy.hunt(df_test)
            metrics = engine.run(signals, df_test, {'ticker': ticker})
            
            # Advanced Metrics calculation
            if metrics['num_trades'] > 0 and not metrics['trades_detailed'].empty:
                td = metrics['trades_detailed']
                pnl = td['pnl_pct'].values
                wins = pnl[pnl > 0]
                losses = pnl[pnl < 0]
                
                gross_profits = wins.sum()
                gross_losses = abs(losses.sum())
                profit_factor = gross_profits / gross_losses if gross_losses > 0 else (np.inf if gross_profits > 0 else 1.0)
                
                avg_win = wins.mean() if len(wins) > 0 else 0.0
                avg_loss = abs(losses.mean()) if len(losses) > 0 else 0.0
                win_loss_ratio = avg_win / avg_loss if avg_loss > 0 else (np.inf if avg_win > 0 else 1.0)
                
                expectancy = pnl.mean()
                max_dd = metrics['max_drawdown_%']
                recovery_factor = abs(metrics['total_return_%'] / max_dd) if max_dd != 0 else 0.0
                
                avg_mfe = td['mfe_pct'].mean()
                avg_mae = td['mae_pct'].mean()
            else:
                profit_factor = 0.0
                avg_win = 0.0
                avg_loss = 0.0
                win_loss_ratio = 0.0
                expectancy = 0.0
                recovery_factor = 0.0
                avg_mfe = 0.0
                avg_mae = 0.0
                
            results.append({
                'Ticker': ticker,
                'Config Name': cfg['name'],
                'Session': cfg['session_preset'],
                'Duration': f"{cfg['ib_duration_min']}m",
                'Variant': cfg['entry_variant'],
                'Level': cfg['pullback_level'],
                'Trades': metrics['num_trades'],
                'Win Rate %': f"{metrics['win_rate_%']:.1f}%" if metrics['num_trades'] > 0 else "0.0%",
                'Profit Factor': f"{profit_factor:.2f}" if profit_factor != np.inf else "INF",
                'Sharpe': f"{metrics['sharpe_ratio']:.2f}" if metrics['num_trades'] > 0 else "0.00",
                'Max DD %': f"{metrics['max_drawdown_%']:.2f}%" if metrics['num_trades'] > 0 else "0.00%",
                'Avg Win %': f"{avg_win:.3f}%",
                'Avg Loss %': f"{avg_loss:.3f}%",
                'Win/Loss Ratio': f"{win_loss_ratio:.2f}" if win_loss_ratio != np.inf else "INF",
                'Expectancy %': f"{expectancy:.3f}%",
                'Recovery Factor': f"{recovery_factor:.2f}",
                'Avg MAE %': f"{avg_mae:.3f}%" if metrics['num_trades'] > 0 else "0.000%",
                'Avg MFE %': f"{avg_mfe:.3f}%" if metrics['num_trades'] > 0 else "0.000%",
                'Return %': f"{metrics['total_return_%']:.2f}%"
            })
            
    df_out = pd.DataFrame(results)
    
    # Save the results in both script data path and user docs path
    backup_dir = Path('scripts/strategies/initial_balance/data/comprehensive_sweep')
    backup_dir.mkdir(parents=True, exist_ok=True)
    df_out.to_csv(backup_dir / 'multi_asset_matrix_results.csv', index=False)
    
    docs_dir = Path(project_root) / 'docs' / 'strategies' / 'initial_balance_break' / 'results'
    docs_dir.mkdir(parents=True, exist_ok=True)
    comparison_csv = docs_dir / 'multi_asset_matrix_results.csv'
    df_out.to_csv(comparison_csv, index=False)
    
    print(f"\n[SUCCESS] Multi-asset comprehensive sweep complete! Results saved to: {comparison_csv}\n")
    print(df_out.to_markdown(index=False))
    print("\n" + "=" * 120)

if __name__ == "__main__":
    run_multi_asset_sweep()
