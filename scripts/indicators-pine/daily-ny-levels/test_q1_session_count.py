"""
Debug Q1 Break session count discrepancy.
Gunship shows N=71, but our Python model counts 73-74 sessions.
Investigate which dates are missing.
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

# Q1 Break config: days=23456, start_date=2026-03-12
# But Gunship shows N=71 as of today (2026-06-29)
# Today is Monday Jun 29
valid_dows = days_to_python_dow('23456')
start_date = pd.Timestamp('2026-03-12').date()
today = pd.Timestamp('2026-06-29').date()

all_weekdays = []
for date in pd.date_range(start_date, today).date:
    if date.weekday() < 5 and date not in HOLIDAYS:
        all_weekdays.append(date)

print(f"Total weekdays Mar 12 - Jun 29 (excluding holidays): {len(all_weekdays)}")
print(f"Gunship shows N=71 for Q1 Break")
print(f"Our Python model counts 73-74 sessions")
print(f"Difference: {len(all_weekdays) - 71} sessions")

# Check which dates have data for Q1 Break (0600-1200 ET)
q1_dates_with_data = []
for date in all_weekdays:
    session_5m = df_5m[(df_5m['date'] == date) & (df_5m['et_hhmm'] >= 600) & (df_5m['et_hhmm'] < 1200)]
    if not session_5m.empty:
        q1_dates_with_data.append(date)

print(f"\nDates with Q1 Break data: {len(q1_dates_with_data)}")
print(f"Missing dates (in weekday list but no data):")
for d in all_weekdays:
    if d not in q1_dates_with_data:
        print(f"  {d}")

# Check which dates have breakout
print(f"\nChecking breakouts for each Q1 Break date...")
breakout_dates = []
no_breakout_dates = []
for date in q1_dates_with_data:
    session_5m = df_5m[(df_5m['date'] == date) & (df_5m['et_hhmm'] >= 600) & (df_5m['et_hhmm'] < 1200)]
    or_bars = session_5m[(session_5m['et_hhmm'] >= 600) & (session_5m['et_hhmm'] < 830)]
    if or_bars.empty:
        no_breakout_dates.append((date, 'NO OR BARS'))
        continue
    or_high = or_bars['high'].max()
    or_low = or_bars['low'].min()
    
    data_5m = session_5m[session_5m['et_hhmm'] >= 830]
    if data_5m.empty:
        no_breakout_dates.append((date, 'NO DATA BARS'))
        continue
    
    bo = False
    for idx, row in data_5m.iterrows():
        if row['high'] > or_high or row['low'] < or_low:
            bo = True
            breakout_dates.append(date)
            break
    if not bo:
        no_breakout_dates.append((date, 'NO BREAKOUT'))

print(f"Dates with breakout: {len(breakout_dates)}")
print(f"Dates without breakout: {len(no_breakout_dates)}")
for d, reason in no_breakout_dates:
    print(f"  {d}: {reason}")

print(f"\nFirst 10 breakout dates: {breakout_dates[:10]}")
print(f"Last 10 breakout dates: {breakout_dates[-10:]}")