"""
Compare MFE calculation approaches:
1. Current: Extensions from OR High/Low
2. Reference: Extensions from Close +/- 0.01%
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import time
import pytz

DATA_PATH = 'data/NQ1_1m.parquet'
START_DATE = '2025-12-21'
END_DATE = '2026-01-14'
CUTOFF_TIME = time(12, 0)
OR_TIME = time(9, 30)
NY_TZ = pytz.timezone('America/New_York')

df = pd.read_parquet(DATA_PATH)
df.index = pd.to_datetime(df.index)
if df.index.tz is None:
    df.index = df.index.tz_localize('UTC').tz_convert(NY_TZ)
else:
    df.index = df.index.tz_convert(NY_TZ)
df = df[(df.index.date >= pd.to_datetime(START_DATE).date()) & 
        (df.index.date <= pd.to_datetime(END_DATE).date())]

results = []

for date in df.index.normalize().unique():
    day_data = df[df.index.normalize() == date]
    or_bars = day_data[day_data.index.time == OR_TIME]
    if len(or_bars) == 0:
        continue
    or_bar = or_bars.iloc[0]
    
    # Current approach: OR High/Low
    or_high = or_bar['high']
    or_low = or_bar['low']
    
    # Reference approach: Close +/- 0.01%
    or_close = or_bar['close']
    ref_bull_base = or_close * (1 + 0.0001)  # +0.01%
    ref_bear_base = or_close * (1 - 0.0001)  # -0.01%
    
    session = day_data[(day_data.index.time > OR_TIME) & (day_data.index.time <= CUTOFF_TIME)]
    
    max_bull_current = 0.0
    max_bear_current = 0.0
    max_bull_ref = 0.0
    max_bear_ref = 0.0
    
    for idx, row in session.iterrows():
        # Current: from OR High/Low
        if row['high'] > or_high:
            ext = (row['high'] - or_high) / or_high * 100
            max_bull_current = max(max_bull_current, ext)
        if row['low'] < or_low:
            ext = (or_low - row['low']) / or_low * 100
            max_bear_current = max(max_bear_current, ext)
        
        # Reference: from Close +/- 0.01%
        if row['high'] > ref_bull_base:
            ext = (row['high'] - ref_bull_base) / or_close * 100
            max_bull_ref = max(max_bull_ref, ext)
        if row['low'] < ref_bear_base:
            ext = (ref_bear_base - row['low']) / or_close * 100
            max_bear_ref = max(max_bear_ref, ext)
    
    results.append({
        'date': str(date.date()),
        'or_high': or_high,
        'or_low': or_low,
        'or_close': or_close,
        'bull_current': max_bull_current,
        'bear_current': max_bear_current,
        'bull_ref': max_bull_ref,
        'bear_ref': max_bear_ref
    })

print('Comparison: Current (OR High/Low) vs Reference (Close +/- 0.01%)')
print('='*80)
for r in results:
    print(f"{r['date']}: Bull {r['bull_current']:.3f}% vs {r['bull_ref']:.3f}% -- Bear {r['bear_current']:.3f}% vs {r['bear_ref']:.3f}%")

# Summary stats
bull_cur = [r['bull_current'] for r in results if r['bull_current'] > 0]
bear_cur = [r['bear_current'] for r in results if r['bear_current'] > 0]
bull_ref = [r['bull_ref'] for r in results if r['bull_ref'] > 0]
bear_ref = [r['bear_ref'] for r in results if r['bear_ref'] > 0]

print()
print('Summary Stats:')
print(f'Current Bull: Mean={np.mean(bull_cur):.4f}%, Med={np.median(bull_cur):.4f}%')
print(f'Ref Bull:     Mean={np.mean(bull_ref):.4f}%, Med={np.median(bull_ref):.4f}%')
print(f'Current Bear: Mean={np.mean(bear_cur):.4f}%, Med={np.median(bear_cur):.4f}%')
print(f'Ref Bear:     Mean={np.mean(bear_ref):.4f}%, Med={np.median(bear_ref):.4f}%')
