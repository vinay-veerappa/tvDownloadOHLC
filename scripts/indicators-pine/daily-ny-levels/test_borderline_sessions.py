"""
Identify borderline sessions for live chart replay.
Focus on 1800 Break and Q1 Break where we don't have exact matches yet.
Find sessions where the classification is sensitive to small parameter changes.
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

def compute_session_mfe_mae(row):
    """Compute session MFE and MAE from OR boundary for the full session"""
    if row['side'] == 1:
        session_mfe = (row['post_bo']['high'].max() - row['or_high']) / row['or_high'] * 100
        session_mae = (row['or_high'] - row['post_bo']['low'].min()) / row['or_high'] * 100
    else:
        session_mfe = (row['or_low'] - row['post_bo']['low'].min()) / row['or_low'] * 100
        session_mae = (row['post_bo']['high'].max() - row['or_low']) / row['or_low'] * 100
    return session_mfe, session_mae

def compute_bo_mfe_mae(row):
    """Compute BO MFE and MAE from breakout price"""
    if row['side'] == 1:
        bo_mfe = (row['post_bo']['high'].max() - row['bo_px']) / row['bo_px'] * 100
        bo_mae = (row['bo_px'] - row['post_bo']['low'].min()) / row['bo_px'] * 100
    else:
        bo_mfe = (row['bo_px'] - row['post_bo']['low'].min()) / row['bo_px'] * 100
        bo_mae = (row['post_bo']['high'].max() - row['bo_px']) / row['bo_px'] * 100
    return bo_mfe, bo_mae

# 1800 Break analysis
print("=" * 100)
print("1800 BREAK - Show all sessions with key metrics")
print("=" * 100)
cfg_1800 = {'or_start': 1800, 'or_end': 1815, 'cutoff': 300, 'days': '12345',
            'crosses_midnight': True, 'start_date': '2026-03-12'}
sessions_1800 = build_sessions_wick_bo(cfg_1800)
print(f"Total sessions: {len(sessions_1800)}")
print(f"\n{'Date':<12} {'Side':<5} {'OR_High':<10} {'OR_Low':<10} {'BO_px':<10} {'BO_MFE':<8} {'BO_MAE':<8} {'Sess_MFE':<9} {'Sess_MAE':<9}")
for _, r in sessions_1800.iterrows():
    bo_mfe, bo_mae = compute_bo_mfe_mae(r)
    sess_mfe, sess_mae = compute_session_mfe_mae(r)
    print(f"{str(r['date']):<12} {r['side']:>5.0f} {r['or_high']:>9.2f} {r['or_low']:>9.2f} {r['bo_px']:>9.2f} {bo_mfe:>7.3f} {bo_mae:>7.3f} {sess_mfe:>8.3f} {sess_mae:>8.3f}")

# Q1 Break analysis
print("\n" + "=" * 100)
print("Q1 BREAK - Show all sessions with key metrics")
print("=" * 100)
cfg_q1 = {'or_start': 600, 'or_end': 830, 'cutoff': 1200, 'days': '23456',
          'crosses_midnight': False, 'start_date': '2026-03-12'}
sessions_q1 = build_sessions_wick_bo(cfg_q1)
print(f"Total sessions: {len(sessions_q1)}")
print(f"\n{'Date':<12} {'Side':<5} {'OR_High':<10} {'OR_Low':<10} {'BO_px':<10} {'BO_MFE':<8} {'BO_MAE':<8} {'Sess_MFE':<9} {'Sess_MAE':<9}")
for _, r in sessions_q1.iterrows():
    bo_mfe, bo_mae = compute_bo_mfe_mae(r)
    sess_mfe, sess_mae = compute_session_mfe_mae(r)
    print(f"{str(r['date']):<12} {r['side']:>5.0f} {r['or_high']:>9.2f} {r['or_low']:>9.2f} {r['bo_px']:>9.2f} {bo_mfe:>7.3f} {bo_mae:>7.3f} {sess_mfe:>8.3f} {sess_mae:>8.3f}")

# For 1800 Break: find sessions where our best rule (P75 wins close bo_px exclude_bo_bar=True) gives wrong result
# Target: 35 full, 40 failed. Our best: 35/40 with P75 wins close or_boundary exclude_bo_bar=True
# Let me show which sessions are classified as full vs failed with this rule
print("\n" + "=" * 100)
print("1800 BREAK - Classification with best config (P75 wins close or_boundary excl_bo_bar=True)")
print("=" * 100)

def classify_detailed(df_p, pct, sample, stop_type, anchor, exclude_bo_bar=False, fallback=0.5):
    results = []
    hist_all_long = []; hist_all_short = []
    hist_win_long = []; hist_win_short = []
    hist_fail_long = []; hist_fail_short = []
    
    for _, row in df_p.iterrows():
        if exclude_bo_bar and len(row['post_bo']) > 1:
            post = row['post_bo'].iloc[1:]
        else:
            post = row['post_bo']
        
        if anchor == 'bo_px':
            px = row['bo_px']
        else:
            px = row['or_high'] if row['side'] == 1 else row['or_low']
        
        if row['side'] == 1:
            bo_mae = (px - post['low'].min()) / px * 100
        else:
            bo_mae = (post['high'].max() - px) / px * 100
        
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
        post_check = row['post_bo'].iloc[1:] if exclude_bo_bar else row['post_bo']
        for idx, r in post_check.iterrows():
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
        results.append({'date': row['date'], 'side': row['side'], 'won': won, 'bo_mae': bo_mae, 'pval': pval})
        
        hist_all.append(bo_mae)
        if won:
            hist_win.append(bo_mae)
        else:
            hist_fail.append(bo_mae)
    
    return pd.DataFrame(results)

res_1800 = classify_detailed(sessions_1800, 75, 'wins', 'close', 'or_boundary', exclude_bo_bar=True)
print(f"Full: {res_1800['won'].sum()}, Failed: {(~res_1800['won']).sum()}")
print(f"\nFull sessions ({res_1800['won'].sum()}):")
for _, r in res_1800[res_1800['won']].iterrows():
    print(f"  {r['date']} side={r['side']:>2.0f} bo_mae={r['bo_mae']:.4f} pval={r['pval']:.4f}")

print(f"\nFailed sessions ({(~res_1800['won']).sum()}):")
for _, r in res_1800[~res_1800['won']].iterrows():
    print(f"  {r['date']} side={r['side']:>2.0f} bo_mae={r['bo_mae']:.4f} pval={r['pval']:.4f}")