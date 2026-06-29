import pandas as pd
import numpy as np
import pytz

def p_nearest(series, p):
    if len(series) == 0: return 0.5  # default fallback
    return np.percentile(series, p, method='nearest')

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
        # Check dayofweek (1=Sunday, 2=Monday, ..., 7=Saturday)
        dow = day_1m.index[0].tz_convert(et).dayofweek + 2  # pandas is 0=Mon, 6=Sun -> shift to 1=Sun, 2=Mon
        if dow == 8: dow = 1
        
        if dow not in days_list:
            continue
            
        rth_1m = day_1m[(day_1m['et_hhmm'] >= 930) | (day_1m['et_hhmm'] < 1600)]  # RTH or full day depending on preset
        # Since some sessions cross midnight (like 1800 Break), let's use the whole day's data
        rth_1m = day_1m.copy()
        
        # 1800 Break crosses midnight: OR is 18:00 - 18:15, Cutoff is 03:00 next day.
        # So we need to handle midnight crossing.
        crosses_midnight = cutoff < or_start
        
        if crosses_midnight:
            # For 1800 Break, OR is on the current date, cutoff is on the NEXT date.
            # So for date D, we need range 18:00 to 18:15, and data up to 03:00 on D+1.
            # Let's pull date D's evening and D+1's early morning.
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
            
        # Post breakout 1-minute tracking
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

    # Now simulate the rolling lifecycle
    # hist_mae_all contains prior breakouts' MAE percentages
    hist_mae_all = []
    
    wins_count = 0
    fails_count = 0
    
    details = []
    
    for t in range(len(sessions)):
        sess = sessions[t]
        date = sess['date']
        
        # Calculate current stop-loss level based on rolling P80 MAE of ALL prior breakouts
        p80_mae_pct = p_nearest(hist_mae_all, 80)
        
        bo_px = sess['bo_px']
        side = sess['side']
        post_bo = sess['post_bo']
        
        # Drawdown calculation (in percent from BO price)
        if side == 1:
            max_drawdown_pts = bo_px - post_bo['low'].min()
        else:
            max_drawdown_pts = post_bo['high'].max() - bo_px
            
        mae_pct = (max_drawdown_pts / bo_px) * 100
        
        # Stop loss price level
        if side == 1:
            sl_level = bo_px * (1 - p80_mae_pct / 100)
            stopped_out = post_bo['low'].min() < sl_level
        else:
            sl_level = bo_px * (1 + p80_mae_pct / 100)
            stopped_out = post_bo['high'].max() > sl_level
            
        # Outcomes:
        # Failed if crossed opposite at cutoff OR stopped out intraday
        is_failed = sess['crossed_opposite'] or stopped_out
        is_win = not is_failed
        
        if is_win:
            wins_count += 1
        else:
            fails_count += 1
            
        # Always append to all breakouts history
        hist_mae_all.append(mae_pct)
            
        details.append({
            'date': date,
            'side': side,
            'outcome': 'Win' if is_win else 'Fail',
            'stopped_out': stopped_out,
            'crossed_opp': sess['crossed_opposite'],
            'p80_mae_pct': p80_mae_pct,
            'mae_pct': mae_pct
        })
        
    return wins_count, fails_count, len(sessions), details

presets = [
    # (name, start, end, cutoff, days_list, Gunship expected wins/losses (excluding today))
    # Note: 1100 BO (excluding today) is 55 wins / 18 fails (total 73)
    ("1100 BO", 1100, 1115, 1230, [2, 3, 4, 5, 6], 55, 18),
    # MO Break (excluding today) is 32 wins / 41 fails (total 73)
    ("MO Break", 930, 935, 1200, [2, 3, 4, 5, 6], 32, 41),
    # Magic Hour (excluding today) is 55 wins / 5 fails (total 60)
    ("Magic Hour", 300, 700, 830, [2, 3, 4, 5, 6], 55, 5),
    # 1800 Break (excluding today) is 35 wins / 39 fails (total 74)
    ("1800 Break", 1800, 1815, 300, [1, 2, 3, 4, 5], 35, 39)
]

print("======================================================================")
# Print table header
print(f"{'Preset Name':<15} {'N (Total)':<10} {'Wins (Python)':<15} {'Fails (Python)':<15} {'Wins (TV)':<10} {'Fails (TV)':<10} {'Match?':<8}")
print("======================================================================")

for name, start, end, cutoff, days, exp_w, exp_f in presets:
    w, f, total, details = evaluate_preset(name, start, end, cutoff, days)
    match = "YES" if w == exp_w and f == exp_f else "NO"
    print(f"{name:<15} {total:<10} {w:<15} {f:<15} {exp_w:<10} {exp_f:<10} {match:<8}")
