import pandas as pd
import numpy as np

df = pd.read_parquet('data/derived/macro_records.parquet')

# Filter to just Judas records with 0m inflection
zero_judas = df[(df['judas_inflection_m'] == 0) & 
                 (df['judas_classification'].isin(['bullish_judas', 'bearish_judas']))]

print('=== ZERO-MINUTE JUDAS TIMING ANALYSIS ===')
print(f'Total zero-minute Judas records: {len(zero_judas)}')

# Check the raw offset values
print('\nHigh Offset at Zero Inflection (for Bullish Judas):')
bull_zero = zero_judas[zero_judas['judas_classification'] == 'bullish_judas']
print(f'  Count: {len(bull_zero)}')
print(f'  Value counts:')
print(bull_zero['high_offset_m'].value_counts().head(10))

print('\nLow Offset at Zero Inflection (for Bearish Judas):')
bear_zero = zero_judas[zero_judas['judas_classification'] == 'bearish_judas']
print(f'  Count: {len(bear_zero)}')
print(f'  Value counts:')
print(bear_zero['low_offset_m'].value_counts().head(10))

# Sample specific records
print('\n=== SAMPLE DETAILS (first 5 zero-minute records) ===')
for i, (idx, row) in enumerate(zero_judas.head(5).iterrows()):
    print(f'\n[{i+1}] {row["trading_date"]} {row["macro_name_raw"]}')
    print(f'    Classification: {row["judas_classification"]}')
    print(f'    High Offset: {row["high_offset_m"]}, Low Offset: {row["low_offset_m"]}')
    print(f'    Extreme Spread: {row["extreme_spread"]}')
    print(f'    Judas Magnitude: {row["judas_magnitude_pct"]:.3f}%')
    print(f'    Real Move Magnitude: {row["real_move_magnitude_pct"]:.3f}%')
    print(f'    Extreme: {row["judas_extreme"]}')
    
# Check if any have justifiably 0m (the first bar hits the extreme)
print('\n=== ANALYSIS: WHY ARE THESE AT 0M? ===')
print('\nThe 0m timing indicates that the Judas inflection (high for bullish, low for bearish)')
print('occurred in the FIRST bar of the macro window (within the first minute).')

print('\nIs this legitimate? Check if high/low values make sense:')
for i, (idx, row) in enumerate(zero_judas.head(3).iterrows()):
    print(f'\n[{i+1}] {row["trading_date"]} {row["macro_name_raw"]} ({row["judas_classification"]})')
    print(f'    Open: {row["open"]}, High: {row["high"]}, Low: {row["low"]}, Close: {row["close"]}')
    if row['judas_classification'] == 'bullish_judas':
        print(f'    HIGH at 0m? High ({row["high"]}) appeared on first bar, then close {row["close"]} < open {row["open"]}')
    else:
        print(f'    LOW at 0m? Low ({row["low"]}) appeared on first bar, then close {row["close"]} >= open {row["open"]}')
