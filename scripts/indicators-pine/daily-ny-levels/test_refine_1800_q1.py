"""
Focus on 1800 Break and Q1 Break.
For 1800 Break: P75 wins close bo_px gives 34/41 (target 35/40).
  - Session 2026-06-17: bo_mae=0.2074, pval=0.2241 (just above invalidation -> win)
  - Session 2026-05-07: bo_mae=0.2241, pval=0.2324 (just above invalidation -> win)
  If we could get one more session to flip from fail to win, we'd get 35/40.
  Or if one win flipped to fail, we'd get 33/42 (worse).

For Q1 Break: P85 wins close or_boundary gives 43/31 (target 44/29).
  Need 1 more win and 2 fewer fails.

Test: what if the rolling history is NOT 5000 bars but something else?
Also test: what if the breakout detection uses CLOSE crossing instead of HIGH/LOW?
And test: what if the MAE is computed differently (e.g., excluding the breakout bar)?
"""
import numpy as np
import pandas as pd
import pytz
import math

def pine_percentile_nearest_rank(arr, pct):
    sorted_arr = np.sort(np.array(arr, dtype=float))
    n = len(sorted_arr)
    if n == 0: return np.nan
    rank = math.ceil(pct / 100.0 * n)
    rank = max(1, min(rank, n))
    return sorted_arr[rank - 1]

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
    '1800 Break':  {'or_start': 1800, 'or_end': 1815, 'cutoff': 300,  'days': '12345',
                    'crosses_midnight': True, 'start_date': '2026-03-12',
                    'target_full': 35, 'target_failed': 40},
    'Q1 Break':    {'or_start': 600,  'or_end': 830,  'cutoff': 1200, 'days': '23456',
                    'crosses_midnight': False, 'start_date': '2026-03-12',
                    'target_full': 44, 'target_failed': 29},
    '1100 BO':     {'or_start': 1100, 'or_end': 1115, 'cutoff': 1230, 'days': '23456',
                    'crosses_midnight': False, 'start_date': '2026-03-13',
                    'target_full': 55, 'target_failed': 18},
    'MO Break':    {'or_start': 930,  'or_end': 935,  'cutoff': 1200, 'days': '23456',
                    'crosses_midnight': False, 'start_date': '2026-03-12',
                    'target_full': 32, 'target_failed': 42},
}

def build_sessions(cfg, bo_method='wick'):
    """bo_method: 'wick' (high/low crosses), 'close' (close crosses)"""
    valid_dows = days_to_python_dow(cfg['days'])
    start_date = pd.Timestamp(cfg['start_date']).date()
    sessions = []
    for date in sorted(df_5m['date'].unique()):
        if date < start_date: continue
        if date in HOLIDAYS: continue
        if date.weekday() not in valid_dows: continue
        if cfg['crosses_midnight']:
            next_date = date + pd.Timedelta(days=1)
            session_5m = pd.concat([
                df_5m[(df_5m['date'] == date) & (df_5m['et_hhmm'] >= cfg['or_start'])],
                df_5m[(df_5m['date'] == next_date) & (df_5m['et_hhmm'] < cfg['cutoff'])]])
        else:
            session_5m = df_5m[(df_5m['date'] == date) & (df_5m['et_hhmm'] >= cfg['or_start']) & (df_5m['et_hhmm'] < cfg['cutoff'])]
        if session_5m.empty: continue
        
        or_bars = session_5m[(session_5m['et_hhmm'] >= cfg['or_start']) & (session_5m['et_hhmm'] < cfg['or_end'])]
        if or_bars.empty: continue
        or_high = or_bars['high'].max()
        or_low = or_bars['low'].min()
        
        data_5m = session_5m[session_5m['et_hhmm'] >= cfg['or_end']]
        if data_5m.empty: continue
        
        bo_side = 0; bo_px = None; bo_idx = None
        for idx, row in data_5m.iterrows():
            if bo_method == 'wick':
                if row['high'] > or_high:
                    bo_side = 1; bo_px = row['high']; bo_idx = idx; break
                elif row['low'] < or_low:
                    bo_side = -1; bo_px = row['low']; bo_idx = idx; break
            else:  # close
                if row['close'] > or_high:
                    bo_side = 1; bo_px = row['close']; bo_idx = idx; break
                elif row['close'] < or_low:
                    bo_side = -1; bo_px = row['close']; bo_idx = idx; break
        if bo_side == 0: continue
        
        post_bo_5m = data_5m.loc[bo_idx:]
        
        sessions.append({
            'date': date, 'side': bo_side, 'or_high': or_high, 'or_low': or_low,
            'bo_px': bo_px, 'post_bo': post_bo_5m,
        })
    return pd.DataFrame(sessions)

def compute_mae_from_anchor(row, anchor, exclude_bo_bar=False):
    if exclude_bo_bar and len(row['post_bo']) > 1:
        post = row['post_bo'].iloc[1:]
    else:
        post = row['post_bo']
    if anchor == 'bo_px':
        px = row['bo_px']
    elif anchor == 'or_boundary':
        px = row['or_high'] if row['side'] == 1 else row['or_low']
    else:
        px = row['bo_px']
    if row['side'] == 1:
        return (px - post['low'].min()) / px * 100
    else:
        return (post['high'].max() - px) / px * 100

def classify(df_p, pct, sample, stop_type, anchor, bo_method='wick', exclude_bo_bar=False, fallback=0.5, rolling_bars=5000):
    results = []
    hist_all_long = []; hist_all_short = []
    hist_win_long = []; hist_win_short = []
    hist_fail_long = []; hist_fail_short = []
    
    for _, row in df_p.iterrows():
        bo_mae = compute_mae_from_anchor(row, anchor, exclude_bo_bar)
        
        if row['side'] == 1:
            hist_all = hist_all_long; hist_win = hist_win_long; hist_fail = hist_fail_long
        else:
            hist_all = hist_all_short; hist_win = hist_win_short; hist_fail = hist_fail_short
        
        hist = hist_all if sample == 'all' else (hist_win if sample == 'wins' else hist_fail)
        pval = fallback if len(hist) == 0 else pine_percentile_nearest_rank(hist, pct)
        
        if anchor == 'bo_px':
            invalid_px = row['bo_px'] * (1 - row['side'] * pval / 100)
        else:
            invalid_px = (row['or_high'] if row['side'] == 1 else row['or_low']) * (1 - row['side'] * pval / 100)
        
        stop_hit = False
        post = row['post_bo'].iloc[1:] if exclude_bo_bar else row['post_bo']
        for idx, r in post.iterrows():
            if stop_type == 'close':
                if row['side'] == 1 and r['close'] <= invalid_px:
                    stop_hit = True; break
                elif row['side'] == -1 and r['close'] >= invalid_px:
                    stop_hit = True; break
            else:
                if row['side'] == 1 and r['low'] <= invalid_px:
                    stop_hit = True; break
                elif row['side'] == -1 and r['high'] >= invalid_px:
                    stop_hit = True; break
        
        won = not stop_hit
        failed = stop_hit
        
        results.append({'won': won, 'failed': failed})
        
        hist_all.append(bo_mae)
        if len(hist_all) > rolling_bars: hist_all.pop(0)
        if won:
            hist_win.append(bo_mae)
            if len(hist_win) > rolling_bars: hist_win.pop(0)
        else:
            hist_fail.append(bo_mae)
            if len(hist_fail) > rolling_bars: hist_fail.pop(0)
    
    res = pd.DataFrame(results)
    return int(res['won'].sum()), int(res['failed'].sum())

# Test 1800 Break with different configurations
print("=" * 100)
print("1800 Break - target 35/40")
print("=" * 100)

for bo_method in ['wick', 'close']:
    for exclude_bo in [False, True]:
        sessions = build_sessions(PRESETS['1800 Break'], bo_method)
        print(f"\nBO method={bo_method}, exclude_bo_bar={exclude_bo}, n={len(sessions)}")
        print(f"  {'Config':<40} {'W/F':<10}")
        for pct in [70, 75, 80, 85]:
            for sample in ['all', 'wins']:
                for stop_type in ['touch', 'close']:
                    for anchor in ['bo_px', 'or_boundary']:
                        key = f"P{pct} {sample} {stop_type} {anchor}"
                        w, f = classify(sessions, pct, sample, stop_type, anchor, bo_method, exclude_bo)
                        match = "MATCH" if w == 35 and f == 40 else f"({w-35:+d}/{f-40:+d})"
                        if abs(w-35) <= 1 and abs(f-40) <= 1:
                            print(f"    {key:<40} {w}/{f} {match}")

# Test Q1 Break
print("\n" + "=" * 100)
print("Q1 Break - target 44/29")
print("=" * 100)

for bo_method in ['wick', 'close']:
    for exclude_bo in [False, True]:
        sessions = build_sessions(PRESETS['Q1 Break'], bo_method)
        print(f"\nBO method={bo_method}, exclude_bo_bar={exclude_bo}, n={len(sessions)}")
        print(f"  {'Config':<40} {'W/F':<10}")
        for pct in [70, 75, 80, 85, 90]:
            for sample in ['all', 'wins']:
                for stop_type in ['touch', 'close']:
                    for anchor in ['bo_px', 'or_boundary']:
                        key = f"P{pct} {sample} {stop_type} {anchor}"
                        w, f = classify(sessions, pct, sample, stop_type, anchor, bo_method, exclude_bo)
                        match = "MATCH" if w == 44 and f == 29 else f"({w-44:+d}/{f-29:+d})"
                        if abs(w-44) <= 2 and abs(f-29) <= 2:
                            print(f"    {key:<40} {w}/{f} {match}")