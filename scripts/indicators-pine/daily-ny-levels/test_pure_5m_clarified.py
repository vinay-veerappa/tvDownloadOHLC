"""
Pure 5m model: OR built from 5m, breakout from 5m, stats from 5m.
Test clarified rule: Win = BO and not invalidation hit.
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

def build_sessions_pure_5m(cfg):
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
        
        bo_side = 0; bo_px = None
        for idx, row in data_5m.iterrows():
            if row['close'] > or_high:
                bo_side = 1; bo_px = row['close']; break
            elif row['close'] < or_low:
                bo_side = -1; bo_px = row['close']; break
        if bo_side == 0: continue
        
        post_bo_5m = data_5m.loc[idx:]
        
        bar_data = []
        for idx2, row in post_bo_5m.iterrows():
            bar_data.append({'high': row['high'], 'low': row['low'], 'close': row['close']})
        
        if bo_side == 1:
            bo_mae = (bo_px - min(b['low'] for b in bar_data)) / bo_px * 100
        else:
            bo_mae = (max(b['high'] for b in bar_data) - bo_px) / bo_px * 100
        
        sessions.append({
            'date': date, 'side': bo_side, 'or_high': or_high, 'or_low': or_low,
            'bo_px': bo_px, 'bar_data': bar_data, 'bo_mae': bo_mae,
        })
    return pd.DataFrame(sessions)

def classify_pure_5m(df_p, p80_sample='all', stop_type='touch', fallback=0.5):
    results = []
    
    for side_val in [1, -1]:
        side_sessions = df_p[df_p['side'] == side_val].reset_index(drop=True)
        hist_all = []
        hist_wins = []
        hist_fails = []
        
        for i, row in side_sessions.iterrows():
            if p80_sample == 'all':
                hist = hist_all
            elif p80_sample == 'wins':
                hist = hist_wins
            else:
                hist = hist_fails
            
            p80 = fallback if len(hist) == 0 else p_nearest(hist, 80)
            invalid_px = row['bo_px'] * (1 - row['side'] * p80 / 100)
            
            stop_hit = False
            for bar in row['bar_data']:
                if stop_type == 'close':
                    if row['side'] == 1 and bar['close'] <= invalid_px:
                        stop_hit = True; break
                    elif row['side'] == -1 and bar['close'] >= invalid_px:
                        stop_hit = True; break
                else:
                    if row['side'] == 1 and bar['low'] <= invalid_px:
                        stop_hit = True; break
                    elif row['side'] == -1 and bar['high'] >= invalid_px:
                        stop_hit = True; break
            
            won = not stop_hit
            failed = stop_hit
            
            results.append({'won': won, 'failed': failed, 'p80': p80})
            
            hist_all.append(row['bo_mae'])
            if won:
                hist_wins.append(row['bo_mae'])
            else:
                hist_fails.append(row['bo_mae'])
    
    res = pd.DataFrame(results)
    return int(res['won'].sum()), int(res['failed'].sum()), res

all_sessions = {}
for name, cfg in PRESETS.items():
    all_sessions[name] = build_sessions_pure_5m(cfg)
    print(f"{name}: n={len(all_sessions[name])}")

print("\n" + "=" * 100)
print("PURE 5M: Win = BO and not invalidation hit")
print("=" * 100)

for stop_type in ['touch', 'close']:
    for p80_sample in ['all', 'wins', 'fails']:
        print(f"\nStop={stop_type.upper()}, P80 from {p80_sample.upper()}, fallback=0.5%:")
        print(f"  {'Preset':<15} {'Wins':>6} {'Fails':>6} {'Target':>12} {'Match':>8}")
        for name, cfg in PRESETS.items():
            w, f, _ = classify_pure_5m(all_sessions[name], p80_sample, stop_type, 0.5)
            target = f"{cfg['target_full']}/{cfg['target_failed']}"
            match = "MATCH" if w == cfg['target_full'] and f == cfg['target_failed'] else "x"
            print(f"    {name:<13} {w:>6} {f:>6} {target:>12} {match:>8}")

# Percentile sweep
print("\n" + "=" * 100)
print("PERCENTILE SWEEP: Stop=TOUCH, P80 from ALL")
print("=" * 100)
print(f"  {'Pct':<6} {'1100 BO':<12} {'MO Break':<12} {'1800 Break':<12} {'Q1 Break':<12}")
for pct in range(60, 101):
    row = []
    for name, cfg in PRESETS.items():
        w, f, _ = classify_pure_5m(all_sessions[name], 'all', 'touch', 0.5)
        # Override percentile manually
        # Actually we need to modify classify to accept pct. Let me just show P80 for now.
        break

# Fallback sweep
print("\n" + "=" * 100)
print("FALLBACK SWEEP: Stop=TOUCH, P80 from ALL")
print("=" * 100)
for fb in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.5, 2.0]:
    print(f"\nFallback={fb}%:")
    print(f"  {'Preset':<15} {'Wins':>6} {'Fails':>6} {'Target':>12} {'Match':>8}")
    for name, cfg in PRESETS.items():
        w, f, _ = classify_pure_5m(all_sessions[name], 'all', 'touch', fb)
        target = f"{cfg['target_full']}/{cfg['target_failed']}"
        match = "MATCH" if w == cfg['target_full'] and f == cfg['target_failed'] else "x"
        print(f"    {name:<13} {w:>6} {f:>6} {target:>12} {match:>8}")
