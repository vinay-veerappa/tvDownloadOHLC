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

def evaluate_preset(name, or_start, or_end, cutoff, days_list):
    sessions = []
    
    for date, day_1m in df_all.groupby('date'):
        dow = day_1m.index[0].tz_convert(et).dayofweek + 2
        if dow == 8: dow = 1
        if dow not in days_list:
            continue
            
        rth_1m = day_1m.copy()
        crosses_midnight = cutoff < or_start
        
        if crosses_midnight:
            next_date = date + pd.Timedelta(days=1)
            day_next = df_all[df_all['date'] == next_date]
            or_bars = rth_1m[(rth_1m['et_hhmm'] >= or_start) & (rth_1m['et_hhmm'] < or_end)]
            data_current = rth_1m[rth_1m['et_hhmm'] >= or_end]
            data_next = day_next[day_next['et_hhmm'] < cutoff]
            data_1m = pd.concat([data_current, data_next])
        else:
            or_bars = rth_1m[(rth_1m['et_hhmm'] >= or_start) & (rth_1m['et_hhmm'] < or_end)]
            data_1m = rth_1m[(rth_1m['et_hhmm'] >= or_end) & (rth_1m['et_hhmm'] < cutoff)]
            
        if or_bars.empty or data_1m.empty:
            continue
            
        or_high = or_bars['high'].max()
        or_low = or_bars['low'].min()
        
        # Find breakout
        bo_side = 0
        bo_px = None
        bo_idx = None
        for idx, row in data_1m.iterrows():
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
            
        close_at_cutoff = data_1m['close'].iloc[-1]
        crossed_opp = (bo_side == 1 and close_at_cutoff < or_low) or (bo_side == -1 and close_at_cutoff > or_high)
        
        sessions.append({
            'date': date,
            'side': bo_side,
            'crossed_opp': crossed_opp
        })

    # In this method: Win if NOT crossed opposite at cutoff
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
print("NO-STOP BOUNDARY CROSS CLASSIFICATION VALIDATION (Method 4 Style)")
print("======================================================================")
print(f"{'Preset Name':<15} {'N (Total)':<10} {'Wins (Python)':<15} {'Fails (Python)':<15} {'Wins (TV)':<10} {'Fails (TV)':<10} {'Diff':<8}")
print("======================================================================")

for name, start, end, cutoff, days, exp_w, exp_f in presets:
    w, f, total = evaluate_preset(name, start, end, cutoff, days)
    # Note: the total N loaded on TV may include/exclude today depending on replay.
    # So we compare Python's total N with TV's total N.
    print(f"{name:<15} {total:<10} {w:<15} {f:<15} {exp_w:<10} {exp_f:<10} {f - exp_f:<8}")
