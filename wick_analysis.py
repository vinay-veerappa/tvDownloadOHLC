import pandas as pd
import numpy as np

df = pd.read_parquet('data/derived/macro_records.parquet')

# Filter to zero-minute Judas records
zero_judas = df[(df['judas_inflection_m'] == 0) & 
                (df['judas_classification'].isin(['bullish_judas', 'bearish_judas']))]

print('=' * 80)
print('WICK ANALYSIS: IS 0M TIMING ACTUALLY WICK FORMATION?')
print('=' * 80)

print('\n### BEARISH JUDAS (Low formed at 0m) ###')
print('If bearish, the LOW is the Judas wick, then close > open (reversal)')
bear_zero = zero_judas[zero_judas['judas_classification'] == 'bearish_judas']
print(f'Total: {len(bear_zero)}')

# Calculate wick size relative to range
bear_zero_copy = bear_zero.copy()
bear_zero_copy['range'] = bear_zero_copy['high'] - bear_zero_copy['low']
bear_zero_copy['low_wick_pct'] = (bear_zero_copy['open'] - bear_zero_copy['low']) / bear_zero_copy['range'] * 100
bear_zero_copy['recovery'] = bear_zero_copy['close'] - bear_zero_copy['low']
bear_zero_copy['recovery_pct'] = bear_zero_copy['recovery'] / bear_zero_copy['range'] * 100

print('\nWick Size (as % of macro range):')
print(f'  Mean: {bear_zero_copy["low_wick_pct"].mean():.1f}%')
print(f'  Median: {bear_zero_copy["low_wick_pct"].median():.1f}%')
print(f'  Min: {bear_zero_copy["low_wick_pct"].min():.1f}%')
print(f'  Max: {bear_zero_copy["low_wick_pct"].max():.1f}%')

print('\nRecovery from Low (as % of macro range):')
print(f'  Mean: {bear_zero_copy["recovery_pct"].mean():.1f}%')
print(f'  Median: {bear_zero_copy["recovery_pct"].median():.1f}%')

print('\nDoes price close ABOVE the low wick? (Confirmation of reversal)')
above_low = (bear_zero_copy['close'] > bear_zero_copy['low']).sum()
print(f'  {above_low}/{len(bear_zero_copy)} records ({above_low/len(bear_zero_copy)*100:.1f}%)')

print('\nClose position relative to Open (for bearish reversal):')
above_open = (bear_zero_copy['close'] > bear_zero_copy['open']).sum()
print(f'  Close > Open: {above_open}/{len(bear_zero_copy)} ({above_open/len(bear_zero_copy)*100:.1f}%) ✓ EXPECTED')

print('\n### BULLISH JUDAS (High formed at 0m) ###')
print('If bullish, the HIGH is the Judas wick, then close < open (reversal)')
bull_zero = zero_judas[zero_judas['judas_classification'] == 'bullish_judas']
print(f'Total: {len(bull_zero)}')

bull_zero_copy = bull_zero.copy()
bull_zero_copy['range'] = bull_zero_copy['high'] - bull_zero_copy['low']
bull_zero_copy['high_wick_pct'] = (bull_zero_copy['high'] - bull_zero_copy['open']) / bull_zero_copy['range'] * 100
bull_zero_copy['recovery'] = bull_zero_copy['high'] - bull_zero_copy['close']
bull_zero_copy['recovery_pct'] = bull_zero_copy['recovery'] / bull_zero_copy['range'] * 100

print('\nWick Size (as % of macro range):')
print(f'  Mean: {bull_zero_copy["high_wick_pct"].mean():.1f}%')
print(f'  Median: {bull_zero_copy["high_wick_pct"].median():.1f}%')
print(f'  Min: {bull_zero_copy["high_wick_pct"].min():.1f}%')
print(f'  Max: {bull_zero_copy["high_wick_pct"].max():.1f}%')

print('\nRecovery from High (as % of macro range):')
print(f'  Mean: {bull_zero_copy["recovery_pct"].mean():.1f}%')
print(f'  Median: {bull_zero_copy["recovery_pct"].median():.1f}%')

print('\nDoes price close BELOW the high wick? (Confirmation of reversal)')
below_high = (bull_zero_copy['close'] < bull_zero_copy['high']).sum()
print(f'  {below_high}/{len(bull_zero_copy)} records ({below_high/len(bull_zero_copy)*100:.1f}%)')

print('\nClose position relative to Open (for bullish reversal):')
below_open = (bull_zero_copy['close'] < bull_zero_copy['open']).sum()
print(f'  Close < Open: {below_open}/{len(bull_zero_copy)} ({below_open/len(bull_zero_copy)*100:.1f}%) ✓ EXPECTED')

print('\n' + '=' * 80)
print('INTERPRETATION')
print('=' * 80)
print('\nIf the above percentages are HIGH (>95%), then the 0m clustering confirms:')
print('  → The Judas inflection is a WICK in the first minute')
print('  → Followed by a quick REVERSAL to establish the real direction')
print('  → This is the DEFINITION of a Judas pattern!')
print('\nThis would validate the timing data as correct, not as bugs.')
