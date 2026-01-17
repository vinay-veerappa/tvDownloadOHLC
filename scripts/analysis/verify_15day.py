"""
Verify MFE > MAE filtering on initial 15-day test period
"""

import pandas as pd
import numpy as np
from datetime import time

df = pd.read_parquet('data/NQ1_1m.parquet')
df.index = pd.to_datetime(df.index)
if df.index.tz is None:
    df.index = df.index.tz_localize('UTC').tz_convert('America/New_York')
else:
    df.index = df.index.tz_convert('America/New_York')

REF_TIME, CUTOFF_TIME = time(9, 31), time(12, 0)
START_DATE = pd.to_datetime('2025-12-21')
END_DATE = pd.to_datetime('2026-01-14')

sub = df[(df.index.date >= START_DATE.date()) & (df.index.date <= END_DATE.date())]

long_mfe = []
short_mfe = []
daily_breakdown = []

for date in sub.index.normalize().unique():
    day = sub[sub.index.normalize() == date]
    ref = day[day.index.time == REF_TIME]
    if len(ref) == 0: continue
    
    rc = ref.iloc[0]['close']
    bull_ref = rc * 1.0001
    bear_ref = rc * 0.9999
    
    sess = day[(day.index.time > REF_TIME) & (day.index.time <= CUTOFF_TIME)]
    
    max_bull_mfe = 0
    max_bear_mae = 0
    for _, r in sess.iterrows():
        if r['high'] > bull_ref:
            max_bull_mfe = max(max_bull_mfe, (r['high'] - bull_ref) / rc * 100)
        if r['low'] < bear_ref:
            max_bear_mae = max(max_bear_mae, (bear_ref - r['low']) / rc * 100)
    
    direction = 'LONG' if max_bull_mfe > max_bear_mae else 'SHORT'
    mfe = max_bull_mfe if direction == 'LONG' else max_bear_mae
    
    daily_breakdown.append({
        'date': str(date.date()),
        'ref': rc,
        'bull_mfe': max_bull_mfe,
        'bear_mae': max_bear_mae,
        'direction': direction,
        'winning_mfe': mfe
    })
    
    if max_bull_mfe > max_bear_mae and max_bull_mfe > 0:
        long_mfe.append(max_bull_mfe)
    elif max_bear_mae > max_bull_mfe and max_bear_mae > 0:
        short_mfe.append(max_bear_mae)

print('=== INITIAL 15-DAY TEST PERIOD ===')
print(f'Date range: {START_DATE.date()} to {END_DATE.date()}')
print(f'Trading days: {len(daily_breakdown)}')
print(f'Long favorable (MFE > MAE): {len(long_mfe)} days')
print(f'Short favorable (MAE > MFE): {len(short_mfe)} days')
print()
print('DAILY BREAKDOWN:')
print('Date       | Ref Close | Bull MFE | Bear MAE | Direction')
print('-' * 60)
for d in daily_breakdown:
    print(f"{d['date']} | {d['ref']:.2f} | {d['bull_mfe']:.3f}%   | {d['bear_mae']:.3f}%   | {d['direction']}")

print()
if long_mfe:
    print(f'Long MFE values: {[round(x,3) for x in long_mfe]}')
    print(f'Long mean: {np.mean(long_mfe):.3f}%, median: {np.median(long_mfe):.3f}%')
if short_mfe:
    print(f'Short MFE values: {[round(x,3) for x in short_mfe]}')
    print(f'Short mean: {np.mean(short_mfe):.3f}%, median: {np.median(short_mfe):.3f}%')
