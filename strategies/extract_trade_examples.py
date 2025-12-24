"""
Extract example trades for visualization

Finds good winning and losing trade examples from Fib 38.2% results
"""

import pandas as pd
import numpy as np

# Load Fib 38.2% results
df = pd.read_csv('docs/strategies/initial_balance_break/mechanism_evaluation/Fib_38.2_Only.csv')

print("="*80)
print("FIB 38.2% TRADE EXAMPLES")
print("="*80)

# Get winning trades
winners = df[df['result'] == 'WIN'].copy()
losers = df[df['result'] == 'LOSS'].copy()

print(f"\nTotal Winners: {len(winners)}")
print(f"Total Losers: {len(losers)}")

# Sort winners by PnL
winners = winners.sort_values('pnl_pct', ascending=False)

# Sort losers by PnL (most negative first)
losers = losers.sort_values('pnl_pct', ascending=True)

print("\n" + "="*80)
print("TOP 3 WINNING TRADES")
print("="*80)

for i, (idx, trade) in enumerate(winners.head(3).iterrows(), 1):
    print(f"\n--- Winner #{i} ---")
    print(f"Date: {trade['date']}")
    print(f"Direction: {trade['direction']}")
    print(f"Entry Time: {trade['entry_time']}")
    print(f"Entry Price: ${trade['entry_price']:,.2f}")
    print(f"Exit Time: {trade['exit_time']}")
    print(f"Exit Price: ${trade.get('exit_price', 'N/A')}")
    print(f"PnL: {trade['pnl_pct']:.3f}%")
    print(f"MAE: {trade['mae_pct']:.3f}%")
    print(f"MFE: {trade['mfe_pct']:.3f}%")
    print(f"Tiers Hit: {trade['tiers_hit']}")
    print(f"Exit Reason: {trade['exit_reason']}")
    print(f"IB Range: {trade['ib_range_pct']:.3f}%")
    print(f"IB Close Position: {trade['ib_close_position']:.1f}%")
    print(f"Expected Break: {trade['expected_break']}")
    print(f"Matched Expectation: {trade['matched_expectation']}")

print("\n" + "="*80)
print("TOP 3 LOSING TRADES")
print("="*80)

for i, (idx, trade) in enumerate(losers.head(3).iterrows(), 1):
    print(f"\n--- Loser #{i} ---")
    print(f"Date: {trade['date']}")
    print(f"Direction: {trade['direction']}")
    print(f"Entry Time: {trade['entry_time']}")
    print(f"Entry Price: ${trade['entry_price']:,.2f}")
    print(f"Exit Time: {trade['exit_time']}")
    print(f"Exit Price: ${trade.get('exit_price', 'N/A')}")
    print(f"PnL: {trade['pnl_pct']:.3f}%")
    print(f"MAE: {trade['mae_pct']:.3f}%")
    print(f"MFE: {trade['mfe_pct']:.3f}%")
    print(f"Tiers Hit: {trade['tiers_hit']}")
    print(f"Exit Reason: {trade['exit_reason']}")
    print(f"IB Range: {trade['ib_range_pct']:.3f}%")
    print(f"IB Close Position: {trade['ib_close_position']:.1f}%")
    print(f"Expected Break: {trade['expected_break']}")
    print(f"Matched Expectation: {trade['matched_expectation']}")

# Save examples to CSV for charting
winners.head(3).to_csv('docs/strategies/initial_balance_break/winning_trade_examples.csv', index=False)
losers.head(3).to_csv('docs/strategies/initial_balance_break/losing_trade_examples.csv', index=False)

print("\n" + "="*80)
print("Examples saved for charting")
print("="*80)
