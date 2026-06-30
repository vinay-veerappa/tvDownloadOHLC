"""
Compare 1m vs 5m breakout detection for 1100 BO to find the missing session.
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

OR_START = 1100; OR_END = 1115; CUTOFF = 1230
DAYS = '23456'
pine_to_python = {1: 6, 2: 0, 3: 1, 4: 2, 5: 3, 6: 4, 7: 5}
valid_dows = set(pine_to_python[int(d)] for d in DAYS)
start_date = pd.Timestamp('2026-03-13').date()

def detect_breakouts(tf_name, data_df):
    sessions = []
    for date in sorted(data_df['date'].unique()):
        if date < start_date: continue
        if date in HOLIDAYS: continue
        if date.weekday() not in valid_dows: continue
        
        day_df = data_df[data_df['date'] == date]
        or_bars = day_df[(day_df['et_hhmm'] >= OR_START) & (day_df['et_hhmm'] < OR_END)]
        if or_bars.empty: continue
        or_high = or_bars['high'].max()
        or_low = or_bars['low'].min()
        
        data = day_df[day_df['et_hhmm'] >= OR_END]
        if data.empty: continue
        
        bo_side = 0; bo_px = None; bo_time = None
        for idx, row in data.iterrows():
            if row['close'] > or_high:
                bo_side = 1; bo_px = row['close']; bo_time = idx; break
            elif row['close'] < or_low:
                bo_side = -1; bo_px = row['close']; bo_time = idx; break
        
        sessions.append({
            'date': date, 'tf': tf_name, 'side': bo_side, 'bo_px': bo_px,
            'or_high': or_high, 'or_low': or_low
        })
    return pd.DataFrame(sessions)

sessions_1m = detect_breakouts('1m', df_1m)
sessions_5m = detect_breakouts('5m', df_5m)

print(f"1m breakout sessions: {len(sessions_1m)}")
print(f"5m breakout sessions: {len(sessions_5m)}")

# Find dates in 1m but not 5m
only_1m = set(sessions_1m['date']) - set(sessions_5m['date'])
only_5m = set(sessions_5m['date']) - set(sessions_1m['date'])

print(f"\nDates with 1m breakout but no 5m breakout: {only_1m}")
print(f"Dates with 5m breakout but no 1m breakout: {only_5m}")

if only_1m:
    for d in sorted(only_1m):
        row = sessions_1m[sessions_1m['date'] == d].iloc[0]
        print(f"\n  {d}: side={row['side']}, bo_px={row['bo_px']}, or_h={row['or_high']}, or_l={row['or_low']}")
        # Show 5m bars for this date
        day_5m = df_5m[df_5m['date'] == d]
        data_5m = day_5m[day_5m['et_hhmm'] >= OR_END]
        print(f"  5m bars after OR:")
        for idx, r in data_5m.iterrows():
            print(f"    {idx} hhmm={r['et_hhmm']} close={r['close']} high={r['high']} low={r['low']}")

# Show side-by-side comparison
print("\n" + "=" * 100)
print("SIDE-BY-SIDE COMPARISON")
print("=" * 100)
all_dates = sorted(set(sessions_1m['date']) | set(sessions_5m['date']))
for d in all_dates:
    r1 = sessions_1m[sessions_1m['date'] == d]
    r5 = sessions_5m[sessions_5m['date'] == d]
    s1 = f"{r1.iloc[0]['side']} @ {r1.iloc[0]['bo_px']}" if len(r1) > 0 else "NO BO"
    s5 = f"{r5.iloc[0]['side']} @ {r5.iloc[0]['bo_px']}" if len(r5) > 0 else "NO BO"
    if s1 != s5:
        print(f"{d}: 1m={s1} | 5m={s5}  *** DIFF")
