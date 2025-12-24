"""
Pullback Mechanism Evaluation Framework

Tests each pullback mechanism independently to determine:
- Which mechanisms work best
- Optimal confluence combinations
- Performance by Fibonacci level
- Performance by FVG timeframe
- Impact of each component on final results
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))
sys.path.insert(0, str(Path(__file__).parent))

from enhanced_backtest_engine import EnhancedBacktestEngine
from initial_balance_pullback import IBPullbackStrategy
import pandas as pd
from typing import List, Dict


def run_mechanism_evaluation(
    ticker: str = 'NQ1',
    start_date: str = '2024-01-01',
    end_date: str = '2025-12-21',
    ib_duration: int = 45
):
    """
    Evaluate each pullback mechanism independently
    
    Tests:
    1. Fibonacci-only (38.2%, 50%, 61.8%)
    2. FVG-only (5m, 15m)
    3. Fibonacci + FVG combinations
    4. Different confluence requirements
    """
    
    results = []
    
    # Test configurations
    test_configs = [
        # Fibonacci-only tests
        {
            'name': 'Fib_38.2_Only',
            'mechanisms': ['fibonacci'],
            'fvg_timeframes': [],
            'fib_type': 'aggressive',
            'min_confluence': 1
        },
        {
            'name': 'Fib_50_Only',
            'mechanisms': ['fibonacci'],
            'fvg_timeframes': [],
            'fib_type': 'standard',
            'min_confluence': 1
        },
        {
            'name': 'Fib_61.8_Only',
            'mechanisms': ['fibonacci'],
            'fvg_timeframes': [],
            'fib_type': 'conservative',
            'min_confluence': 1
        },
        
        # FVG-only tests
        {
            'name': 'FVG_5m_Only',
            'mechanisms': ['fvg'],
            'fvg_timeframes': ['5m'],
            'fib_type': 'standard',
            'min_confluence': 1
        },
        {
            'name': 'FVG_15m_Only',
            'mechanisms': ['fvg'],
            'fvg_timeframes': ['15m'],
            'fib_type': 'standard',
            'min_confluence': 1
        },
        
        # Confluence combinations
        {
            'name': 'Fib_50_+_FVG_5m',
            'mechanisms': ['fibonacci', 'fvg'],
            'fvg_timeframes': ['5m'],
            'fib_type': 'standard',
            'min_confluence': 2
        },
        {
            'name': 'Fib_50_+_FVG_15m',
            'mechanisms': ['fibonacci', 'fvg'],
            'fvg_timeframes': ['15m'],
            'fib_type': 'standard',
            'min_confluence': 2
        },
        {
            'name': 'Fib_50_+_FVG_Both',
            'mechanisms': ['fibonacci', 'fvg'],
            'fvg_timeframes': ['5m', '15m'],
            'fib_type': 'standard',
            'min_confluence': 2
        },
        {
            'name': 'Fib_61.8_+_FVG_15m',
            'mechanisms': ['fibonacci', 'fvg'],
            'fvg_timeframes': ['15m'],
            'fib_type': 'conservative',
            'min_confluence': 2
        },
        
        # High confluence (best quality)
        {
            'name': 'Fib_50_+_FVG_Both_HighConf',
            'mechanisms': ['fibonacci', 'fvg'],
            'fvg_timeframes': ['5m', '15m'],
            'fib_type': 'standard',
            'min_confluence': 3
        }
    ]
    
    print(f"\n{'='*100}")
    print(f"PULLBACK MECHANISM EVALUATION - Testing {len(test_configs)} Configurations")
    print(f"{'='*100}\n")
    
    for i, config in enumerate(test_configs, 1):
        print(f"\n{'#'*100}")
        print(f"# Test {i}/{len(test_configs)}: {config['name']}")
        print(f"# Mechanisms: {config['mechanisms']}")
        print(f"# FVG Timeframes: {config['fvg_timeframes']}")
        print(f"# Fibonacci: {config['fib_type']}")
        print(f"# Min Confluence: {config['min_confluence']}")
        print(f"{'#'*100}\n")
        
        # Create engine
        engine = EnhancedBacktestEngine(
            ticker=ticker,
            timeframe='5m',
            start_date=start_date,
            end_date=end_date,
            initial_capital=100000.0,
            commission=2.50,
            slippage_ticks=1
        )
        
        # Create strategy
        strategy = IBPullbackStrategy(
            engine=engine,
            ib_duration_minutes=ib_duration,
            pullback_mechanisms=config['mechanisms'],
            fvg_timeframes=config['fvg_timeframes'],
            fib_entry_type=config['fib_type'],
            min_confluence_score=config['min_confluence'],
            tp_r_multiples=[0.5, 1.0],
            position_tiers=[0.5, 0.5],
            use_optimized_stop=True
        )
        
        # Run backtest
        metrics = strategy.run()
        
        # Export results
        output_dir = Path('docs/strategies/initial_balance_break/mechanism_evaluation')
        output_dir.mkdir(parents=True, exist_ok=True)
        
        csv_path = output_dir / f"{config['name']}.csv"
        engine.export_trades_to_csv(str(csv_path))
        
        # Calculate MFE reach probabilities
        if len(engine.trades) > 0:
            df = pd.DataFrame(engine.trades)
            mfe_reach = {}
            for r in [0.5, 1.0, 1.5, 2.0]:
                mfe_reach[f'{r}R'] = (df['mfe_pct'] >= r).sum() / len(df) * 100
        else:
            mfe_reach = {f'{r}R': 0 for r in [0.5, 1.0, 1.5, 2.0]}
        
        # Store results
        result = {
            'config_name': config['name'],
            'mechanisms': ','.join(config['mechanisms']),
            'fvg_timeframes': ','.join(config['fvg_timeframes']) if config['fvg_timeframes'] else 'None',
            'fib_type': config['fib_type'],
            'min_confluence': config['min_confluence'],
            **metrics,
            **mfe_reach
        }
        results.append(result)
    
    # Create comparison DataFrame
    df_results = pd.DataFrame(results)
    
    # Save comparison
    comparison_path = Path('docs/strategies/initial_balance_break/mechanism_evaluation/comparison.csv')
    df_results.to_csv(comparison_path, index=False)
    
    # Print comparison
    print(f"\n{'='*100}")
    print(f"MECHANISM EVALUATION RESULTS")
    print(f"{'='*100}\n")
    
    # Key metrics to display
    display_cols = [
        'config_name', 'total_trades', 'win_rate', 'profit_factor',
        'total_return_pct', '0.5R', '1.0R'
    ]
    
    print(df_results[display_cols].to_string(index=False))
    
    # Find best performers
    print(f"\n{'='*100}")
    print(f"BEST PERFORMERS")
    print(f"{'='*100}\n")
    
    if len(df_results) > 0:
        best_pf = df_results.loc[df_results['profit_factor'].idxmax()]
        best_wr = df_results.loc[df_results['win_rate'].idxmax()]
        best_return = df_results.loc[df_results['total_return_pct'].idxmax()]
        best_mfe = df_results.loc[df_results['1.0R'].idxmax()]
        
        print(f"Best Profit Factor: {best_pf['config_name']}")
        print(f"  PF: {best_pf['profit_factor']:.2f}, WR: {best_pf['win_rate']:.1f}%, Return: {best_pf['total_return_pct']:.1f}%")
        
        print(f"\nBest Win Rate: {best_wr['config_name']}")
        print(f"  WR: {best_wr['win_rate']:.1f}%, PF: {best_wr['profit_factor']:.2f}, Return: {best_wr['total_return_pct']:.1f}%")
        
        print(f"\nBest Return: {best_return['config_name']}")
        print(f"  Return: {best_return['total_return_pct']:.1f}%, PF: {best_return['profit_factor']:.2f}, WR: {best_return['win_rate']:.1f}%")
        
        print(f"\nBest MFE (1R Reach): {best_mfe['config_name']}")
        print(f"  1R Reach: {best_mfe['1.0R']:.1f}%, PF: {best_mfe['profit_factor']:.2f}, WR: {best_mfe['win_rate']:.1f}%")
    
    print(f"\n✓ Detailed results saved to: {comparison_path}")
    
    return df_results


if __name__ == '__main__':
    # Run comprehensive mechanism evaluation
    results = run_mechanism_evaluation(
        ticker='NQ1',
        start_date='2024-01-01',
        end_date='2025-12-21',
        ib_duration=45
    )
    
    print(f"\n{'='*100}")
    print(f"MECHANISM EVALUATION COMPLETE!")
    print(f"{'='*100}")
