"""
Historical and Multi-Asset Validation

Test the IB Break pullback strategy:
1. Historical: 2015-2020 (500+ days, different market regimes)
2. Multi-Asset: ES, RTY, YM, GC (validate robustness)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))
sys.path.insert(0, str(Path(__file__).parent))

from enhanced_backtest_engine import EnhancedBacktestEngine
from initial_balance_pullback import IBPullbackStrategy
import pandas as pd
from datetime import datetime

def run_historical_validation():
    """Test on historical data 2015-2020"""
    
    print("="*100)
    print("HISTORICAL VALIDATION (2015-2020)")
    print("="*100)
    
    results = []
    
    # Test periods covering different market regimes
    test_periods = [
        ('2015-01-01', '2016-12-31', 'Bull Market 2015-2016'),
        ('2017-01-01', '2018-12-31', 'Bull + Correction 2017-2018'),
        ('2019-01-01', '2020-12-31', 'Recovery + COVID 2019-2020'),
    ]
    
    for start_date, end_date, period_name in test_periods:
        print(f"\n{'#'*100}")
        print(f"# Testing: {period_name}")
        print(f"# Period: {start_date} to {end_date}")
        print(f"{'#'*100}\n")
        
        engine = EnhancedBacktestEngine(
            ticker='NQ1',
            timeframe='5m',
            start_date=start_date,
            end_date=end_date,
            initial_capital=100000.0,
            commission=2.50,
            slippage_ticks=1
        )
        
        strategy = IBPullbackStrategy(
            engine=engine,
            ib_duration_minutes=45,
            pullback_mechanisms=['fibonacci'],
            fvg_timeframes=[],
            fib_entry_type='aggressive',  # 38.2%
            min_confluence_score=1,
            tp_r_multiples=[0.5, 1.0],
            position_tiers=[0.5, 0.5],
            use_optimized_stop=False  # IB opposite
        )
        
        try:
            metrics = strategy.run()
            
            # Export results
            output_dir = Path('docs/strategies/initial_balance_break/historical_validation')
            output_dir.mkdir(parents=True, exist_ok=True)
            
            csv_path = output_dir / f"nq_{start_date[:4]}_{end_date[:4]}.csv"
            engine.export_trades_to_csv(str(csv_path))
            
            results.append({
                'period': period_name,
                'start_date': start_date,
                'end_date': end_date,
                **metrics
            })
        except Exception as e:
            print(f"⚠ Error testing {period_name}: {e}")
            results.append({
                'period': period_name,
                'start_date': start_date,
                'end_date': end_date,
                'error': str(e)
            })
    
    # Save comparison
    if results:
        df_results = pd.DataFrame(results)
        comparison_path = Path('docs/strategies/initial_balance_break/historical_validation/comparison.csv')
        df_results.to_csv(comparison_path, index=False)
        
        print(f"\n{'='*100}")
        print("HISTORICAL VALIDATION RESULTS")
        print("="*100 + "\n")
        
        display_cols = ['period', 'total_trades', 'win_rate', 'profit_factor', 'total_return_pct']
        available_cols = [col for col in display_cols if col in df_results.columns]
        print(df_results[available_cols].to_string(index=False))
        
        print(f"\n✓ Results saved to: {comparison_path}")
    
    return results


def run_multi_asset_validation():
    """Test on different asset types"""
    
    print("\n" + "="*100)
    print("MULTI-ASSET VALIDATION")
    print("="*100)
    
    results = []
    
    # Assets to test
    assets = [
        ('ES1', 'E-mini S&P 500'),
        ('RTY1', 'E-mini Russell 2000'),
        ('YM1', 'E-mini Dow Jones'),
        ('GC1', 'Gold Futures'),
    ]
    
    # Use 2019-2020 period (good data availability)
    start_date = '2019-01-01'
    end_date = '2020-12-31'
    
    for ticker, name in assets:
        print(f"\n{'#'*100}")
        print(f"# Testing: {name} ({ticker})")
        print(f"# Period: {start_date} to {end_date}")
        print(f"{'#'*100}\n")
        
        # Check if data file exists
        data_file = Path(f'data/{ticker}_5m.parquet')
        if not data_file.exists():
            print(f"⚠ No data file for {ticker}, skipping...")
            results.append({
                'ticker': ticker,
                'name': name,
                'error': 'No data file'
            })
            continue
        
        engine = EnhancedBacktestEngine(
            ticker=ticker,
            timeframe='5m',
            start_date=start_date,
            end_date=end_date,
            initial_capital=100000.0,
            commission=2.50,
            slippage_ticks=1
        )
        
        strategy = IBPullbackStrategy(
            engine=engine,
            ib_duration_minutes=45,
            pullback_mechanisms=['fibonacci'],
            fvg_timeframes=[],
            fib_entry_type='aggressive',  # 38.2%
            min_confluence_score=1,
            tp_r_multiples=[0.5, 1.0],
            position_tiers=[0.5, 0.5],
            use_optimized_stop=False  # IB opposite
        )
        
        try:
            metrics = strategy.run()
            
            # Export results
            output_dir = Path('docs/strategies/initial_balance_break/multi_asset_validation')
            output_dir.mkdir(parents=True, exist_ok=True)
            
            csv_path = output_dir / f"{ticker.lower()}_2019_2020.csv"
            engine.export_trades_to_csv(str(csv_path))
            
            results.append({
                'ticker': ticker,
                'name': name,
                **metrics
            })
        except Exception as e:
            print(f"⚠ Error testing {ticker}: {e}")
            results.append({
                'ticker': ticker,
                'name': name,
                'error': str(e)
            })
    
    # Save comparison
    if results:
        df_results = pd.DataFrame(results)
        comparison_path = Path('docs/strategies/initial_balance_break/multi_asset_validation/comparison.csv')
        df_results.to_csv(comparison_path, index=False)
        
        print(f"\n{'='*100}")
        print("MULTI-ASSET VALIDATION RESULTS")
        print("="*100 + "\n")
        
        display_cols = ['ticker', 'name', 'total_trades', 'win_rate', 'profit_factor', 'total_return_pct']
        available_cols = [col for col in display_cols if col in df_results.columns]
        print(df_results[available_cols].to_string(index=False))
        
        print(f"\n✓ Results saved to: {comparison_path}")
    
    return results


if __name__ == '__main__':
    print("\n" + "="*100)
    print("COMPREHENSIVE VALIDATION TESTING")
    print("="*100)
    
    # Run historical validation
    historical_results = run_historical_validation()
    
    # Run multi-asset validation
    multi_asset_results = run_multi_asset_validation()
    
    print("\n" + "="*100)
    print("ALL VALIDATION TESTS COMPLETE!")
    print("="*100)
