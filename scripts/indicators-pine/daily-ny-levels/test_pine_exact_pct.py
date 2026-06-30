"""
Test percentile method differences.
Pine uses array.percentile_nearest_rank(arr, pct):
  - Sort array ascending
  - rank = ceil(pct/100 * N), 1-indexed
  - return sorted[rank-1]

Python numpy options:
  - 'lower': rank = floor(p/100 * N) + 1
  - 'higher': rank = ceil(p/100 * N)
  - 'nearest': rank = round(p/100 * N)
  - 'linear': interpolation

Test all four and compare to Pine's nearest-rank.
"""
import numpy as np
import pandas as pd
import pytz

def pine_percentile_nearest_rank(arr, pct):
    """Exact replication of Pine's array.percentile_nearest_rank"""
    sorted_arr = np.sort(np.array(arr, dtype=float))
    n = len(sorted_arr)
    if n == 0: return np.nan
    import math
    rank = math.ceil(pct / 100.0 * n)
    rank = max(1, min(rank, n))  # clamp to [1, n]
    return sorted_arr[rank - 1]  # 1-indexed

# Test on small examples
print("=" * 80)
print("PERCENTILE METHOD COMPARISON")
print("=" * 80)

test_arrays = [
    [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],  # N=10
    [0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95],  # N=9
    [0.5, 0.3, 0.8, 0.1, 0.4, 0.6, 0.9, 0.2, 0.7],  # N=9, unsorted
    [0.364, 0.260, 0.508, 0.198, 0.252, 0.524, 0.246, 0.241, 0.262],  # real-ish MAE values
]

for arr in test_arrays:
    print(f"\nArray: {arr} (N={len(arr)})")
    for pct in [25, 50, 75, 80, 85, 90, 95]:
        pine_val = pine_percentile_nearest_rank(arr, pct)
        np_nearest = np.percentile(arr, pct, method='nearest')
        np_lower = np.percentile(arr, pct, method='lower')
        np_higher = np.percentile(arr, pct, method='higher')
        match = "OK" if pine_val == np_nearest else "DIFF"
        print(f"  P{pct:>3}: Pine={pine_val:.4f}  np.nearest={np_nearest:.4f} {match}  |  np.lower={np_lower:.4f}  np.higher={np_higher:.4f}")

# Now run the full classification with EXACT Pine percentile
print("\n" + "=" * 100)
print("CLASSIFICATION WITH EXACT PINE NEAREST-RANK PERCENTILE")
print("=" * 100)

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

def build_sessions_wick_bo(cfg):
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
            if row['high'] > or_high:
                bo_side = 1; bo_px = row['high']; bo_idx = idx; break
            elif row['low'] < or_low:
                bo_side = -1; bo_px = row['low']; bo_idx = idx; break
        if bo_side == 0: continue
        
        post_bo_5m = data_5m.loc[bo_idx:]
        
        sessions.append({
            'date': date, 'side': bo_side, 'or_high': or_high, 'or_low': or_low,
            'bo_px': bo_px, 'post_bo': post_bo_5m,
        })
    return pd.DataFrame(sessions)

def compute_mae_from_anchor(row, anchor):
    if anchor == 'bo_px':
        px = row['bo_px']
    elif anchor == 'or_boundary':
        px = row['or_high'] if row['side'] == 1 else row['or_low']
    else:
        px = row['bo_px']
    if row['side'] == 1:
        return (px - row['post_bo']['low'].min()) / px * 100
    else:
        return (row['post_bo']['high'].max() - px) / px * 100

def classify_pine_exact(df_p, pct, sample, stop_type, anchor, fallback=0.5):
    results = []
    hist_all_long = []; hist_all_short = []
    hist_win_long = []; hist_win_short = []
    hist_fail_long = []; hist_fail_short = []
    
    for _, row in df_p.iterrows():
        bo_mae = compute_mae_from_anchor(row, anchor)
        
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
        for idx, r in row['post_bo'].iterrows():
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

all_sessions = {}
for name, cfg in PRESETS.items():
    all_sessions[name] = build_sessions_wick_bo(cfg)
    print(f"{name}: n={len(all_sessions[name])}")

print("\n" + "=" * 100)
print("FULL SWEEP WITH EXACT PINE NEAREST-RANK PERCENTILE")
print("=" * 100)

matches = []
for pct in [75, 80, 85, 90, 95]:
    for sample in ['all', 'wins', 'fails']:
        for stop_type in ['touch', 'close']:
            for anchor in ['bo_px', 'or_boundary']:
                key = f"P{pct} {sample} {stop_type} {anchor}"
                vals = []; all_match = True
                for name, cfg in PRESETS.items():
                    w, f = classify_pine_exact(all_sessions[name], pct, sample, stop_type, anchor, 0.5)
                    vals.append(f"{w}/{f}")
                    if w != cfg['target_full'] or f != cfg['target_failed']:
                        all_match = False
                if all_match:
                    matches.append(key)

if matches:
    print("\nUNIVERSAL MATCHES FOUND:")
    for m in matches:
        print(f"  {m}")
else:
    print("\nNo universal matches. Closest per preset:")
    for name, cfg in PRESETS.items():
        best = None; best_dist = 1e9
        for pct in [75, 80, 85, 90, 95]:
            for sample in ['all', 'wins', 'fails']:
                for stop_type in ['touch', 'close']:
                    for anchor in ['bo_px', 'or_boundary']:
                        w, f = classify_pine_exact(all_sessions[name], pct, sample, stop_type, anchor, 0.5)
                        dist = abs(w - cfg['target_full']) + abs(f - cfg['target_failed'])
                        if dist < best_dist:
                            best_dist = dist
                            best = (pct, sample, stop_type, anchor, w, f)
        pct, sample, stop_type, anchor, w, f = best
        print(f"  {name:<13} target={cfg['target_full']}/{cfg['target_failed']}  best={w}/{f}  P{pct} {sample} {stop_type} {anchor}")