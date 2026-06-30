"""
Count sessions from June 26th backwards to find the start date that produces
exactly N=73 (1100 BO), N=74 (MO Break), N=75 (1800 Break), N=73 (Q1 Break).

June 29th session is NOT included (replay mode — last complete session is Fri June 26).
Also check: Good Friday (April 3) — CME has a shortened session.
Also check: Memorial Day (May 25) and Juneteenth (June 19) — already excluded.
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

# Exclude June 29 and beyond (replay mode — last complete session is June 26)
df_1m = df_1m[df_1m['date'] <= pd.Timestamp('2026-06-26').date()]

# Check holidays
print("=" * 80)
print("HOLIDAY CHECK")
print("=" * 80)
holidays = {
    '2026-04-03': 'Good Friday',
    '2026-05-25': 'Memorial Day',
    '2026-06-19': 'Juneteenth',
}
for date_str, name in holidays.items():
    d = pd.Timestamp(date_str).date()
    day_data = df_1m[df_1m['date'] == d]
    if day_data.empty:
        print(f"  {date_str} ({name}): NO DATA — already excluded")
    else:
        rth = day_data[(day_data['et_hhmm'] >= 930) & (day_data['et_hhmm'] < 1600)]
        print(f"  {date_str} ({name}): {len(day_data)} total bars, {len(rth)} RTH bars")
        if len(rth) > 0:
            print(f"    RTH hours: {rth['et_hhmm'].min()} - {rth['et_hhmm'].max()}")
            # Good Friday is a shortened session — CME closes at 12:00 CT = 13:00 ET
            if name == 'Good Friday':
                print(f"    Good Friday has data! CME shortened session (closes 1:00 PM ET)")
print()

# Build sessions for each preset, counting from June 26 backwards
PRESETS = {
    '1100 BO':     {'or_start': 1100, 'or_end': 1115, 'cutoff': 1230, 'days': '23456', 'target_n': 73},
    'MO Break':    {'or_start': 930,  'or_end': 935,  'cutoff': 1200, 'days': '23456', 'target_n': 74},
    '1800 Break':  {'or_start': 1800, 'or_end': 1815, 'cutoff': 300,  'days': '12345', 'target_n': 75},
    'Q1 Break':    {'or_start': 600,  'or_end': 830,  'cutoff': 1200, 'days': '23456', 'target_n': 73},
}

def days_to_python_dow(days_str):
    pine_to_python = {1: 6, 2: 0, 3: 1, 4: 2, 5: 3, 6: 4, 7: 5}
    return set(pine_to_python[int(d)] for d in days_str)

dow_names = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']

print("=" * 80)
print("SESSION COUNTS (excluding June 29, ending at June 26)")
print("=" * 80)

for name, cfg in PRESETS.items():
    valid_dows = days_to_python_dow(cfg['days'])
    crosses_midnight = cfg['cutoff'] < cfg['or_start']
    
    # Build all valid session dates
    all_dates = sorted(df_1m['date'].unique())
    session_dates = []
    
    for date in all_dates:
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
            session_dates.append((date, bo_side))
        else:
            # 1800 Break — crosses midnight
            if date.weekday() not in valid_dows:
                continue
            next_date = date + pd.Timedelta(days=1)
            day_1m = df_1m[df_1m['date'] == date]
            next_day_1m = df_1m[df_1m['date'] == next_date]
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
            session_dates.append((date, bo_side))
    
    bo_sessions = [(d, s) for d, s in session_dates if s != 0]
    no_bo_count = len(session_dates) - len(bo_sessions)
    
    print(f"\n  {name} (target N={cfg['target_n']}):")
    print(f"    Total dates with OR: {len(session_dates)}")
    print(f"    With breakout: {len(bo_sessions)}")
    print(f"    No breakout: {no_bo_count}")
    if bo_sessions:
        print(f"    First: {bo_sessions[0][0]} ({dow_names[bo_sessions[0][0].weekday()]})")
        print(f"    Last:  {bo_sessions[-1][0]} ({dow_names[bo_sessions[-1][0].weekday()]})")
    
    # Now try excluding holidays to see if we get the target
    # Test: exclude Good Friday (April 3)
    bo_no_gf = [(d, s) for d, s in bo_sessions if d != pd.Timestamp('2026-04-03').date()]
    print(f"    Excluding Good Friday: {len(bo_no_gf)}")
    
    # Test: exclude Memorial Day (May 25) — already excluded in previous scripts
    bo_no_mem = [(d, s) for d, s in bo_sessions if d != pd.Timestamp('2026-05-25').date()]
    print(f"    Excluding Memorial Day: {len(bo_no_mem)}")
    
    # Test: exclude Juneteenth (June 19) — already excluded
    bo_no_jun = [(d, s) for d, s in bo_sessions if d != pd.Timestamp('2026-06-19').date()]
    print(f"    Excluding Juneteenth: {len(bo_no_jun)}")
    
    # Test: exclude all 3 holidays
    bo_no_holidays = [(d, s) for d, s in bo_sessions 
                      if d not in [pd.Timestamp('2026-04-03').date(),
                                   pd.Timestamp('2026-05-25').date(),
                                   pd.Timestamp('2026-06-19').date()]]
    print(f"    Excluding ALL 3 holidays: {len(bo_no_holidays)}")
    
    # Check if Good Friday has a valid session for this preset
    gf = [s for d, s in bo_sessions if d == pd.Timestamp('2026-04-03').date()]
    if gf:
        print(f"    Good Friday session: side={'bull' if gf[0]==1 else 'bear' if gf[0]==-1 else 'none'}")
    else:
        print(f"    Good Friday: no breakout session for {name}")

# Now check: does Good Friday have a valid 1100 BO session?
print("\n" + "=" * 80)
print("GOOD FRIDAY (April 3) DETAILED CHECK")
print("=" * 80)
gf_date = pd.Timestamp('2026-04-03').date()
gf_data = df_1m[df_1m['date'] == gf_date]
if not gf_data.empty:
    print(f"  Total bars: {len(gf_data)}")
    print(f"  ET hours: {gf_data['et_hhmm'].min()} - {gf_data['et_hhmm'].max()}")
    
    # Check 1100 BO OR window
    or_bars = gf_data[(gf_data['et_hhmm'] >= 1100) & (gf_data['et_hhmm'] < 1115)]
    print(f"\n  1100 BO OR window (1100-1115): {len(or_bars)} bars")
    if not or_bars.empty:
        print(f"    OR High: {or_bars['high'].max()}, OR Low: {or_bars['low'].min()}")
        data = gf_data[(gf_data['et_hhmm'] >= 1115) & (gf_data['et_hhmm'] < 1230)]
        print(f"    Data window (1115-1230): {len(data)} bars")
        if not data.empty:
            or_h = or_bars['high'].max()
            or_l = or_bars['low'].min()
            bo = 0
            for idx, row in data.iterrows():
                if row['close'] > or_h:
                    bo = 1; break
                elif row['close'] < or_l:
                    bo = -1; break
            print(f"    Breakout: {'bull' if bo==1 else 'bear' if bo==-1 else 'none'}")
    
    # Check MO Break OR window
    or_bars_mo = gf_data[(gf_data['et_hhmm'] >= 930) & (gf_data['et_hhmm'] < 935)]
    print(f"\n  MO Break OR window (0930-0935): {len(or_bars_mo)} bars")
    if not or_bars_mo.empty:
        data_mo = gf_data[(gf_data['et_hhmm'] >= 935) & (gf_data['et_hhmm'] < 1200)]
        print(f"    Data window (0935-1200): {len(data_mo)} bars")
    
    # Check Q1 Break OR window
    or_bars_q1 = gf_data[(gf_data['et_hhmm'] >= 600) & (gf_data['et_hhmm'] < 830)]
    print(f"\n  Q1 Break OR window (0600-0830): {len(or_bars_q1)} bars")
    if not or_bars_q1.empty:
        data_q1 = gf_data[(gf_data['et_hhmm'] >= 830) & (gf_data['et_hhmm'] < 1200)]
        print(f"    Data window (0830-1200): {len(data_q1)} bars")
    
    # Check 1800 Break (previous day = April 2, Thursday)
    print(f"\n  1800 Break: April 2 (Thu) 1800 → April 3 (Fri) 0300")
    apr2 = df_1m[df_1m['date'] == pd.Timestamp('2026-04-02').date()]
    or_bars_18 = apr2[(apr2['et_hhmm'] >= 1800) & (apr2['et_hhmm'] < 1815)]
    print(f"    OR window (Apr 2, 1800-1815): {len(or_bars_18)} bars")
    if not or_bars_18.empty:
        data_18 = pd.concat([apr2[apr2['et_hhmm'] >= 1815], gf_data[gf_data['et_hhmm'] < 300]])
        print(f"    Data window (1815-0300): {len(data_18)} bars")

# Summary: what start date gives exactly the target N for each preset?
print("\n" + "=" * 80)
print("FINDING THE CORRECT START DATE (ending June 26, excluding holidays)")
print("=" * 80)

holidays_set = {pd.Timestamp('2026-04-03').date(),
                pd.Timestamp('2026-05-25').date(),
                pd.Timestamp('2026-06-19').date()}

for name, cfg in PRESETS.items():
    valid_dows = days_to_python_dow(cfg['days'])
    crosses_midnight = cfg['cutoff'] < cfg['or_start']
    target = cfg['target_n']
    
    # Build all valid BO sessions (excluding holidays)
    all_dates = sorted(df_1m['date'].unique())
    bo_dates = []
    
    for date in all_dates:
        if date in holidays_set:
            continue
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
            if bo_side != 0:
                bo_dates.append(date)
        else:
            if date.weekday() not in valid_dows:
                continue
            next_date = date + pd.Timedelta(days=1)
            day_1m = df_1m[df_1m['date'] == date]
            next_day_1m = df_1m[df_1m['date'] == next_date]
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
            if bo_side != 0:
                bo_dates.append(date)
    
    # Count from the end (June 26) backwards
    bo_dates_sorted = sorted(bo_dates, reverse=True)
    
    print(f"\n  {name} (target N={target}):")
    print(f"    Total BO sessions (excl holidays, ≤ June 26): {len(bo_dates)}")
    
    if len(bo_dates) >= target:
        start_date = bo_dates_sorted[target - 1]  # The Nth from the end
        print(f"    {target}th from end: {start_date} ({dow_names[start_date.weekday()]})")
        print(f"    Date range: {bo_dates_sorted[-1]} to {bo_dates_sorted[0]}")
        
        # Verify count
        count_from_start = sum(1 for d in bo_dates if d >= start_date)
        print(f"    Sessions from {start_date} to {bo_dates_sorted[0]}: {count_from_start}")
    else:
        print(f"    NOT ENOUGH SESSIONS! Only {len(bo_dates)} available")
    
    # Also try INCLUDING Good Friday to see if it matches
    bo_dates_with_gf = []
    for date in all_dates:
        if date == pd.Timestamp('2026-05-25').date() or date == pd.Timestamp('2026-06-19').date():
            continue  # Still exclude Memorial Day and Juneteenth
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
            if bo_side != 0:
                bo_dates_with_gf.append(date)
        else:
            if date.weekday() not in valid_dows:
                continue
            next_date = date + pd.Timedelta(days=1)
            day_1m = df_1m[df_1m['date'] == date]
            next_day_1m = df_1m[df_1m['date'] == next_date]
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
            if bo_side != 0:
                bo_dates_with_gf.append(date)
    
    print(f"    Including Good Friday (excl Mem/Jun only): {len(bo_dates_with_gf)}")
    if len(bo_dates_with_gf) == target:
        print(f"    ✅ MATCHES TARGET with Good Friday included!")