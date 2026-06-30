"""
Check the exact date range of sessions for each preset.
The user is in replay mode — the last complete session is Fri June 26.
The 5000-bar limit on the 5-min chart determines how far back the Gunship can see.

Key questions:
1. What is the FIRST session date in our Python data for each preset?
2. Does Good Friday (April 3, 2026) have data? (CME closed)
3. Are there any other data gaps?
4. How many bars does each session use on the 5-min chart?
"""
import pandas as pd
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

# Check the full date range
print("=" * 80)
print("DATA RANGE CHECK")
print("=" * 80)
print(f"  Parquet data: {df_1m.index.min()} to {df_1m.index.max()}")
print(f"  Total 1-min bars: {len(df_1m)}")
print()

# Check for data gaps — days with no data between March 16 and June 28
print("=" * 80)
print("DATA GAP CHECK (Mon-Fri days with no data)")
print("=" * 80)
all_dates = pd.date_range('2026-03-16', '2026-06-28', freq='D')
data_dates = set(df_1m['date'].unique())
dow_names = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']

for d in all_dates:
    if d.weekday() >= 5:  # Skip weekends
        continue
    if d.date() in data_dates:
        # Check if there's data during RTH (930-1600)
        day_data = df_1m[df_1m['date'] == d.date()]
        rth = day_data[(day_data['et_hhmm'] >= 930) & (day_data['et_hhmm'] < 1600)]
        if rth.empty:
            print(f"  {d.date()} ({dow_names[d.weekday()]}) — NO RTH DATA (holiday or gap)")
        # Check for specific holidays
        if d.date() in [pd.Timestamp('2026-04-03').date()]:
            print(f"  {d.date()} ({dow_names[d.weekday()]}) — GOOD FRIDAY: {len(rth)} RTH bars")
        if d.date() in [pd.Timestamp('2026-05-25').date()]:
            print(f"  {d.date()} ({dow_names[d.weekday()]}) — MEMORIAL DAY: {len(rth)} RTH bars")
        if d.date() in [pd.Timestamp('2026-06-19').date()]:
            print(f"  {d.date()} ({dow_names[d.weekday()]}) — JUNETEENTH: {len(rth)} RTH bars")
    else:
        print(f"  {d.date()} ({dow_names[d.weekday()]}) — NO DATA AT ALL")

print()

# Check April 3 specifically (Good Friday)
print("=" * 80)
print("GOOD FRIDAY CHECK (April 3, 2026)")
print("=" * 80)
apr3 = df_1m[df_1m['date'] == pd.Timestamp('2026-04-03').date()]
if apr3.empty:
    print("  No data for April 3 — CME was closed (Good Friday)")
else:
    print(f"  April 3 has {len(apr3)} bars")
    print(f"  ET hours: {apr3['et_hhmm'].min()} - {apr3['et_hhmm'].max()}")
print()

# Check the first and last session dates for each preset
print("=" * 80)
print("FIRST/LAST SESSION DATES PER PRESET")
print("=" * 80)

PRESETS = {
    '1100 BO':     {'or_start': 1100, 'or_end': 1115, 'cutoff': 1230, 'days': '23456'},
    'MO Break':    {'or_start': 930,  'or_end': 935,  'cutoff': 1200, 'days': '23456'},
    '1800 Break':  {'or_start': 1800, 'or_end': 1815, 'cutoff': 300,  'days': '12345'},
    'Q1 Break':    {'or_start': 600,  'or_end': 830,  'cutoff': 1200, 'days': '23456'},
}

def days_to_python_dow(days_str):
    pine_to_python = {1: 6, 2: 0, 3: 1, 4: 2, 5: 3, 6: 4, 7: 5}
    return set(pine_to_python[int(d)] for d in days_str)

for name, cfg in PRESETS.items():
    valid_dows = days_to_python_dow(cfg['days'])
    crosses_midnight = cfg['cutoff'] < cfg['or_start']
    
    session_dates = []
    for date in sorted(data_dates):
        if not crosses_midnight:
            if date.weekday() not in valid_dows:
                continue
            day_1m = df_1m[df_1m['date'] == date]
            or_bars = day_1m[(day_1m['et_hhmm'] >= cfg['or_start']) & (day_1m['et_hhmm'] < cfg['or_end'])]
            if or_bars.empty:
                continue
            data_1m = day_1m[(day_1m['et_hhmm'] >= cfg['or_end']) & (day_1m['et_hhmm'] < cfg['cutoff'])]
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
            if bo_side == 0:
                session_dates.append((date, 'no_bo'))
            else:
                session_dates.append((date, 'bull' if bo_side == 1 else 'bear'))
        else:
            # 1800 Break — crosses midnight
            if date.weekday() not in valid_dows:
                continue
            next_date = date + pd.Timedelta(days=1)
            day_1m = df_1m[df_1m['date'] == date]
            next_day_1m = df_1m[df_1m['date'] == next_date] if next_date in data_dates else pd.DataFrame()
            or_bars = day_1m[(day_1m['et_hhmm'] >= cfg['or_start']) & (day_1m['et_hhmm'] < cfg['or_end'])]
            if or_bars.empty:
                continue
            data_1m = pd.concat([day_1m[day_1m['et_hhmm'] >= cfg['or_end']],
                                 next_day_1m[next_day_1m['et_hhmm'] < cfg['cutoff']]])
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
            if bo_side == 0:
                session_dates.append((date, 'no_bo'))
            else:
                session_dates.append((date, 'bull' if bo_side == 1 else 'bear'))
    
    bo_sessions = [(d, s) for d, s in session_dates if s != 'no_bo']
    no_bo_sessions = [(d, s) for d, s in session_dates if s == 'no_bo']
    
    print(f"\n  {name}:")
    print(f"    Total dates with OR: {len(session_dates)}")
    print(f"    With breakout: {len(bo_sessions)}")
    print(f"    No breakout: {len(no_bo_sessions)}")
    if bo_sessions:
        print(f"    First session: {bo_sessions[0][0]} ({dow_names[bo_sessions[0][0].weekday()]})")
        print(f"    Last session:  {bo_sessions[-1][0]} ({dow_names[bo_sessions[-1][0].weekday()]})")
    if no_bo_sessions:
        print(f"    No-breakout dates: {[str(d) for d, _ in no_bo_sessions]}")

# Count 5-min bars per session to estimate 5000-bar limit
print("\n" + "=" * 80)
print("5-MIN BAR COUNT PER SESSION (for 5000-bar limit estimation)")
print("=" * 80)

df_5m = df_1m.resample('5min', label='left', closed='left').agg(
    {'open':'first', 'high':'max', 'low':'min', 'close':'last', 'volume':'sum'}).dropna()
df_5m['et_time'] = df_5m.index.tz_convert(et)
df_5m['et_hhmm'] = df_5m['et_time'].dt.hour * 100 + df_5m['et_time'].dt.minute
df_5m['date'] = df_5m['et_time'].dt.date

# Count total 5-min bars per day (full CME session)
daily_bars = df_5m.groupby('date').size()
print(f"  Average 5-min bars per day: {daily_bars.mean():.1f}")
print(f"  Min: {daily_bars.min()}, Max: {daily_bars.max()}")
print(f"  5000 bars / {daily_bars.mean():.1f} bars per day = {5000 / daily_bars.mean():.1f} days")
print()

# Count bars in the 1100 BO data window only (11:15-12:30 = 75 min = 15 bars)
print(f"  1100 BO data window (11:15-12:30): ~15 bars per session")
print(f"  But the CHART shows ALL bars, not just the data window")
print(f"  The 5000-bar limit applies to the ENTIRE chart, not per session")
print()

# Check: how many 5-min bars from the first to last session date?
for name in ['1100 BO', 'Q1 Break']:
    cfg = PRESETS[name]
    valid_dows = days_to_python_dow(cfg['days'])
    dates = [d for d in sorted(data_dates) if d.weekday() in valid_dows]
    if dates:
        first_date = dates[0]
        last_date = dates[-1]
        bars_in_range = df_5m[(df_5m['date'] >= first_date) & (df_5m['date'] <= last_date)]
        print(f"  {name}: {first_date} to {last_date}")
        print(f"    Total 5-min bars in range: {len(bars_in_range)}")
        print(f"    Trading days: {len(dates)}")
        print(f"    Bars per trading day: {len(bars_in_range) / len(dates):.1f}")

# Check if the Gunship might start from a different date
print("\n" + "=" * 80)
print("REPLAY MODE: SESSION COUNT FROM JUNE 26 BACKWARDS")
print("=" * 80)
print("  If the replay is at June 29 (Mon) and the last complete session is June 26 (Fri):")
print()

# Count Mon-Fri sessions from June 26 backwards
mon_fri_dates = []
for d in pd.date_range('2026-03-01', '2026-06-26', freq='D'):
    if d.weekday() < 5:  # Mon-Fri
        if d.date() in data_dates:
            day_data = df_1m[df_1m['date'] == d.date()]
            rth = day_data[(day_data['et_hhmm'] >= 930) & (day_data['et_hhmm'] < 1600)]
            if not rth.empty:
                mon_fri_dates.append(d.date())

print(f"  Mon-Fri dates with RTH data (March 1 to June 26): {len(mon_fri_dates)}")
if mon_fri_dates:
    print(f"  First: {mon_fri_dates[0]}, Last: {mon_fri_dates[-1]}")

# Try different start dates to find exactly 73
for start in ['2026-03-01', '2026-03-02', '2026-03-03', '2026-03-04', '2026-03-05', '2026-03-06',
              '2026-03-09', '2026-03-10', '2026-03-11', '2026-03-12', '2026-03-13', '2026-03-16']:
    count = 0
    for d in pd.date_range(start, '2026-06-26', freq='D'):
        if d.weekday() < 5:
            if d.date() in data_dates:
                day_data = df_1m[df_1m['date'] == d.date()]
                rth = day_data[(day_data['et_hhmm'] >= 930) & (day_data['et_hhmm'] < 1600)]
                if not rth.empty:
                    count += 1
    if count in [72, 73, 74, 75]:
        print(f"  Start={start}: {count} Mon-Fri sessions with RTH data → {'✅ MATCH 73' if count == 73 else ''}")