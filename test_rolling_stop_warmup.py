import pandas as pd
import numpy as np
import pytz

def p_nearest(series, p):
    if len(series) == 0: return 0.5
    return np.percentile(series, p, method='nearest')

df = pd.read_parquet('data/live/live_storage_-NQ.parquet')
df['datetime'] = pd.to_datetime(df['timestamp'], utc=True)
df = df.set_index('datetime')

# Load all data starting from Dec 30, 2025 (to build history!)
df_all = df[(df.index >= '2025-12-30') & (df.index < '2026-06-30')]
df_all = df_all[~df_all.index.strftime('%Y-%m-%d').isin(['2026-05-25', '2026-06-19'])]

et = pytz.timezone('America/New_York')
df_all['et_time'] = df_all.index.tz_convert(et)
df_all['et_hhmm'] = df_all['et_time'].dt.hour * 100 + df_all['et_time'].dt.minute
df_all['date'] = df_all['et_time'].dt.date

def evaluate_preset_warmup(name, or_start, or_end, cutoff, days_list, use_wins_only=False):
    sessions = []
    for date, day_1m in df_all.groupby('date'):
        dow = day_1m.index[0].tz_convert(et).dayofweek + 2
        if dow == 8: dow = 1
        if dow not in days_list: continue
        
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
            
        if or_bars.empty or data_1m.empty: continue
        
        or_high = or_bars['high'].max()
        or_low = or_bars['low'].min()
        
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
                
        if bo_side == 0: continue
        post_bo = data_1m.loc[bo_idx:]
        close_at_cutoff = data_1m['close'].iloc[-1]
        
        sessions.append({
            'date': date,
            'side': bo_side,
            'or_high': or_high,
            'or_low': or_low,
            'bo_px': bo_px,
            'post_bo': post_bo,
            'close_at_cutoff': close_at_cutoff,
            'crossed_opposite': (bo_side == 1 and close_at_cutoff < or_low) or (bo_side == -1 and close_at_cutoff > or_high)
        })

    hist_mae_bull = []
    hist_mae_bear = []
    
    wins_count = 0
    fails_count = 0
    study_count = 0
    
    for t in range(len(sessions)):
        sess = sessions[t]
        date = sess['date']
        is_study_period = date >= pd.Timestamp('2026-03-16').date()
        
        side = sess['side']
        bo_px = sess['bo_px']
        post_bo = sess['post_bo']
        
        if side == 1:
            p80_mae_pct = p_nearest(hist_mae_bull, 80)
            max_drawdown = bo_px - post_bo['low'].min()
        else:
            p80_mae_pct = p_nearest(hist_mae_bear, 80)
            max_drawdown = post_bo['high'].max() - bo_px
            
        mae_pct = (max_drawdown / bo_px) * 100
        
        # Stop loss level
        if side == 1:
            sl_level = bo_px * (1 - p80_mae_pct / 100)
            stopped_out = post_bo['low'].min() < sl_level
        else:
            sl_level = bo_px * (1 + p80_mae_pct / 100)
            stopped_out = post_bo['high'].max() > sl_level
            
        is_failed = sess['crossed_opposite'] or stopped_out
        is_win = not is_failed
        
        if is_study_period:
            study_count += 1
            if is_win: wins_count += 1
            else: fails_count += 1
            
        if is_win:
            if use_wins_only:
                if side == 1: hist_mae_bull.append(mae_pct)
                else: hist_mae_bear.append(mae_pct)
        
        if not use_wins_only:
            if side == 1: hist_mae_bull.append(mae_pct)
            else: hist_mae_bear.append(mae_pct)
            
    return wins_count, fails_count, study_count

presets = [
    ("1100 BO", 1100, 1115, 1230, [2, 3, 4, 5, 6], 55, 18),
    ("MO Break", 930, 935, 1200, [2, 3, 4, 5, 6], 32, 41),
    # Magic Hour (excluding today) is 54 wins / 6 fails (total 60)
    ("Magic Hour", 300, 700, 830, [2, 3, 4, 5, 6], 54, 6),
    ("1800 Break", 1800, 1815, 300, [1, 2, 3, 4, 5], 35, 39)
]

print("======================================================================")
print("WARM-UP ROLLING STOP-LOSS VALIDATION (ALL BREAKOUTS MAE)")
print("======================================================================")
print(f"{'Preset Name':<15} {'N (Total)':<10} {'Wins (Python)':<15} {'Fails (Python)':<15} {'Wins (TV)':<10} {'Fails (TV)':<10} {'Match?':<8}")
print("======================================================================")
for name, start, end, cutoff, days, exp_w, exp_f in presets:
    w, f, total = evaluate_preset_warmup(name, start, end, cutoff, days, use_wins_only=False)
    match = "YES" if w == exp_w and f == exp_f else "NO"
    print(f"{name:<15} {total:<10} {w:<15} {f:<15} {exp_w:<10} {exp_f:<10} {match:<8}")

print("\n======================================================================")
print("WARM-UP ROLLING STOP-LOSS VALIDATION (WINS-ONLY MAE)")
print("======================================================================")
print(f"{'Preset Name':<15} {'N (Total)':<10} {'Wins (Python)':<15} {'Fails (Python)':<15} {'Wins (TV)':<10} {'Fails (TV)':<10} {'Match?':<8}")
print("======================================================================")
for name, start, end, cutoff, days, exp_w, exp_f in presets:
    w, f, total = evaluate_preset_warmup(name, start, end, cutoff, days, use_wins_only=True)
    match = "YES" if w == exp_w and f == exp_f else "NO"
    print(f"{name:<15} {total:<10} {w:<15} {f:<15} {exp_w:<10} {exp_f:<10} {match:<8}")
