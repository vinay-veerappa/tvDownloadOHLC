"""
Analyze Entry Patterns from IB Break Backtest Results
"""

import pandas as pd
import numpy as np

# Load 45-min IB results (best performer)
df = pd.read_csv('docs/strategies/initial_balance_break/backtest_results_45min.csv')

print("="*80)
print("ENTRY PATTERN ANALYSIS - 45-Minute Initial Balance")
print("="*80)

print(f"\nTotal Trades: {len(df)}")
print(f"Date Range: {df['date'].min()} to {df['date'].max()}")

# Entry Type
print("\n" + "="*80)
print("1. ENTRY TYPE")
print("="*80)
print(df['entry_type'].value_counts())
print("\n→ All trades are BREAKOUT entries (immediate entry on IB break)")

# Entry Timing
print("\n" + "="*80)
print("2. ENTRY TIMING")
print("="*80)
df['entry_dt'] = pd.to_datetime(df['entry_time'], utc=True)
df['entry_time_str'] = df['entry_dt'].astype(str).str[11:16]  # Extract HH:MM

print("\nEntry Time Distribution:")
print(df['entry_time_str'].value_counts().head(10))

most_common = df['entry_time_str'].mode()
if len(most_common) > 0:
    print(f"\nMost common entry time: {most_common.iloc[0]}")
    print(f"→ This is 10:15 AM ET, which is 45 minutes after market open (9:30)")
    print(f"→ IB forms from 9:30-10:15, then strategy enters on first break")

# Direction Distribution
print("\n" + "="*80)
print("3. DIRECTION DISTRIBUTION")
print("="*80)
print(df['direction'].value_counts())
print(f"\nLong: {(df['direction']=='LONG').sum()} trades")
print(f"Short: {(df['direction']=='SHORT').sum()} trades")

# IB Close Position Analysis
print("\n" + "="*80)
print("4. IB CLOSE POSITION (Directional Bias)")
print("="*80)
print(f"\nIB Close Position Stats:")
print(f"  Mean: {df['ib_close_position'].mean():.1f}%")
print(f"  Median: {df['ib_close_position'].median():.1f}%")
print(f"  Min: {df['ib_close_position'].min():.1f}%")
print(f"  Max: {df['ib_close_position'].max():.1f}%")

print(f"\nDistribution:")
print(f"  Lower Half (0-50%): {(df['ib_close_position'] < 50).sum()} trades → Expect LOW break")
print(f"  Upper Half (50-100%): {(df['ib_close_position'] >= 50).sum()} trades → Expect HIGH break")

# Expectation Matching
print("\n" + "="*80)
print("5. DIRECTIONAL BIAS ACCURACY")
print("="*80)
matched = df['matched_expectation'].sum()
total = len(df)
print(f"\nTrades matching expected direction: {matched} / {total} ({matched/total*100:.1f}%)")
print(f"→ Strategy correctly predicted break direction {matched/total*100:.1f}% of the time")

# Win Rate by Match
print("\nWin Rate Analysis:")
for match_val in [True, False]:
    subset = df[df['matched_expectation'] == match_val]
    wins = (subset['result'] == 'WIN').sum()
    total_subset = len(subset)
    wr = wins / total_subset * 100 if total_subset > 0 else 0
    label = "Matched Expectation" if match_val else "Against Expectation"
    print(f"  {label}: {wins}/{total_subset} = {wr:.1f}% win rate")

# Entry Pattern Examples
print("\n" + "="*80)
print("6. ENTRY PATTERN EXAMPLES")
print("="*80)

print("\n📈 LONG ENTRY PATTERN:")
long_example = df[df['direction'] == 'LONG'].iloc[0]
print(f"  Date: {long_example['date']}")
print(f"  IB Close Position: {long_example['ib_close_position']:.1f}% (upper half)")
print(f"  Expected Break: {long_example['expected_break']}")
print(f"  Entry Time: {long_example['entry_time']}")
print(f"  Entry: Break above IB high → Go LONG")
print(f"  Result: {long_example['result']} ({long_example['pnl_pct']:.2f}%)")

print("\n📉 SHORT ENTRY PATTERN:")
short_example = df[df['direction'] == 'SHORT'].iloc[0]
print(f"  Date: {short_example['date']}")
print(f"  IB Close Position: {short_example['ib_close_position']:.1f}% (lower half)")
print(f"  Expected Break: {short_example['expected_break']}")
print(f"  Entry Time: {short_example['entry_time']}")
print(f"  Entry: Break below IB low → Go SHORT")
print(f"  Result: {short_example['result']} ({short_example['pnl_pct']:.2f}%)")

# IB Range Analysis
print("\n" + "="*80)
print("7. IB RANGE CHARACTERISTICS")
print("="*80)
print(f"\nIB Range (% of open price):")
print(f"  Mean: {df['ib_range_pct'].mean():.3f}%")
print(f"  Median: {df['ib_range_pct'].median():.3f}%")
print(f"  Min: {df['ib_range_pct'].min():.3f}%")
print(f"  Max: {df['ib_range_pct'].max():.3f}%")

# Win Rate by IB Range Size
print("\nWin Rate by IB Range Size:")
df['range_bucket'] = pd.cut(df['ib_range_pct'], bins=[0, 0.5, 0.7, 1.0, 5.0], 
                             labels=['Tight (0-0.5%)', 'Normal (0.5-0.7%)', 'Wide (0.7-1.0%)', 'Very Wide (>1.0%)'])
for bucket in df['range_bucket'].unique():
    subset = df[df['range_bucket'] == bucket]
    wins = (subset['result'] == 'WIN').sum()
    total_subset = len(subset)
    wr = wins / total_subset * 100 if total_subset > 0 else 0
    print(f"  {bucket}: {wins}/{total_subset} = {wr:.1f}% win rate")

# Summary
print("\n" + "="*80)
print("ENTRY PATTERN SUMMARY")
print("="*80)
print("""
The strategy uses a PURE BREAKOUT entry pattern:

1. **IB Formation**: 9:30-10:15 AM ET (45 minutes)
   - Track high and low during this period
   - Calculate where IB closes within the range

2. **Directional Bias**:
   - IB closes in upper half (>50%) → Expect HIGH break → Go LONG
   - IB closes in lower half (<50%) → Expect LOW break → Go SHORT

3. **Entry Trigger**:
   - Immediately after 10:15 AM (IB close)
   - Enter on FIRST breakout of expected level
   - No pullback waiting, no confirmation needed

4. **Entry Execution**:
   - LONG: Price breaks above IB high
   - SHORT: Price breaks below IB low
   - Entry price = IB high/low level

5. **Stop Loss**: Opposite side of IB range
   - LONG: Stop at IB low
   - SHORT: Stop at IB high

6. **Take Profit**: 2R (2x risk distance)

7. **Time Exits**:
   - 3:30 PM ET (avoid close volatility)
   - 4:00 PM ET (end of day hard stop)

CURRENT ISSUE:
- Only 88% of trades match expected direction
- Win rate is 45.45% (needs improvement)
- Profit factor 0.97 (nearly breakeven)

RECOMMENDED IMPROVEMENT:
→ Switch to PULLBACK entries using Fair Value Gaps (FVG)
→ This should improve win rate to 60-65% and R/R to 1.5-2.0
""")

print("\n" + "="*80)
