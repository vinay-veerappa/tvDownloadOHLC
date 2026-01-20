"""Check Jan 13 data for extensions near 12:00"""
import pandas as pd
import pytz

df = pd.read_parquet('data/NQ1_1m.parquet')
df.index = pd.to_datetime(df.index)
if df.index.tz is None:
    df.index = df.index.tz_localize('UTC').tz_convert(pytz.timezone('America/New_York'))
else:
    df.index = df.index.tz_convert(pytz.timezone('America/New_York'))

# Filter to Jan 13, 2026
jan13 = df[(df.index.date == pd.to_datetime('2026-01-13').date())]

# Get 09:30 OR
or_bar = jan13[jan13.index.time == pd.to_datetime('09:30').time()].iloc[0]
or_high = or_bar['high']
or_low = or_bar['low']
print(f'OR High: {or_high}, OR Low: {or_low}')

# Show all bars from 11:00 to 12:15
from datetime import time
session = jan13[(jan13.index.time >= time(11, 0)) & 
                (jan13.index.time <= time(12, 10))]

print(f'\nBars from 11:00-12:10 on Jan 13:')
print(f'{"Time":<8} {"High":<12} {"Low":<12} {"ExtAbove%":<12} {"ExtBelow%":<12} {"MinSince930":<12} {"Notes"}')
print("-" * 80)

max_ext_above = 0
max_ext_below = 0
max_time_above = 0
max_time_below = 0

for idx, row in session.iterrows():
    ext_above = (row['high'] - or_high) / or_high * 100
    ext_below = (or_low - row['low']) / or_low * 100
    mins_since_930 = (idx.hour * 60 + idx.minute) - (9 * 60 + 30)
    
    notes = []
    if ext_above > 0:
        notes.append("▲")
        if ext_above > max_ext_above:
            max_ext_above = ext_above
            max_time_above = mins_since_930
            notes.append("NEW MAX ABOVE!")
    if ext_below > 0:
        notes.append("▼")
        if ext_below > max_ext_below:
            max_ext_below = ext_below
            max_time_below = mins_since_930
            notes.append("NEW MAX BELOW!")
    
    print(f'{idx.strftime("%H:%M"):<8} {row["high"]:<12.2f} {row["low"]:<12.2f} {ext_above:<12.4f} {ext_below:<12.4f} {mins_since_930:<12} {" ".join(notes)}')

print("\n" + "=" * 80)
print(f"MAX Extension Above OR: {max_ext_above:.4f}% at minute {max_time_above}")
print(f"MAX Extension Below OR: {max_ext_below:.4f}% at minute {max_time_below}")

# Compare with what we recorded
print("\n" + "=" * 80)
print("What Python script recorded for Jan 13:")
print(f"  mfe_bull: 0.250214% at peak_time_bull: 12")
print(f"  mfe_bear: 0.468556% at peak_time_bear: 79")
