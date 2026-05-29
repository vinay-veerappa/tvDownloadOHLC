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

def run_comprehensive_variants():
    print("=" * 100)
    print("COMPREHENSIVE MULTI-VARIANT MATRIX SWEEP")
    print("=" * 100 + "\n")
    
    # 1. Load Data
    ticker = 'NQ1'
    DATA_PATH = f"data/{ticker}_5m.parquet"
    if not os.path.exists(DATA_PATH):
        print(f"[ERROR] Data not found at {DATA_PATH}")
        return
        
    print(f"[INFO] Loading NQ 5-minute data from {DATA_PATH}...")
    df = pd.read_parquet(DATA_PATH)
    df = df.sort_index()
    
    # Localize timezone to America/New_York
    if df.index.tz is None:
        df.index = df.index.tz_localize('UTC').tz_convert('America/New_York')
    else:
        df.index = df.index.tz_convert('America/New_York')
        
    # We will test on a 5-year dataset to ensure deep, robust verification
    start_date = '2021-01-01'
    end_date = '2025-12-31'
    df_test = df[(df.index >= start_date) & (df.index <= end_date)].copy()
    
    print(f"[SUCCESS] Data loaded successfully. Test window: {start_date} to {end_date} ({len(df_test)} bars).\n")
    
    # 2. Define our matrix configurations
    configs = [
        # --- RTH Sessions ---
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
            'name': 'RTH_30m_PreBreak_Fib50_Sequence_Bias',
            'session_preset': 'RTH',
            'ib_duration_min': 30,
            'entry_variant': 'pre_break',
            'pullback_level': 'fib_50',
            'stop_loss_type': 'ib_opposite',
            'bias_source': 'sequence'
        },
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
            'name': 'RTH_45m_PreBreak_Q25_Sequence_Bias',
            'session_preset': 'RTH',
            'ib_duration_min': 45,
            'entry_variant': 'pre_break',
            'pullback_level': 'q_25',
            'stop_loss_type': 'ib_opposite',
            'bias_source': 'sequence'
        },
        {
            'name': 'RTH_45m_PostBreak_Edge_OppSL',
            'session_preset': 'RTH',
            'ib_duration_min': 45,
            'entry_variant': 'post_break',
            'pullback_level': 'ib_edge',
            'stop_loss_type': 'ib_opposite',
            'bias_source': 'ib_close'
        },
        {
            'name': 'RTH_45m_PostBreak_Edge_EdgeSL',
            'session_preset': 'RTH',
            'ib_duration_min': 45,
            'entry_variant': 'post_break',
            'pullback_level': 'ib_edge',
            'stop_loss_type': 'ib_edge',
            'bias_source': 'ib_close'
        },
        {
            'name': 'RTH_60m_PostBreak_Fib618',
            'session_preset': 'RTH',
            'ib_duration_min': 60,
            'entry_variant': 'post_break',
            'pullback_level': 'fib_618',
            'stop_loss_type': 'ib_opposite',
            'bias_source': 'ib_close'
        },
        {
            'name': 'RTH_45m_PostBreak_Edge_FVG_Bias',
            'session_preset': 'RTH',
            'ib_duration_min': 45,
            'entry_variant': 'post_break',
            'pullback_level': 'ib_edge',
            'stop_loss_type': 'ib_opposite',
            'bias_source': 'fvg'
        },
        {
            'name': 'RTH_45m_PostBreak_Edge_FVG_Inversion',
            'session_preset': 'RTH',
            'ib_duration_min': 45,
            'entry_variant': 'post_break',
            'pullback_level': 'ib_edge',
            'stop_loss_type': 'ib_opposite',
            'bias_source': 'fvg_inversion'
        },
        
        # --- Globex Sessions (Starts 18:00) ---
        {
            'name': 'Globex_30m_PreBreak_Fib50',
            'session_preset': 'Globex',
            'ib_duration_min': 30,
            'entry_variant': 'pre_break',
            'pullback_level': 'fib_50',
            'stop_loss_type': 'ib_opposite',
            'bias_source': 'ib_close'
        },
        {
            'name': 'Globex_30m_PreBreak_Fib50_Sequence_Bias',
            'session_preset': 'Globex',
            'ib_duration_min': 30,
            'entry_variant': 'pre_break',
            'pullback_level': 'fib_50',
            'stop_loss_type': 'ib_opposite',
            'bias_source': 'sequence'
        },
        {
            'name': 'Globex_45m_PostBreak_Edge',
            'session_preset': 'Globex',
            'ib_duration_min': 45,
            'entry_variant': 'post_break',
            'pullback_level': 'ib_edge',
            'stop_loss_type': 'ib_opposite',
            'bias_source': 'ib_close'
        },
        {
            'name': 'Globex_45m_PostBreak_Edge_Sequence_Bias',
            'session_preset': 'Globex',
            'ib_duration_min': 45,
            'entry_variant': 'post_break',
            'pullback_level': 'ib_edge',
            'stop_loss_type': 'ib_opposite',
            'bias_source': 'sequence'
        },
        {
            'name': 'Globex_60m_PostBreak_Fib618',
            'session_preset': 'Globex',
            'ib_duration_min': 60,
            'entry_variant': 'post_break',
            'pullback_level': 'fib_618',
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
        
        # --- Tokyo Sessions (Starts 19:00) ---
        {
            'name': 'Tokyo_30m_PreBreak_Fib50',
            'session_preset': 'Tokyo',
            'ib_duration_min': 30,
            'entry_variant': 'pre_break',
            'pullback_level': 'fib_50',
            'stop_loss_type': 'ib_opposite',
            'bias_source': 'ib_close'
        },
        {
            'name': 'Tokyo_30m_PreBreak_Fib50_Sequence_Bias',
            'session_preset': 'Tokyo',
            'ib_duration_min': 30,
            'entry_variant': 'pre_break',
            'pullback_level': 'fib_50',
            'stop_loss_type': 'ib_opposite',
            'bias_source': 'sequence'
        },
        {
            'name': 'Tokyo_45m_PostBreak_Edge',
            'session_preset': 'Tokyo',
            'ib_duration_min': 45,
            'entry_variant': 'post_break',
            'pullback_level': 'ib_edge',
            'stop_loss_type': 'ib_opposite',
            'bias_source': 'ib_close'
        },
        {
            'name': 'Tokyo_45m_PostBreak_Edge_Sequence_Bias',
            'session_preset': 'Tokyo',
            'ib_duration_min': 45,
            'entry_variant': 'post_break',
            'pullback_level': 'ib_edge',
            'stop_loss_type': 'ib_opposite',
            'bias_source': 'sequence'
        },
        {
            'name': 'Tokyo_60m_PostBreak_Fib618',
            'session_preset': 'Tokyo',
            'ib_duration_min': 60,
            'entry_variant': 'post_break',
            'pullback_level': 'fib_618',
            'stop_loss_type': 'ib_opposite',
            'bias_source': 'ib_close'
        },
        {
            'name': 'Tokyo_45m_PostBreak_Edge_FVG_Inversion',
            'session_preset': 'Tokyo',
            'ib_duration_min': 45,
            'entry_variant': 'post_break',
            'pullback_level': 'ib_edge',
            'stop_loss_type': 'ib_opposite',
            'bias_source': 'fvg_inversion'
        }
    ]
    
    results = []
    
    # 3. Execution Sweep
    engine = VectorizedBacktester(slippage_pct=0.0001)
    
    print(f"[RUNNING] Sweeping {len(configs)} configurations across the matrix...")
    
    for i, cfg in enumerate(configs, 1):
        print(f"   [{i}/{len(configs)}] Running {cfg['name']}...")
        
        strategy = IBPullbackStrategy(
            ticker=ticker,
            session_preset=cfg['session_preset'],
            ib_duration_min=cfg['ib_duration_min'],
            entry_variant=cfg['entry_variant'],
            pullback_level=cfg['pullback_level'],
            stop_loss_type=cfg['stop_loss_type'],
            bias_source=cfg['bias_source']
        )
        
        # Hunt for signals
        signals = strategy.hunt(df_test)
        
        # Run vectorized backtester
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
            'Config Name': cfg['name'],
            'Session': cfg['session_preset'],
            'Duration': f"{cfg['ib_duration_min']}m",
            'Variant': cfg['entry_variant'],
            'Level': cfg['pullback_level'],
            'SL Type': cfg['stop_loss_type'],
            'Bias': cfg['bias_source'],
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
            'Avg MAE %': f"{avg_mae:.3f}%",
            'Avg MFE %': f"{avg_mfe:.3f}%",
            'Return %': f"{metrics['total_return_%']:.2f}%"
        })
        
    df_out = pd.DataFrame(results)
    
    # Save the results in both script data path and user docs path
    backup_dir = Path('scripts/strategies/initial_balance/data/comprehensive_sweep')
    backup_dir.mkdir(parents=True, exist_ok=True)
    df_out.to_csv(backup_dir / 'matrix_results.csv', index=False)
    
    docs_dir = Path(project_root) / 'docs' / 'strategies' / 'initial_balance_break' / 'results'
    docs_dir.mkdir(parents=True, exist_ok=True)
    comparison_csv = docs_dir / 'matrix_results.csv'
    df_out.to_csv(comparison_csv, index=False)
    
    print(f"\n[SUCCESS] All runs complete! Matrix results saved to: {comparison_csv}\n")
    
    # Print the beautiful comparison Markdown table
    print(df_out.to_markdown(index=False))
    print("\n" + "=" * 100)

if __name__ == "__main__":
    run_comprehensive_variants()
