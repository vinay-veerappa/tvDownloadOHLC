"""
Debug 1800 Break and Q1 Break to find which sessions differ.
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

def classify_detailed(df_p, pct, sample, stop_type, anchor, fallback=0.5):
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
        
        results.append({'date': row['date'], 'side': row['side'], 'won': won, 'failed': failed,
                       'pval': pval, 'bo_mae': bo_mae, 'bo_px': row['bo_px'], 'invalid_px': invalid_px})
        
        hist_all.append(bo_mae)
        if len(hist_all) > ROLLING_BARS: hist_all.pop(0)
        if won:
            hist_win.append(bo_mae)
            if len(hist_win) > ROLLING_BARS: hist_win.pop(0)
        else:
            hist_fail.append(bo_mae)
            if len(hist_fail) > ROLLING_BARS: hist_fail.pop(0)
    
    return pd.DataFrame(results)

for name, cfg in PRESETS.items():
    print("=" * 100)
    print(f"{name} - target {cfg['target_full']}/{cfg['target_failed']}")
    print("=" * 100)
    
    sessions = build_sessions_wick_bo(cfg)
    
    # Try both close configurations
    configs = [
        ('P70', 'wins', 'close', 'bo_px'),
        ('P75', 'wins', 'close', 'bo_px'),
        ('P80', 'wins', 'close', 'bo_px'),
        ('P85', 'wins', 'close', 'or_boundary'),
        ('P90', 'wins', 'close', 'or_boundary'),
        ('P90', 'wins', 'touch', 'or_boundary'),
    ]
    
    for pct_str, sample, stop, anchor in configs:
        pct = int(pct_str[1:])
        res = classify_detailed(sessions, pct, sample, stop, anchor, 0.5)
        w = int(res['won'].sum()); f = int(res['failed'].sum())
        target_w = cfg['target_full']; target_f = cfg['target_failed']
        match = "MATCH" if w == target_w and f == target_f else f"(diff {w-target_w:+d}/{f-target_f:+d})"
        print(f"\n{cfg['or_start']}-{cfg['or_end']} {sample} {stop} {anchor} P{pct}: {w}/{f} {match}")
        
        if w + f == target_w + target_f:
            # Show borderline sessions (where pval is close to bo_mae)
            res_sorted = res.sort_values('bo_mae')
            print("  Borderline sessions (bo_mae near pval):")
            for _, r in res_sorted.iterrows():
                diff = r['bo_mae'] - r['pval']
                marker = " <-- borderline" if abs(diff) < 0.01 else ""
                if abs(diff) < 0.02:
                    print(f"    {r['date']} side={r['side']:>2.0f} won={r['won']} bo_mae={r['bo_mae']:.4f} pval={r['pval']:.4f} diff={diff:+.4f}{marker}")