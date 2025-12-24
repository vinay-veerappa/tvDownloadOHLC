"""
Re-run Fib 38.2% test with IB Opposite stop loss

Compare MAE-optimized stop vs IB opposite stop
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))
sys.path.insert(0, str(Path(__file__).parent))

from enhanced_backtest_engine import EnhancedBacktestEngine
from initial_balance_pullback import IBPullbackStrategy
import pandas as pd

print("="*80)
print("STOP LOSS COMPARISON TEST")
print("="*80)

results = []

# Test 1: IB Opposite Stop (Traditional)
print("\n" + "#"*80)
print("# Test 1: Fib 38.2% + IB OPPOSITE STOP")
print("#"*80 + "\n")

engine1 = EnhancedBacktestEngine(
    ticker='NQ1',
    timeframe='5m',
    start_date='2024-01-01',
    end_date='2025-12-21',
    initial_capital=100000.0,
    commission=2.50,
    slippage_ticks=1
)

strategy1 = IBPullbackStrategy(
    engine=engine1,
    ib_duration_minutes=45,
    pullback_mechanisms=['fibonacci'],
    fvg_timeframes=[],
    fib_entry_type='aggressive',  # 38.2%
    min_confluence_score=1,
    tp_r_multiples=[0.5, 1.0],
    position_tiers=[0.5, 0.5],
    use_optimized_stop=False  # IB OPPOSITE
)

metrics1 = strategy1.run()

output_dir = Path('docs/strategies/initial_balance_break/stop_loss_comparison')
output_dir.mkdir(parents=True, exist_ok=True)

csv1 = output_dir / 'fib382_ib_opposite_stop.csv'
engine1.export_trades_to_csv(str(csv1))

results.append({
    'stop_type': 'IB_Opposite',
    **metrics1
})

# Test 2: MAE-Optimized Stop (Current)
print("\n" + "#"*80)
print("# Test 2: Fib 38.2% + MAE-OPTIMIZED STOP (-0.253%)")
print("#"*80 + "\n")

engine2 = EnhancedBacktestEngine(
    ticker='NQ1',
    timeframe='5m',
    start_date='2024-01-01',
    end_date='2025-12-21',
    initial_capital=100000.0,
    commission=2.50,
    slippage_ticks=1
)

strategy2 = IBPullbackStrategy(
    engine=engine2,
    ib_duration_minutes=45,
    pullback_mechanisms=['fibonacci'],
    fvg_timeframes=[],
    fib_entry_type='aggressive',  # 38.2%
    min_confluence_score=1,
    tp_r_multiples=[0.5, 1.0],
    position_tiers=[0.5, 0.5],
    use_optimized_stop=True  # MAE-OPTIMIZED
)

metrics2 = strategy2.run()

csv2 = output_dir / 'fib382_mae_optimized_stop.csv'
engine2.export_trades_to_csv(str(csv2))

results.append({
    'stop_type': 'MAE_Optimized',
    **metrics2
})

# Comparison
df_results = pd.DataFrame(results)
comparison_csv = output_dir / 'stop_loss_comparison.csv'
df_results.to_csv(comparison_csv, index=False)

print("\n" + "="*80)
print("STOP LOSS COMPARISON RESULTS")
print("="*80 + "\n")

print(df_results[['stop_type', 'total_trades', 'win_rate', 'profit_factor', 
                   'total_return_pct', 'avg_mae', 'avg_mfe']].to_string(index=False))

print("\n" + "="*80)
print("WINNER")
print("="*80)

best = df_results.loc[df_results['total_return_pct'].idxmax()]
print(f"\nBest Stop Loss Method: {best['stop_type']}")
print(f"  Win Rate: {best['win_rate']:.1f}%")
print(f"  Profit Factor: {best['profit_factor']:.2f}")
print(f"  Total Return: {best['total_return_pct']:.1f}%")
print(f"  Avg MAE: {best['avg_mae']:.2f}%")
print(f"  Avg MFE: {best['avg_mfe']:.2f}%")

print(f"\n✓ Results saved to: {comparison_csv}")
print("\n" + "="*80)
