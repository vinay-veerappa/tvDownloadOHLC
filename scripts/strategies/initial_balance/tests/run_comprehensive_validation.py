import sys
from pathlib import Path
import os
import pandas as pd
import numpy as np

# Standard Path Resolution
project_root = str(Path(__file__).parent.parent.parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)
core_dir = str(Path(__file__).parent.parent / 'core')
if core_dir not in sys.path:
    sys.path.insert(0, core_dir)

from scripts.trading_framework.core.backtest_engine import VectorizedBacktester
from scripts.strategies.initial_balance.core.initial_balance_pullback import IBPullbackStrategy

def run_historical_validation():
    """Test on historical data 2015-2020 using modern vectorized framework"""
    print("="*100)
    print("HISTORICAL VALIDATION (2015-2020)")
    print("="*100)
    
    ticker = 'NQ1'
    DATA_PATH = f"data/{ticker}_5m.parquet"
    if not os.path.exists(DATA_PATH):
        print(f"[ERROR] NQ1 data not found at {DATA_PATH}")
        return []
        
    print(f"[INFO] Loading {ticker} data from {DATA_PATH}...")
    df = pd.read_parquet(DATA_PATH)
    df = df.sort_index()
    
    # Localize timezone to America/New_York
    if df.index.tz is None:
        df.index = df.index.tz_localize('UTC').tz_convert('America/New_York')
    else:
        df.index = df.index.tz_convert('America/New_York')
        
    engine = VectorizedBacktester(slippage_pct=0.0001)
    
    results = []
    test_periods = [
        ('2015-01-01', '2016-12-31', 'Bull Market 2015-2016'),
        ('2017-01-01', '2018-12-31', 'Bull + Correction 2017-2018'),
        ('2019-01-01', '2020-12-31', 'Recovery + COVID 2019-2020'),
        ('2021-01-01', '2025-12-31', 'Modern 5-Year Horizon 2021-2025'),
    ]
    
    for start_date, end_date, period_name in test_periods:
        print(f"\nTesting period: {period_name} ({start_date} to {end_date})")
        df_period = df[(df.index >= start_date) & (df.index <= end_date)].copy()
        print(f"   Successfully loaded {len(df_period)} bars.")
        
        if len(df_period) == 0:
            print("   [WARNING] No data found in this period, skipping...")
            continue
            
        strategy = IBPullbackStrategy(
            ticker=ticker,
            session_preset='RTH',
            ib_duration_min=45,
            entry_variant='pre_break',
            pullback_level='fib_382',
            stop_loss_type='ib_opposite',
            bias_source='ib_close'
        )
        
        signals = strategy.hunt(df_period)
        metrics = engine.run(signals, df_period, {'ticker': ticker})
        
        # Calculate advanced metrics
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
            
            # Export individual trade files
            backup_dir = Path('scripts/strategies/initial_balance/data/historical_validation')
            backup_dir.mkdir(parents=True, exist_ok=True)
            td.to_csv(backup_dir / f"nq_{start_date[:4]}_{end_date[:4]}.csv")
            
            docs_dir = Path(project_root) / 'docs' / 'strategies' / 'initial_balance_break' / 'research' / 'historical_validation'
            docs_dir.mkdir(parents=True, exist_ok=True)
            td.to_csv(docs_dir / f"nq_{start_date[:4]}_{end_date[:4]}.csv")
        else:
            profit_factor = 0.0
            avg_win = 0.0
            avg_loss = 0.0
            win_loss_ratio = 0.0
            expectancy = 0.0
            recovery_factor = 0.0
            
        results.append({
            'Period': period_name,
            'Start Date': start_date,
            'End Date': end_date,
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
            'Return %': f"{metrics['total_return_%']:.2f}%"
        })
        
    if results:
        df_results = pd.DataFrame(results)
        
        backup_path = Path('scripts/strategies/initial_balance/data/historical_validation/comparison.csv')
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        df_results.to_csv(backup_path, index=False)
        
        docs_path = Path(project_root) / 'docs' / 'strategies' / 'initial_balance_break' / 'research' / 'historical_validation' / 'comparison.csv'
        docs_path.parent.mkdir(parents=True, exist_ok=True)
        df_results.to_csv(docs_path, index=False)
        
        print(f"\n{'='*100}")
        print("HISTORICAL VALIDATION RESULTS")
        print("="*100 + "\n")
        print(df_results.to_markdown(index=False))
        print(f"\n[SUCCESS] Comparison saved to: {docs_path}")
        
    return results

def run_multi_asset_validation():
    """Test on different asset types using modern vectorized framework"""
    print("\n" + "="*100)
    print("MULTI-ASSET VALIDATION (2019-2020)")
    print("="*100)
    
    assets = [
        ('ES1', 'E-mini S&P 500'),
        ('RTY1', 'E-mini Russell 2000'),
        ('YM1', 'E-mini Dow Jones'),
        ('GC1', 'Gold Futures'),
    ]
    
    start_date = '2021-01-01'
    end_date = '2025-12-31'
    results = []
    
    engine = VectorizedBacktester(slippage_pct=0.0001)
    
    for ticker, name in assets:
        print(f"\nTesting asset: {name} ({ticker})")
        DATA_PATH = f"data/{ticker}_5m.parquet"
        if not os.path.exists(DATA_PATH):
            print(f"   [WARNING] Data file not found for {ticker} at {DATA_PATH}, skipping...")
            continue
            
        df = pd.read_parquet(DATA_PATH)
        df = df.sort_index()
        
        # Localize timezone to America/New_York
        if df.index.tz is None:
            df.index = df.index.tz_localize('UTC').tz_convert('America/New_York')
        else:
            df.index = df.index.tz_convert('America/New_York')
            
        df_period = df[(df.index >= start_date) & (df.index <= end_date)].copy()
        print(f"   Successfully loaded {len(df_period)} bars.")
        
        strategy = IBPullbackStrategy(
            ticker=ticker,
            session_preset='RTH',
            ib_duration_min=45,
            entry_variant='pre_break',
            pullback_level='fib_382',
            stop_loss_type='ib_opposite',
            bias_source='ib_close'
        )
        
        signals = strategy.hunt(df_period)
        metrics = engine.run(signals, df_period, {'ticker': ticker})
        
        # Calculate advanced metrics
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
            
            # Export individual trade files
            backup_dir = Path('scripts/strategies/initial_balance/data/multi_asset_validation')
            backup_dir.mkdir(parents=True, exist_ok=True)
            td.to_csv(backup_dir / f"{ticker.lower()}_2019_2020.csv")
            
            docs_dir = Path(project_root) / 'docs' / 'strategies' / 'initial_balance_break' / 'research' / 'multi_asset_validation'
            docs_dir.mkdir(parents=True, exist_ok=True)
            td.to_csv(docs_dir / f"{ticker.lower()}_2019_2020.csv")
        else:
            profit_factor = 0.0
            avg_win = 0.0
            avg_loss = 0.0
            win_loss_ratio = 0.0
            expectancy = 0.0
            recovery_factor = 0.0
            
        results.append({
            'Ticker': ticker,
            'Name': name,
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
            'Return %': f"{metrics['total_return_%']:.2f}%"
        })
        
    if results:
        df_results = pd.DataFrame(results)
        
        backup_path = Path('scripts/strategies/initial_balance/data/multi_asset_validation/comparison.csv')
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        df_results.to_csv(backup_path, index=False)
        
        docs_path = Path(project_root) / 'docs' / 'strategies' / 'initial_balance_break' / 'research' / 'multi_asset_validation' / 'comparison.csv'
        docs_path.parent.mkdir(parents=True, exist_ok=True)
        df_results.to_csv(docs_path, index=False)
        
        print(f"\n{'='*100}")
        print("MULTI-ASSET VALIDATION RESULTS")
        print("="*100 + "\n")
        print(df_results.to_markdown(index=False))
        print(f"\n[SUCCESS] Comparison saved to: {docs_path}")
        
    return results

if __name__ == '__main__':
    print("\n" + "="*100)
    print("COMPREHENSIVE VALIDATION TESTING")
    print("="*100)
    
    historical_results = run_historical_validation()
    multi_asset_results = run_multi_asset_validation()
    
    print("\n" + "="*100)
    print("ALL VALIDATION TESTS COMPLETE!")
    print("="*100)
