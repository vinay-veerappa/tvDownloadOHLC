"""
Mirror current Pine logic as closely as possible:
- OR built from 1m LTF
- Signal logic on 5m main chart
- P80 MAE from ALL breakout sessions (bo_mae_all)
- EV target precedence, then fakeout (opposite OR boundary wick), then invalidation
- Compare per-session outcome to Gunship targets
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

def p_nearest(series, p):
    if len(series) == 0: return np.nan
    return np.percentile(series, p, method='nearest')

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
EV_TARGET = 0.30

def build_sessions(cfg):
    valid_dows = days_to_python_dow(cfg['days'])
    start_date = pd.Timestamp(cfg['start_date']).date()
    sessions = []
    for date in sorted(df_1m['date'].unique()):
        if date < start_date: continue
        if date in HOLIDAYS: continue
        if date.weekday() not in valid_dows: continue
        if cfg['crosses_midnight']:
            next_date = date + pd.Timedelta(days=1)
            session_1m = pd.concat([
                df_1m[(df_1m['date'] == date) & (df_1m['et_hhmm'] >= cfg['or_start'])],
                df_1m[(df_1m['date'] == next_date) & (df_1m['et_hhmm'] < cfg['cutoff'])]])
        else:
            session_1m = df_1m[(df_1m['date'] == date) & (df_1m['et_hhmm'] >= cfg['or_start']) & (df_1m['et_hhmm'] < cfg['cutoff'])]
        if session_1m.empty: continue
        
        or_bars = session_1m[(session_1m['et_hhmm'] >= cfg['or_start']) & (session_1m['et_hhmm'] < cfg['or_end'])]
        if or_bars.empty: continue
        or_high = or_bars['high'].max()
        or_low = or_bars['low'].min()
        
        # 5m signal bars from or_end to cutoff
        if cfg['crosses_midnight']:
            next_date = date + pd.Timedelta(days=1)
            data_5m = pd.concat([
                df_5m[(df_5m['date'] == date) & (df_5m['et_hhmm'] >= cfg['or_end'])],
                df_5m[(df_5m['date'] == next_date) & (df_5m['et_hhmm'] < cfg['cutoff'])]])
        else:
            data_5m = df_5m[(df_5m['date'] == date) & (df_5m['et_hhmm'] >= cfg['or_end']) & (df_5m['et_hhmm'] < cfg['cutoff'])]
        if data_5m.empty: continue
        
        sessions.append({
            'date': date, 'or_high': or_high, 'or_low': or_low,
            'data_5m': data_5m,
        })
    return pd.DataFrame(sessions)

def classify_mirror(df_p, ev_target=EV_TARGET, p80_fallback=0.5):
    results = []
    hist_all_long = []
    hist_all_short = []
    
    for _, row in df_p.iterrows():
        data_5m = row['data_5m']
        bo_px = None
        bo_side = 0
        bo_idx = None
        for idx, r in data_5m.iterrows():
            if r['close'] > row['or_high']:
                bo_px = r['close']; bo_side = 1; bo_idx = idx; break
            elif r['close'] < row['or_low']:
                bo_px = r['close']; bo_side = -1; bo_idx = idx; break
        
        if bo_side == 0:
            results.append({'date': row['date'], 'outcome': 'NO_BO', 'won': False, 'failed': False})
            continue
        
        post_bo = data_5m.loc[bo_idx:]
        
        # Compute bo_mae for this session (wick-based from bo_px)
        if bo_side == 1:
            bo_mae = (bo_px - post_bo['low'].min()) / bo_px * 100.0
        else:
            bo_mae = (post_bo['high'].max() - bo_px) / bo_px * 100.0
        
        # P80 from all breakout MAEs for this side
        hist_all = hist_all_long if bo_side == 1 else hist_all_short
        p80 = p80_fallback if len(hist_all) == 0 else p_nearest(hist_all, 80)
        target_px = bo_px * (1 + bo_side * ev_target / 100.0)
        invalid_px = bo_px * (1 - bo_side * p80 / 100.0)
        
        outcome = 0
        for idx, r in post_bo.iterrows():
            # EV target hit takes precedence
            if bo_side == 1 and r['high'] >= target_px:
                outcome = 1; break
            if bo_side == -1 and r['low'] <= target_px:
                outcome = 1; break
            # Fakeout: wick through opposite OR boundary
            if bo_side == 1 and r['low'] < row['or_low']:
                outcome = 2; break
            if bo_side == -1 and r['high'] > row['or_high']:
                outcome = 2; break
            # Invalidation
            if outcome == 0:
                if bo_side == 1 and r['low'] <= invalid_px:
                    outcome = -1
                if bo_side == -1 and r['high'] >= invalid_px:
                    outcome = -1
        
        won = outcome == 1
        failed = outcome == -1 or outcome == 2  # fakeout also counts as fail
        
        results.append({
            'date': row['date'], 'outcome': outcome, 'won': won, 'failed': failed,
            'bo_side': bo_side, 'bo_px': bo_px, 'p80': p80, 'bo_mae': bo_mae,
            'target_px': target_px, 'invalid_px': invalid_px,
        })
        
        hist_all.append(bo_mae)
    
    return pd.DataFrame(results)

all_sessions = {}
for name, cfg in PRESETS.items():
    all_sessions[name] = build_sessions(cfg)
    print(f"{name}: n={len(all_sessions[name])}")

print("\n" + "=" * 100)
print("MIRROR CURRENT PINE LOGIC (1m OR + 5m signal, P80 from ALL, EV precedence, fakeout precedence)")
print("=" * 100)

for name, cfg in PRESETS.items():
    res = classify_mirror(all_sessions[name])
    w = int(res['won'].sum())
    f = int(res['failed'].sum())
    no_bo = int((res['outcome'] == 'NO_BO').sum())
    target = f"{cfg['target_full']}/{cfg['target_failed']}"
    match = "MATCH" if w == cfg['target_full'] and f == cfg['target_failed'] else "x"
    print(f"{name:<13} wins={w:>3} fails={f:>3} no_bo={no_bo:>3} target={target:>12} {match}")

# Show mismatched dates for 1100 BO
print("\n" + "=" * 100)
print("1100 BO per-session outcomes:")
print("=" * 100)
res_1100 = classify_mirror(all_sessions['1100 BO'])
for _, r in res_1100.iterrows():
    print(f"  {r['date']} side={r['bo_side']:>2} outcome={r['outcome']:>3} p80={r['p80']:.3f} bo_mae={r['bo_mae']:.3f} bo_px={r['bo_px']:.2f} inv={r['invalid_px']:.2f}")
