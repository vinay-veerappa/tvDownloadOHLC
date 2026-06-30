"""
Find universal config with exact Pine nearest-rank percentile.
Best per-preset matches so far:
- 1100 BO: 55/18 ✅ P75 all, close stop, OR-boundary anchor (wick BO)
- MO Break: 32/42 ✅ P80 wins, touch stop, OR-boundary anchor (wick BO)
- 1800 Break: 35/40 ✅ P75 wins, close stop, OR-boundary anchor (wick BO, exclude_bo_bar=True)
- Q1 Break: 44/29 ✅ P90 wins, close stop, OR-boundary anchor (close BO, exclude_bo_bar=True)

Test if there's ONE config that matches all 4.
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
    '1100 BO':     {'or_start': 1100, 'or_end': 1115, 'cutoff': 1230, 'days': '23456',
                    'crosses_midnight': False, 'start_date': '2026-03-13',
                    'target_full': 55, 'target_failed': 18},
    'MO Break':    {'or_start': 930,  'or_end': 935,  'cutoff': 1200, 'days': '23456',
                    'crosses_midnight': False, 'start_date': '2026-03-12',
                    'target_full': 32, 'target_failed': 42},
    '1800 Break':  {'or_start': 1800, 'or_end': 1815, 'cutoff': 300,  'days': '12345',
                    'crosses_midnight': True, 'start_date': '2026-03-12',
                    'target_full': 35, 'target_failed': 40},
    'Q1 Break':    {'or_start': 600,  'or_end': 830,  'cutoff': 1200, 'days': '23456',
                    'crosses_midnight': False, 'start_date': '2026-03-12',
                    'target_full': 44, 'target_failed': 29},
}
ROLLING_BARS = 5000

def build_sessions(cfg, bo_method='wick'):
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
            else:
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
    if row['side'] == 1:
        return (px - post['low'].min()) / px * 100
    else:
        return (post['high'].max() - px) / px * 100

def classify(df_p, pct, sample, stop_type, anchor, bo_method='wick', exclude_bo_bar=False, fallback=0.5):
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
        if len(hist_all) > ROLLING_BARS: hist_all.pop(0)
        if won:
            hist_win.append(bo_mae)
            if len(hist_win) > ROLLING_BARS: hist_win.pop(0)
        else:
            hist_fail.append(bo_mae)
            if len(hist_fail) > ROLLING_BARS: hist_fail.pop(0)
    
    res = pd.DataFrame(results)
    return int(res['won'].sum()), int(res['failed'].sum())

print("=" * 100)
print("UNIVERSAL CONFIG SEARCH")
print("=" * 100)

matches = []
for bo_method in ['wick', 'close']:
    for exclude_bo in [False, True]:
        for pct in [70, 75, 80, 85, 90]:
            for sample in ['all', 'wins']:
                for stop_type in ['touch', 'close']:
                    for anchor in ['bo_px', 'or_boundary']:
                        key = f"bo={bo_method} excl_bo={exclude_bo} P{pct} {sample} {stop_type} {anchor}"
                        vals = []; all_match = True
                        for name, cfg in PRESETS.items():
                            sessions = build_sessions(cfg, bo_method)
                            w, f = classify(sessions, pct, sample, stop_type, anchor, bo_method, exclude_bo)
                            vals.append(f"{w}/{f}")
                            if w != cfg['target_full'] or f != cfg['target_failed']:
                                all_match = False
                        if all_match:
                            matches.append((key, vals))

if matches:
    print("\n🎉 UNIVERSAL MATCHES FOUND:")
    for key, vals in matches:
        print(f"  {key}")
        print(f"    1100 BO={vals[0]}  MO Break={vals[1]}  1800 Break={vals[2]}  Q1 Break={vals[3]}")
else:
    print("\nNo universal matches. Showing 3-of-4 matches:")
    for bo_method in ['wick', 'close']:
        for exclude_bo in [False, True]:
            for pct in [70, 75, 80, 85, 90]:
                for sample in ['all', 'wins']:
                    for stop_type in ['touch', 'close']:
                        for anchor in ['bo_px', 'or_boundary']:
                            matches_count = 0
                            vals = []
                            for name, cfg in PRESETS.items():
                                sessions = build_sessions(cfg, bo_method)
                                w, f = classify(sessions, pct, sample, stop_type, anchor, bo_method, exclude_bo)
                                vals.append(f"{w}/{f}")
                                if w == cfg['target_full'] and f == cfg['target_failed']:
                                    matches_count += 1
                            if matches_count >= 3:
                                key = f"bo={bo_method} excl_bo={exclude_bo} P{pct} {sample} {stop_type} {anchor}"
                                print(f"  [{matches_count}/4] {key}")
                                print(f"    1100 BO={vals[0]}  MO Break={vals[1]}  1800 Break={vals[2]}  Q1 Break={vals[3]}")