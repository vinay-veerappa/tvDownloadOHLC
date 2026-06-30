"""
Debug which 1100 BO session has no 5m breakout.
"""
import pandas as pd
import numpy as np
import pytz

df_1m = pd.read_parquet('data/live/live_storage_-NQ.parquet')
df_1m['datetime'] = pd.to_datetime(df_1m['timestamp'], utc=True)
df_1m = df_1m.set_index('datetime')
df_1m = df_1m[['open', 'high', 'low', 'close', 'volume']].copy()

et = pytz.timezone('America/New_York')
df_1m['et_time'] = df_1m.index.tz_convert(et)
df_1m['et_hhmm'] = df_1m['et_time'].dt.hour * 100 + df_1m['et_time'].dt.minute
df_1m['et_dow'] = df_1m['et_time'].dt.dayofweek
df_1m['date'] = df_1m['et_time'].dt.date

df_1m = df_1m[df_1m['date'] <= pd.Timestamp('2026-06-26').date()]
HOLIDAYS = {pd.Timestamp('2026-04-03').date(), pd.Timestamp('2026-05-25').date(), pd.Timestamp('2026-06-19').date()}
df_1m = df_1m[~df_1m['date'].isin(HOLIDAYS)]
df_1m = df_1m[df_1m['date'] >= pd.Timestamp('2026-03-12').date()]

df_5m = df_1m.resample('5min', label='left', closed='left').agg(
    {'open':'first', 'high':'max', 'low':'min', 'close':'last', 'volume':'sum'}).dropna()
df_5m['et_time'] = df_5m.index.tz_convert(et)
df_5m['et_hhmm'] = df_5m['et_time'].dt.hour * 100 + df_5m['et_time'].dt.minute
df_5m['et_dow'] = df_5m['et_time'].dt.dayofweek
df_5m['date'] = df_5m['et_time'].dt.date

def days_to_python_dow(days_str):
    pine_to_python = {1: 6, 2: 0, 3: 1, 4: 2, 5: 3, 6: 4, 7: 5}
    return set(pine_to_python[int(d)] for d in days_str)

PRESETS = {
    '1100 BO':     {'or_start': 1100, 'or_end': 1115, 'cutoff': 1230, 'days': '23456',
                    'crosses_midnight': False, 'start_date': '2026-03-13'},
}

cfg = PRESETS['1100 BO']
valid_dows = days_to_python_dow(cfg['days'])
start_date = pd.Timestamp(cfg['start_date']).date()

for date in sorted(df_5m['date'].unique()):
    if date < start_date: continue
    if date in HOLIDAYS: continue
    if date.weekday() not in valid_dows: continue
    
    session_5m = df_5m[(df_5m['date'] == date) & (df_5m['et_hhmm'] >= cfg['or_start']) & (df_5m['et_hhmm'] < cfg['cutoff'])]
    if session_5m.empty:
        print(f"{date}: NO 5m bars in session window")
        continue
    
    or_bars = session_5m[(session_5m['et_hhmm'] >= cfg['or_start']) & (session_5m['et_hhmm'] < cfg['or_end'])]
    if or_bars.empty:
        print(f"{date}: NO OR bars")
        continue
    or_high = or_bars['high'].max()
    or_low = or_bars['low'].min()
    
    data_5m = session_5m[session_5m['et_hhmm'] >= cfg['or_end']]
    bo = False
    for idx, row in data_5m.iterrows():
        if row['close'] > or_high or row['close'] < or_low:
            bo = True
            break
    if not bo:
        print(f"{date}: NO BREAKOUT. OR high={or_high:.2f} low={or_low:.2f}")
        print("  Data bars:")
        for idx, row in data_5m.iterrows():
            print(f"    {row['et_hhmm']} O={row['open']:.2f} H={row['high']:.2f} L={row['low']:.2f} C={row['close']:.2f}")
