import pandas as pd
import numpy as np
import pytz

# Load NQ data
df = pd.read_parquet('data/live/live_storage_-NQ.parquet')
df['datetime'] = pd.to_datetime(df['timestamp'], utc=True)
df = df.set_index('datetime')

# Exclude Memorial Day and Juneteenth to align with TradingView chart sessions
df_all = df[(df.index >= '2026-03-16') & (df.index < '2026-06-30')]
df_all = df_all[~df_all.index.strftime('%Y-%m-%d').isin(['2026-05-25', '2026-06-19'])]

et = pytz.timezone('America/New_York')
df_all['et_time'] = df_all.index.tz_convert(et)
df_all['et_hhmm'] = df_all['et_time'].dt.hour * 100 + df_all['et_time'].dt.minute
df_all['date'] = df_all['et_time'].dt.date

def evaluate_preset_5m(name, or_start, or_end, cutoff, days_list):
    sessions = []
    
    for date, day_1m in df_all.groupby('date'):
        dow = day_1m.index[0].tz_convert(et).dayofweek + 2
        if dow == 8: dow = 1
        if dow not in days_list:
            continue
            
        # Resample to 5m for breakout and evaluation
        # Note: We must align 5m bars on left-closed intervals (e.g. 0930-0935 is labeled 0930)
        day_5m = day_1m.resample('5min', label='left', closed='left').agg({
            'open':'first', 'high':'max', 'low':'min', 'close':'last', 'volume':'sum'
        }).dropna()
        day_5m['et_time'] = day_5m.index.tz_convert(et)
        day_5m['et_hhmm'] = day_5m['et_time'].dt.hour * 100 + day_5m['et_time'].dt.minute
        
        # Build OR using 1m data (since the LTF loop builds OR on 1m bars in TV)
        crosses_midnight = cutoff < or_start
        
        if crosses_midnight:
            next_date = date + pd.Timedelta(days=1)
            day_next_1m = df_all[df_all['date'] == next_date]
            or_bars = day_1m[(day_1m['et_hhmm'] >= or_start) & (day_1m['et_hhmm'] < or_end)]
            
            # 5m data bars for breakout and post-breakout evaluation
            day_next_5m = day_next_1m.resample('5min', label='left', closed='left').agg({
                'open':'first', 'high':'max', 'low':'min', 'close':'last', 'volume':'sum'
            }).dropna()
            day_next_5m['et_time'] = day_next_5m.index.tz_convert(et)
            day_next_5m['et_hhmm'] = day_next_5m['et_time'].dt.hour * 100 + day_next_5m['et_time'].dt.minute
            
            data_current = day_5m[day_5m['et_hhmm'] >= or_end]
            data_next = day_next_5m[day_next_5m['et_hhmm'] < cutoff]
            data_5m = pd.concat([data_current, data_next])
        else:
            or_bars = day_1m[(day_1m['et_hhmm'] >= or_start) & (day_1m['et_hhmm'] < or_end)]
            data_5m = day_5m[(day_5m['et_hhmm'] >= or_end) & (day_5m['et_hhmm'] < cutoff)]
            
        if or_bars.empty or data_5m.empty:
            continue
            
        or_high = or_bars['high'].max()
        or_low = or_bars['low'].min()
        
        # Find breakout using 5-minute bars close!
        bo_side = 0
        bo_px = None
        bo_idx = None
        for idx, row in data_5m.iterrows():
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
                
        if bo_side == 0:
            continue
            
        close_at_cutoff = data_5m['close'].iloc[-1]
        crossed_opp = (bo_side == 1 and close_at_cutoff < or_low) or (bo_side == -1 and close_at_cutoff > or_high)
        
        sessions.append({
            'date': date,
            'side': bo_side,
            'crossed_opp': crossed_opp
        })

    # Win if NOT crossed opposite at cutoff
    wins = sum(not s['crossed_opp'] for s in sessions)
    fails = sum(s['crossed_opp'] for s in sessions)
    
    return wins, fails, len(sessions)

presets = [
    # (name, start, end, cutoff, days_list, Gunship expected wins/losses (excluding today))
    # 1100 BO (excluding today) is 55 wins / 18 fails (total 73)
    ("1100 BO", 1100, 1115, 1230, [2, 3, 4, 5, 6], 55, 18),
    # MO Break (excluding today) is 32 wins / 41 fails (total 73)
    ("MO Break", 930, 935, 1200, [2, 3, 4, 5, 6], 32, 41),
    # Magic Hour (excluding today) is 55 wins / 5 fails (total 60)
    ("Magic Hour", 300, 700, 830, [2, 3, 4, 5, 6], 55, 5),
    # 1800 Break (excluding today) is 35 wins / 39 fails (total 74)
    ("1800 Break", 1800, 1815, 300, [1, 2, 3, 4, 5], 35, 39)
]

print("======================================================================")
print("5-MINUTE CHART TIME FRAME BREAKOUT DETECTION & EVALUATION")
print("======================================================================")
print(f"{'Preset Name':<15} {'N (Total)':<10} {'Wins (Python)':<15} {'Fails (Python)':<15} {'Wins (TV)':<10} {'Fails (TV)':<10} {'Diff':<8}")
print("======================================================================")

for name, start, end, cutoff, days, exp_w, exp_f in presets:
    w, f, total = evaluate_preset_5m(name, start, end, cutoff, days)
    print(f"{name:<15} {total:<10} {w:<15} {f:<15} {exp_w:<10} {exp_f:<10} {f - exp_f:<8}")
