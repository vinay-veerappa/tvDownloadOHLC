"""
Compare MFE calculation: Python vs PineScript
Uses the same logic as the PineScript indicator:
- Reference: 09:31 candle close ±0.01%
- Bull MFE: Max extension ABOVE bull_ref (close + 0.01%)
- Bear MFE: Max extension BELOW bear_ref (close - 0.01%)
- Commits BOTH directions at 12:00 PM cutoff
"""

import pandas as pd
import numpy as np
from datetime import time
import pytz

DATA_PATH = 'data/NQ1_1m.parquet'
START_DATE = '2025-12-21'
END_DATE = '2026-01-14'
CUTOFF_TIME = time(12, 0)
REF_TIME = time(9, 31)  # 09:31 candle close as reference
NY_TZ = pytz.timezone('America/New_York')

# Load and filter data
df = pd.read_parquet(DATA_PATH)
df.index = pd.to_datetime(df.index)
if df.index.tz is None:
    df.index = df.index.tz_localize('UTC').tz_convert(NY_TZ)
else:
    df.index = df.index.tz_convert(NY_TZ)
df = df[(df.index.date >= pd.to_datetime(START_DATE).date()) & 
        (df.index.date <= pd.to_datetime(END_DATE).date())]

# Track MFE using 09:31 close ±0.01%
bull_mfe_history = []
bear_mfe_history = []
daily_details = []

for date in df.index.normalize().unique():
    day_data = df[df.index.normalize() == date]
    
    # Get 09:31 candle close as reference
    ref_bars = day_data[day_data.index.time == REF_TIME]
    if len(ref_bars) == 0:
        continue
    
    ref_close = ref_bars.iloc[0]['close']
    bull_ref = ref_close * 1.0001  # +0.01%
    bear_ref = ref_close * 0.9999  # -0.01%
    
    # Get session data (after 09:31, before cutoff)
    session = day_data[(day_data.index.time > REF_TIME) & (day_data.index.time <= CUTOFF_TIME)]
    
    if len(session) == 0:
        continue
    
    # Track max MFE in each direction
    daily_max_bull = 0.0
    daily_max_bear = 0.0
    
    for idx, row in session.iterrows():
        # Bull MFE: extension above bull_ref
        if row['high'] > bull_ref:
            ext = (row['high'] - bull_ref) / ref_close * 100
            daily_max_bull = max(daily_max_bull, ext)
        
        # Bear MFE: extension below bear_ref
        if row['low'] < bear_ref:
            ext = (bear_ref - row['low']) / ref_close * 100
            daily_max_bear = max(daily_max_bear, ext)
    
    # Commit BOTH directions if they have values
    if daily_max_bull > 0:
        bull_mfe_history.append(daily_max_bull)
    if daily_max_bear > 0:
        bear_mfe_history.append(daily_max_bear)
    
    daily_details.append({
        'date': str(date.date()),
        'ref_close': ref_close,
        'bull_ref': bull_ref,
        'bear_ref': bear_ref,
        'bull_mfe': daily_max_bull,
        'bear_mfe': daily_max_bear
    })

# Output in format matching PineScript log
print("=== MFE HISTORY DUMP (Python) ===")
print(f"Total Bull Days: {len(bull_mfe_history)}, Total Bear Days: {len(bear_mfe_history)}")
print()

if bull_mfe_history:
    print(f"Bull MFE: [{', '.join([f'{x:.3f}' for x in bull_mfe_history])}]")
    print(f"Bull P20={np.percentile(bull_mfe_history, 20):.4f}, P50={np.percentile(bull_mfe_history, 50):.4f}, P80={np.percentile(bull_mfe_history, 80):.4f}")
    print()

if bear_mfe_history:
    print(f"Bear MFE: [{', '.join([f'{x:.3f}' for x in bear_mfe_history])}]")
    print(f"Bear P20={np.percentile(bear_mfe_history, 20):.4f}, P50={np.percentile(bear_mfe_history, 50):.4f}, P80={np.percentile(bear_mfe_history, 80):.4f}")
    print()

print("=== END DUMP ===")
print()

# Detailed daily breakdown
print("=== DAILY BREAKDOWN ===")
print("Date       | Ref Close | Bull Ref  | Bear Ref  | Bull MFE | Bear MFE")
print("-" * 75)
for d in daily_details:
    print(f"{d['date']} | {d['ref_close']:.2f} | {d['bull_ref']:.2f} | {d['bear_ref']:.2f} | {d['bull_mfe']:.3f}%  | {d['bear_mfe']:.3f}%")
