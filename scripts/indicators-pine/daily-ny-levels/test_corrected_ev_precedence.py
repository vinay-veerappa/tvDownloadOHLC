"""
Test corrected EV precedence: EV target checked every bar, fakeout/stop only lock if EV never hits.
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
        
        bar_data = []
        for idx, row in post_bo_5m.iterrows():
            bar_data.append({'high': row['high'], 'low': row['low'], 'close': row['close']})
        
        sessions.append({
            'date': date, 'side': bo_side, 'or_high': or_high, 'or_low': or_low,
            'bo_px': bo_px, 'bar_data': bar_data,
        })
    return pd.DataFrame(sessions)

def classify_corrected_ev_precedence(df_p, p80_sample='all', stop_type='touch', fallback=0.5, ev_target_pct=0.30):
    """
    Corrected Pine logic:
    - On every bar until outcome decided, check EV target first
    - If EV target hits at any point -> WIN
    - If session ends without EV hit, check if stop or fakeout occurred -> FAIL
    - P80 from rolling history
    """
    results = []
    
    for side_val in [1, -1]:
        side_sessions = df_p[df_p['side'] == side_val].reset_index(drop=True)
        hist_mae_all = []
        hist_mae_wins = []
        hist_mae_fails = []
        
        for i, row in side_sessions.iterrows():
            hist = hist_mae_all if p80_sample == 'all' else (hist_mae_wins if p80_sample == 'wins' else hist_mae_fails)
            p80 = fallback if len(hist) == 0 else p_nearest(hist, 80)
            
            invalid_px = row['bo_px'] * (1 - row['side'] * p80 / 100)
            target_px = row['bo_px'] * (1 + row['side'] * ev_target_pct / 100)
            
            ev_hit = any(
                (row['side'] == 1 and bar['high'] >= target_px) or
                (row['side'] == -1 and bar['low'] <= target_px)
                for bar in row['bar_data']
            )
            
            stop_hit = False
            fakeout = False
            if ev_hit:
                won = True; failed = False
            else:
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
                
                if not stop_hit:
                    fakeout = any(
                        (row['side'] == 1 and bar['low'] < row['or_low']) or
                        (row['side'] == -1 and bar['high'] > row['or_high'])
                        for bar in row['bar_data']
                    )
                
                won = False
                failed = stop_hit or fakeout
            
            results.append({
                'date': row['date'], 'side': row['side'],
                'won': won, 'failed': failed,
                'ev_hit': ev_hit, 'stop_hit': stop_hit, 'fakeout': fakeout,
                'p80': p80,
            })
            
            if row['side'] == 1:
                mae_bo = max(0, (row['bo_px'] - min(b['low'] for b in row['bar_data'])) / row['bo_px'] * 100)
            else:
                mae_bo = max(0, (max(b['high'] for b in row['bar_data']) - row['bo_px']) / row['bo_px'] * 100)
            
            hist_mae_all.append(mae_bo)
            if won:
                hist_mae_wins.append(mae_bo)
            else:
                hist_mae_fails.append(mae_bo)
    
    res = pd.DataFrame(results)
    return int(res['won'].sum()), int(res['failed'].sum()), res

all_sessions = {}
for name, cfg in PRESETS.items():
    all_sessions[name] = build_sessions(cfg)

print("=" * 100)
print("CORRECTED EV PRECEDENCE (EV can override at any bar)")
print("=" * 100)
for stop_type in ['touch', 'close']:
    for p80_sample in ['all', 'wins', 'fails']:
        print(f"\nStop={stop_type.upper()}, P80 from {p80_sample.upper()}:")
        print(f"  {'Preset':<15} {'Wins':>6} {'Fails':>6} {'Target':>12} {'Match':>8}")
        for name, cfg in PRESETS.items():
            w, f, _ = classify_corrected_ev_precedence(all_sessions[name], p80_sample, stop_type, 0.5, 0.30)
            target = f"{cfg['target_full']}/{cfg['target_failed']}"
            match = "MATCH" if w == cfg['target_full'] and f == cfg['target_failed'] else "x"
            print(f"    {name:<13} {w:>6} {f:>6} {target:>12} {match:>8}")

# Also test with no fakeout rule under corrected EV precedence
print("\n" + "=" * 100)
print("NO FAKEOUT + CORRECTED EV PRECEDENCE")
print("=" * 100)
for ev_target_pct in [None, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50]:
    print(f"\nEV target={ev_target_pct}:")
    print(f"  {'Preset':<15} {'Wins':>6} {'Fails':>6} {'Target':>12} {'Match':>8}")
    for name, cfg in PRESETS.items():
        df = all_sessions[name].copy()
        # Override fakeout to False for all sessions
        df['or_high'] = df['or_high'] * 100
        df['or_low'] = df['or_low'] / 100
        w, f, _ = classify_corrected_ev_precedence(df, 'all', 'touch', 0.5, ev_target_pct if ev_target_pct else 0.0)
        target = f"{cfg['target_full']}/{cfg['target_failed']}"
        match = "MATCH" if w == cfg['target_full'] and f == cfg['target_failed'] else "x"
        print(f"    {name:<13} {w:>6} {f:>6} {target:>12} {match:>8}")
