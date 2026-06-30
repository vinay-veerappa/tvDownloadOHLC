"""
Test if the win condition is simply: max MFE (from BO px) >= EV target,
without any invalidation stop. Fail = didn't reach EV target.
This tests the simple EV-only hypothesis.
"""
import pandas as pd
import numpy as np
import pytz

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
        
        if bo_side == 1:
            mfe = (post_bo_5m['high'].max() - bo_px) / bo_px * 100
        else:
            mfe = (bo_px - post_bo_5m['low'].min()) / bo_px * 100
        
        sessions.append({
            'date': date, 'side': bo_side, 'or_high': or_high, 'or_low': or_low,
            'bo_px': bo_px, 'mfe': mfe,
        })
    return pd.DataFrame(sessions)

all_sessions = {}
for name, cfg in PRESETS.items():
    all_sessions[name] = build_sessions_wick_bo(cfg)
    print(f"{name}: n={len(all_sessions[name])}")

print("\n" + "=" * 100)
print("EV-ONLY RULE: Win = MFE from BO px >= ev_threshold")
print("=" * 100)
print(f"  {'EV Thr':<8} {'1100 BO':<12} {'MO Break':<12} {'1800 Break':<12} {'Q1 Break':<12} {'Match':<8}")
for ev_thr in [0.10, 0.15, 0.20, 0.25, 0.28, 0.29, 0.30, 0.35, 0.40, 0.41, 0.45, 0.50, 0.55, 0.60]:
    vals = []; all_match = True
    for name, cfg in PRESETS.items():
        df = all_sessions[name]
        w = int((df['mfe'] >= ev_thr).sum())
        f = len(df) - w
        vals.append(f"{w}/{f}")
        if w != cfg['target_full'] or f != cfg['target_failed']:
            all_match = False
    print(f"  {ev_thr:<8.2f} {vals[0]:<12} {vals[1]:<12} {vals[2]:<12} {vals[3]:<12} {'MATCH' if all_match else 'x':<8}")

print("\n" + "=" * 100)
print("EV-ONLY with proximity tolerance: Win = MFE >= ev_threshold - tol")
print("=" * 100)
for tol in [0.00, 0.01, 0.02, 0.03, 0.04, 0.05]:
    print(f"\nTolerance = {tol:.2f}%:")
    print(f"  {'EV Thr':<8} {'1100 BO':<12} {'MO Break':<12} {'1800 Break':<12} {'Q1 Break':<12} {'Match':<8}")
    for ev_thr in [0.25, 0.28, 0.29, 0.30, 0.35, 0.40, 0.45, 0.50]:
        vals = []; all_match = True
        for name, cfg in PRESETS.items():
            df = all_sessions[name]
            w = int((df['mfe'] >= (ev_thr - tol)).sum())
            f = len(df) - w
            vals.append(f"{w}/{f}")
            if w != cfg['target_full'] or f != cfg['target_failed']:
                all_match = False
        print(f"  {ev_thr:<8.2f} {vals[0]:<12} {vals[1]:<12} {vals[2]:<12} {vals[3]:<12} {'MATCH' if all_match else 'x':<8}")
