import pandas as pd
import numpy as np
import pytz

df = pd.read_parquet('data/live/live_storage_-NQ.parquet')
df['datetime'] = pd.to_datetime(df['timestamp'], utc=True)
df = df.set_index('datetime')

# Load all data starting from Dec 30, 2025
df_all = df[(df.index >= '2025-12-30') & (df.index < '2026-06-30')]
df_all = df_all[~df_all.index.strftime('%Y-%m-%d').isin(['2026-05-25', '2026-06-19'])]

et = pytz.timezone('America/New_York')
df_all['et_time'] = df_all.index.tz_convert(et)
df_all['et_hhmm'] = df_all['et_time'].dt.hour * 100 + df_all['et_time'].dt.minute
df_all['date'] = df_all['et_time'].dt.date

def test_preset_rules(name, or_start, or_end, cutoff, days_list, exp_w, exp_f, use_5m=False):
    sessions = []
    
    for date, day_1m in df_all.groupby('date'):
        # Filter to study period
        if date < pd.Timestamp('2026-03-16').date():
            continue
            
        dow = day_1m.index[0].tz_convert(et).dayofweek + 2
        if dow == 8: dow = 1
        if dow not in days_list: continue
        
        # Determine timeframe
        if use_5m:
            day_data = day_1m.resample('5min', label='left', closed='left').agg({
                'open':'first', 'high':'max', 'low':'min', 'close':'last', 'volume':'sum'
            }).dropna()
            day_data['et_time'] = day_data.index.tz_convert(et)
            day_data['et_hhmm'] = day_data['et_time'].dt.hour * 100 + day_data['et_time'].dt.minute
        else:
            day_data = day_1m.copy()
            
        crosses_midnight = cutoff < or_start
        
        if crosses_midnight:
            next_date = date + pd.Timedelta(days=1)
            day_next = df_all[df_all['date'] == next_date]
            if use_5m:
                day_next_5m = day_next.resample('5min', label='left', closed='left').agg({
                    'open':'first', 'high':'max', 'low':'min', 'close':'last', 'volume':'sum'
                }).dropna()
                day_next_5m['et_time'] = day_next_5m.index.tz_convert(et)
                day_next_5m['et_hhmm'] = day_next_5m['et_time'].dt.hour * 100 + day_next_5m['et_time'].dt.minute
                
                or_bars = day_data[(day_data['et_hhmm'] >= or_start) & (day_data['et_hhmm'] < or_end)]
                data_current = day_data[day_data['et_hhmm'] >= or_end]
                data_next = day_next_5m[day_next_5m['et_hhmm'] < cutoff]
                data_window = pd.concat([data_current, data_next])
            else:
                or_bars = day_data[(day_data['et_hhmm'] >= or_start) & (day_data['et_hhmm'] < or_end)]
                data_current = day_data[day_data['et_hhmm'] >= or_end]
                data_next = day_next[day_next['et_hhmm'] < cutoff]
                data_window = pd.concat([data_current, data_next])
        else:
            or_bars = day_data[(day_data['et_hhmm'] >= or_start) & (day_data['et_hhmm'] < or_end)]
            data_window = day_data[(day_data['et_hhmm'] >= or_end) & (day_data['et_hhmm'] < cutoff)]
            
        if or_bars.empty or data_window.empty: continue
        
        or_high = or_bars['high'].max()
        or_low = or_bars['low'].min()
        
        # Breakout check
        bo_side = 0
        bo_px = None
        bo_idx = None
        for idx, row in data_window.iterrows():
            if row['close'] > or_high:
                bo_side = 1
                bo_px = row['close']
                bo_idx = idx
                break
            elif row['close'] < or_low:
                bo_side = -1
                bo_px = row['close']
                bo_idx = idx
                break
                
        if bo_side == 0: continue
        post_bo = data_window.loc[bo_idx:]
        close_at_cutoff = data_window['close'].iloc[-1]
        
        # Rule 1: Cutoff Close beyond opposite OR boundary
        fail_r1 = (bo_side == 1 and close_at_cutoff < or_low) or (bo_side == -1 and close_at_cutoff > or_high)
        
        # Rule 2: Intraday Close beyond opposite OR boundary
        fail_r2 = (bo_side == 1 and post_bo['close'].min() < or_low) or (bo_side == -1 and post_bo['close'].max() > or_high)
        
        # Rule 3: Intraday Touch (high/low) of opposite OR boundary
        fail_r3 = (bo_side == 1 and post_bo['low'].min() < or_low) or (bo_side == -1 and post_bo['high'].max() > or_high)
        
        sessions.append({
            'date': date,
            'fail_r1': fail_r1,
            'fail_r2': fail_r2,
            'fail_r3': fail_r3
        })
        
    df_sess = pd.DataFrame(sessions)
    if df_sess.empty:
        return 0, 0, 0, 0
        
    n = len(df_sess)
    r1_fails = df_sess['fail_r1'].sum()
    r2_fails = df_sess['fail_r2'].sum()
    r3_fails = df_sess['fail_r3'].sum()
    
    return n, r1_fails, r2_fails, r3_fails

presets = [
    ("1100 BO", 1100, 1115, 1230, [2, 3, 4, 5, 6], 55, 18),
    ("MO Break", 930, 935, 1200, [2, 3, 4, 5, 6], 32, 41),
    ("Magic Hour", 300, 700, 830, [2, 3, 4, 5, 6], 54, 6),
    ("1800 Break", 1800, 1815, 300, [1, 2, 3, 4, 5], 35, 39)
]

for tf_name, use_5m in [("1-Minute", False), ("5-Minute", True)]:
    print(f"\n=======================================================")
    print(f"EVALUATING RULES ON {tf_name.upper()} TIMEFRAME")
    print(f"=======================================================")
    print(f"{'Preset':<15} {'N':<5} {'TV Fails':<10} {'R1 (Close)':<12} {'R2 (Intra-C)':<15} {'R3 (Touch)':<12}")
    print(f"-------------------------------------------------------")
    for name, start, end, cutoff, days, exp_w, exp_f in presets:
        n, r1, r2, r3 = test_preset_rules(name, start, end, cutoff, days, exp_w, exp_f, use_5m=use_5m)
        print(f"{name:<15} {n:<5} {exp_f:<10} {r1:<12} {r2:<15} {r3:<12}")
