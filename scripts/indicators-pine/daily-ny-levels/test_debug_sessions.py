"""
Debug session counts and date lists for pure 5m model.
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
    'MO Break':    {'or_start': 930,  'or_end': 935,  'cutoff': 1200, 'days': '23456',
                    'crosses_midnight': False, 'start_date': '2026-03-12'},
    '1800 Break':  {'or_start': 1800, 'or_end': 1815, 'cutoff': 300,  'days': '12345',
                    'crosses_midnight': True, 'start_date': '2026-03-12'},
    'Q1 Break':    {'or_start': 600,  'or_end': 830,  'cutoff': 1200, 'days': '23456',
                    'crosses_midnight': False, 'start_date': '2026-03-12'},
}

def get_session_dates(cfg):
    valid_dows = days_to_python_dow(cfg['days'])
    start_date = pd.Timestamp(cfg['start_date']).date()
    dates = []
    for date in sorted(df_5m['date'].unique()):
        if date < start_date: continue
        if date in HOLIDAYS: continue
        if date.weekday() not in valid_dows: continue
        dates.append(date)
    return dates

for name, cfg in PRESETS.items():
    dates = get_session_dates(cfg)
    print(f"\n{name}: {len(dates)} potential session dates")
    print(f"  first={dates[0]} last={dates[-1]}")
    print(f"  dates: {', '.join(str(d) for d in dates[:5])} ... {', '.join(str(d) for d in dates[-5:])}")

# Check all weekdays between Mar 12 and Jun 26
print("\n" + "=" * 100)
print("All weekdays Mar 12 - Jun 26, excluding holidays:")
all_dates = pd.date_range('2026-03-12', '2026-06-26', freq='D').date
for d in all_dates:
    if d.weekday() < 5 and d not in HOLIDAYS:
        pass
print(f"Total weekdays: {sum(1 for d in all_dates if d.weekday() < 5 and d not in HOLIDAYS)}")

# Check which dates each preset includes
print("\n" + "=" * 100)
print("Date inclusion matrix:")
all_unique_dates = sorted(set(d for cfg in PRESETS.values() for d in get_session_dates(cfg)))
print(f"{'Date':<12} {'DOW':<5} {'1100':<6} {'MO':<4} {'1800':<6} {'Q1':<4}")
for d in all_unique_dates:
    dow = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][d.weekday()]
    inc = []
    for name, cfg in PRESETS.items():
        dates = get_session_dates(cfg)
        inc.append('x' if d in dates else '.')
    print(f"{str(d):<12} {dow:<5} {inc[0]:<6} {inc[1]:<4} {inc[2]:<6} {inc[3]:<4}")
