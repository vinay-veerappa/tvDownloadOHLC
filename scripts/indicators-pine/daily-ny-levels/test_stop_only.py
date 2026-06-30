"""
Test P80 stop-loss ONLY (no R2 fakeout rule).
The user confirmed June 18 (1100 BO) failed because the P80 MAE stop was hit (CLOSE-based).
June 18 also has R2=Y, but the user attributed the fail to the stop, not R2.
Maybe the Gunship ONLY uses the P80 stop, not R2.

Test: Win = NOT stop_hit. Fail = stop_hit only.
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
            session_5m = pd.concat([
                df_5m[(df_5m['date'] == date) & (df_5m['et_hhmm'] >= cfg['or_start'])],
                df_5m[(df_5m['date'] == next_date) & (df_5m['et_hhmm'] < cfg['cutoff'])]])
        else:
            session_1m = df_1m[(df_1m['date'] == date) & (df_1m['et_hhmm'] >= cfg['or_start']) & (df_1m['et_hhmm'] < cfg['cutoff'])]
            session_5m = df_5m[(df_5m['date'] == date) & (df_5m['et_hhmm'] >= cfg['or_start']) & (df_5m['et_hhmm'] < cfg['cutoff'])]
        if session_1m.empty or session_5m.empty: continue
        or_bars = session_1m[(session_1m['et_hhmm'] >= cfg['or_start']) & (session_1m['et_hhmm'] < cfg['or_end'])]
        if or_bars.empty: continue
        or_high = or_bars['high'].max()
        or_low = or_bars['low'].min()
        data_1m = session_1m[session_1m['et_hhmm'] >= cfg['or_end']]
        data_5m = session_5m[session_5m['et_hhmm'] >= cfg['or_end']]
        if data_1m.empty or data_5m.empty: continue
        
        bo_side = 0; bo_px = None; bo_idx = None
        for idx, row in data_1m.iterrows():
            if row['close'] > or_high:
                bo_side = 1; bo_px = row['close']; bo_idx = idx; break
            elif row['close'] < or_low:
                bo_side = -1; bo_px = row['close']; bo_idx = idx; break
        if bo_side == 0: continue
        
        bo_5m_idx = None
        for idx in data_5m.index:
            if idx >= bo_idx: bo_5m_idx = idx; break
        if bo_5m_idx is None: bo_5m_idx = data_5m.index[0]
        post_bo_5m = data_5m.loc[bo_5m_idx:]
        
        if bo_side == 1:
            mae_bo = ((bo_px - post_bo_5m['low'].min()) / bo_px) * 100
        else:
            mae_bo = ((post_bo_5m['high'].max() - bo_px) / bo_px) * 100
        
        bar_data = []
        for idx, row in post_bo_5m.iterrows():
            bar_data.append({'high': row['high'], 'low': row['low'], 'close': row['close']})
        
        sessions.append({
            'date': date, 'side': bo_side, 'or_high': or_high, 'or_low': or_low,
            'bo_px': bo_px, 'mae_bo': mae_bo, 'bar_data': bar_data,
        })
    return pd.DataFrame(sessions)

def test_stop_only(df_p, p80_sample, stop_type, fallback):
    """P80 stop-loss ONLY. No R2. Win = NOT stop_hit."""
    results = []
    for side_val in [1, -1]:
        side_sessions = df_p[df_p['side'] == side_val].reset_index(drop=True)
        hist_wins = []
        hist_all = []
        hist_fails = []
        
        for i, row in side_sessions.iterrows():
            if p80_sample == 'wins': hist = hist_wins
            elif p80_sample == 'all': hist = hist_all
            elif p80_sample == 'fails': hist = hist_fails
            
            p80 = p_nearest(hist, 80) if len(hist) > 0 else fallback
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
            results.append({'date': row['date'], 'side': row['side'], 'won': won})
            
            hist_all.append(row['mae_bo'])
            if won: hist_wins.append(row['mae_bo'])
            else: hist_fails.append(row['mae_bo'])
    
    res = pd.DataFrame(results).sort_values('date').reset_index(drop=True)
    return res['won'].sum(), (~res['won']).sum()

all_sessions = {}
for name, cfg in PRESETS.items():
    all_sessions[name] = build_sessions(cfg)

# Test P80 stop ONLY (no R2)
print("=" * 90)
print("P80 STOP-LOSS ONLY (no R2 fakeout rule)")
print("=" * 90)

for stop_type in ['close', 'touch']:
    for p80_sample in ['wins', 'all', 'fails']:
        print(f"\n  Stop={stop_type.upper()}, P80 from {p80_sample.upper()}, fb=0.5%:")
        print(f"  {'Preset':<15} {'Wins':>6} {'Fails':>6} {'Target':>12} {'Match':>8}")
        print(f"  {'-'*55}")
        for name, cfg in PRESETS.items():
            w, f = test_stop_only(all_sessions[name], p80_sample, stop_type, 0.5)
            target = f"{cfg['target_full']}/{cfg['target_failed']}"
            match = "✅" if w == cfg['target_full'] and f == cfg['target_failed'] else "❌"
            print(f"    {name:<13} {w:>6} {f:>6} {target:>12} {match:>8}")

# Fallback sweep for P80 from ALL, CLOSE
print(f"\n  --- Fallback sweep (Stop=CLOSE, P80 from ALL) ---")
for fb in [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.5, 2.0]:
    print(f"\n  Fallback={fb}%:")
    print(f"  {'Preset':<15} {'Wins':>6} {'Fails':>6} {'Target':>12} {'Match':>8}")
    print(f"  {'-'*55}")
    for name, cfg in PRESETS.items():
        w, f = test_stop_only(all_sessions[name], 'all', 'close', fb)
        target = f"{cfg['target_full']}/{cfg['target_failed']}"
        match = "✅" if w == cfg['target_full'] and f == cfg['target_failed'] else "❌"
        print(f"    {name:<13} {w:>6} {f:>6} {target:>12} {match:>8}")

# Fallback sweep for P80 from ALL, TOUCH
print(f"\n  --- Fallback sweep (Stop=TOUCH, P80 from ALL) ---")
for fb in [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.5, 2.0]:
    print(f"\n  Fallback={fb}%:")
    print(f"  {'Preset':<15} {'Wins':>6} {'Fails':>6} {'Target':>12} {'Match':>8}")
    print(f"  {'-'*55}")
    for name, cfg in PRESETS.items():
        w, f = test_stop_only(all_sessions[name], 'all', 'touch', fb)
        target = f"{cfg['target_full']}/{cfg['target_failed']}"
        match = "✅" if w == cfg['target_full'] and f == cfg['target_failed'] else "❌"
        print(f"    {name:<13} {w:>6} {f:>6} {target:>12} {match:>8}")