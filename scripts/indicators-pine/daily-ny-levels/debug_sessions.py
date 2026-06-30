"""
Debug session counts for each preset.
Also test: stop-loss ONLY (no R1) as the fail rule.
"""
import pandas as pd
import numpy as np
import pytz

df_1m = pd.read_parquet('data/live/live_storage_-NQ.parquet')
df_1m['datetime'] = pd.to_datetime(df_1m['timestamp'], utc=True)
df_1m = df_1m.set_index('datetime')
df_1m = df_1m[['open', 'high', 'low', 'close', 'volume']].copy()

df_1m = df_1m[(df_1m.index >= '2026-03-16') & (df_1m.index < '2026-06-29')]
df_1m = df_1m[~df_1m.index.strftime('%Y-%m-%d').isin(['2026-05-25', '2026-06-19'])]

et = pytz.timezone('America/New_York')
df_1m['et_time'] = df_1m.index.tz_convert(et)
df_1m['et_hhmm'] = df_1m['et_time'].dt.hour * 100 + df_1m['et_time'].dt.minute
df_1m['et_dow'] = df_1m['et_time'].dt.dayofweek
df_1m['date'] = df_1m['et_time'].dt.date

df_5m = df_1m.resample('5min', label='left', closed='left').agg(
    {'open':'first', 'high':'max', 'low':'min', 'close':'last', 'volume':'sum'}).dropna()
df_5m['et_time'] = df_5m.index.tz_convert(et)
df_5m['et_hhmm'] = df_5m['et_time'].dt.hour * 100 + df_5m['et_time'].dt.minute
df_5m['et_dow'] = df_5m['et_time'].dt.dayofweek
df_5m['date'] = df_5m['et_time'].dt.date

def p_nearest(series, p):
    if len(series) == 0: return np.nan
    return np.percentile(series, p, method='nearest')

# Debug: list all unique dates for each preset's OR window
print("=" * 80)
print("DEBUG: Session dates for each preset")
print("=" * 80)

# 1800 Break: OR=1800-1815, cutoff=0300 next day, days=12345 (Sun-Thu)
print("\n1800 Break (OR=1800-1815, cutoff=0300 next day, days=Sun-Thu):")
dates_1800 = []
for date, day_1m in df_1m.groupby('date'):
    # Check if this date's DOW is Sun(6), Mon(0), Tue(1), Wed(2), or Thu(3)
    if date.weekday() not in [6, 0, 1, 2, 3]:
        continue
    or_bars = day_1m[(day_1m['et_hhmm'] >= 1800) & (day_1m['et_hhmm'] < 1815)]
    if or_bars.empty:
        continue
    next_date = date + pd.Timedelta(days=1)
    next_day_1m = df_1m[df_1m['date'] == next_date]
    data_1m = pd.concat([day_1m[day_1m['et_hhmm'] >= 1815], 
                         next_day_1m[next_day_1m['et_hhmm'] < 300]])
    if data_1m.empty:
        continue
    or_high = or_bars['high'].max()
    or_low = or_bars['low'].min()
    # Check for breakout
    bo_side = 0
    for idx, row in data_1m.iterrows():
        if row['close'] > or_high:
            bo_side = 1; break
        elif row['close'] < or_low:
            bo_side = -1; break
    dow_name = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][date.weekday()]
    dates_1800.append(f"  {date} ({dow_name}) BO={'bull' if bo_side==1 else 'bear' if bo_side==-1 else 'none'}")

print(f"  Total: {len(dates_1800)} sessions")
for d in dates_1800:
    print(d)

# MO Break: OR=0930-0935, cutoff=1200, days=23456 (Mon-Fri)
print("\nMO Break (OR=0930-0935, cutoff=1200, days=Mon-Fri):")
dates_mo = []
for date, day_1m in df_1m.groupby('date'):
    if date.weekday() not in [0, 1, 2, 3, 4]:
        continue
    or_bars = day_1m[(day_1m['et_hhmm'] >= 930) & (day_1m['et_hhmm'] < 935)]
    if or_bars.empty:
        continue
    data_1m = day_1m[(day_1m['et_hhmm'] >= 935) & (day_1m['et_hhmm'] < 1200)]
    if data_1m.empty:
        continue
    or_high = or_bars['high'].max()
    or_low = or_bars['low'].min()
    bo_side = 0
    for idx, row in data_1m.iterrows():
        if row['close'] > or_high:
            bo_side = 1; break
        elif row['close'] < or_low:
            bo_side = -1; break
    dow_name = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][date.weekday()]
    dates_mo.append(f"  {date} ({dow_name}) BO={'bull' if bo_side==1 else 'bear' if bo_side==-1 else 'none'}")

print(f"  Total: {len(dates_mo)} sessions")
for d in dates_mo:
    print(d)

# Magic Hour: OR=0300-0700, cutoff=0830, days=23456 (Mon-Fri)
print("\nMagic Hour (OR=0300-0700, cutoff=0830, days=Mon-Fri):")
dates_mh = []
for date, day_1m in df_1m.groupby('date'):
    if date.weekday() not in [0, 1, 2, 3, 4]:
        continue
    or_bars = day_1m[(day_1m['et_hhmm'] >= 300) & (day_1m['et_hhmm'] < 700)]
    if or_bars.empty:
        continue
    data_1m = day_1m[(day_1m['et_hhmm'] >= 700) & (day_1m['et_hhmm'] < 830)]
    if data_1m.empty:
        continue
    or_high = or_bars['high'].max()
    or_low = or_bars['low'].min()
    bo_side = 0
    for idx, row in data_1m.iterrows():
        if row['close'] > or_high:
            bo_side = 1; break
        elif row['close'] < or_low:
            bo_side = -1; break
    dow_name = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][date.weekday()]
    dates_mh.append(f"  {date} ({dow_name}) BO={'bull' if bo_side==1 else 'bear' if bo_side==-1 else 'none'}")

print(f"  Total: {len(dates_mh)} sessions")
for d in dates_mh:
    print(d)

# 1100 BO: OR=1100-1115, cutoff=1230, days=23456 (Mon-Fri)
print("\n1100 BO (OR=1100-1115, cutoff=1230, days=Mon-Fri):")
dates_1100 = []
for date, day_1m in df_1m.groupby('date'):
    if date.weekday() not in [0, 1, 2, 3, 4]:
        continue
    or_bars = day_1m[(day_1m['et_hhmm'] >= 1100) & (day_1m['et_hhmm'] < 1115)]
    if or_bars.empty:
        continue
    data_1m = day_1m[(day_1m['et_hhmm'] >= 1115) & (day_1m['et_hhmm'] < 1230)]
    if data_1m.empty:
        continue
    or_high = or_bars['high'].max()
    or_low = or_bars['low'].min()
    bo_side = 0
    for idx, row in data_1m.iterrows():
        if row['close'] > or_high:
            bo_side = 1; break
        elif row['close'] < or_low:
            bo_side = -1; break
    dow_name = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][date.weekday()]
    dates_1100.append(f"  {date} ({dow_name}) BO={'bull' if bo_side==1 else 'bear' if bo_side==-1 else 'none'}")

print(f"  Total: {len(dates_1100)} sessions")
for d in dates_1100:
    print(d)