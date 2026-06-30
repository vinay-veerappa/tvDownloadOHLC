"""
Comprehensive theory grid for Gunship classification matching.
Tests many combinations of rules to find what matches the target FULL/FAIL counts.
"""
import pandas as pd
import numpy as np
import pytz
from itertools import product

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

def compute_derived(row):
    """Precompute EV hit, fakeout, max MFE/MAE for a session."""
    bo_px = row['bo_px']
    side = row['side']
    or_high = row['or_high']
    or_low = row['or_low']
    
    ev_hits = []
    fakeout = False
    max_mfe_pct = 0.0
    max_mae_pct = 0.0
    
    for bar in row['bar_data']:
        # MFE/MAE in percent from BO px
        if side == 1:
            mfe_pct = (bar['high'] - bo_px) / bo_px * 100
            mae_pct = (bo_px - bar['low']) / bo_px * 100
            if bar['low'] < or_low:
                fakeout = True
        else:
            mfe_pct = (bo_px - bar['low']) / bo_px * 100
            mae_pct = (bar['high'] - bo_px) / bo_px * 100
            if bar['high'] > or_high:
                fakeout = True
        max_mfe_pct = max(max_mfe_pct, mfe_pct)
        max_mae_pct = max(max_mae_pct, mae_pct)
    
    return {
        'fakeout': fakeout,
        'max_mfe_pct': max_mfe_pct,
        'max_mae_pct': max_mae_pct,
    }

def classify_sessions(df_p, **params):
    """
    Generic classifier. Params:
    - ev_target_pct: float or None
    - ev_precedence: bool
    - stop_enabled: bool
    - stop_type: 'touch' or 'close'
    - stop_anchor: 'bo_px' or 'or_boundary'
    - p80_sample: 'all', 'wins', 'fails'
    - p80_pct: percentile to use (default 80)
    - fallback: cold-start value
    - fakeout_enabled: bool
    - win_requires_ev: bool (if True, only EV hit counts as win)
    - fail_requires_stop_or_fakeout: bool (if True, fail = stop or fakeout)
    """
    ev_target_pct = params.get('ev_target_pct', 0.30)
    ev_precedence = params.get('ev_precedence', True)
    stop_enabled = params.get('stop_enabled', True)
    stop_type = params.get('stop_type', 'touch')
    stop_anchor = params.get('stop_anchor', 'bo_px')
    p80_sample = params.get('p80_sample', 'all')
    p80_pct = params.get('p80_pct', 80)
    fallback = params.get('fallback', 0.5)
    fakeout_enabled = params.get('fakeout_enabled', True)
    win_requires_ev = params.get('win_requires_ev', False)
    fail_requires_stop_or_fakeout = params.get('fail_requires_stop_or_fakeout', True)
    
    results = []
    
    for side_val in [1, -1]:
        side_sessions = df_p[df_p['side'] == side_val].reset_index(drop=True)
        hist_mae_all = []
        hist_mae_wins = []
        hist_mae_fails = []
        
        for i, row in side_sessions.iterrows():
            if p80_sample == 'all':
                hist = hist_mae_all
            elif p80_sample == 'wins':
                hist = hist_mae_wins
            elif p80_sample == 'fails':
                hist = hist_mae_fails
            
            p80 = fallback if len(hist) == 0 else p_nearest(hist, p80_pct)
            
            # EV target hit?
            ev_hit = False
            if ev_target_pct is not None:
                for bar in row['bar_data']:
                    if row['side'] == 1 and bar['high'] >= row['bo_px'] * (1 + ev_target_pct / 100):
                        ev_hit = True; break
                    elif row['side'] == -1 and bar['low'] <= row['bo_px'] * (1 - ev_target_pct / 100):
                        ev_hit = True; break
            
            # Stop-loss hit?
            stop_hit = False
            if stop_enabled and (not ev_precedence or not ev_hit):
                if stop_anchor == 'bo_px':
                    invalid_px = row['bo_px'] * (1 - row['side'] * p80 / 100)
                else:  # or_boundary
                    invalid_px = row['or_low'] if row['side'] == 1 else row['or_high']
                
                for bar in row['bar_data']:
                    if stop_type == 'close':
                        if row['side'] == 1 and bar['close'] <= invalid_px:
                            stop_hit = True; break
                        elif row['side'] == -1 and bar['close'] >= invalid_px:
                            stop_hit = True; break
                    else:  # touch
                        if row['side'] == 1 and bar['low'] <= invalid_px:
                            stop_hit = True; break
                        elif row['side'] == -1 and bar['high'] >= invalid_px:
                            stop_hit = True; break
            
            # Fakeout
            fakeout = False
            if fakeout_enabled and (not ev_precedence or not ev_hit):
                fakeout = row['fakeout']
            
            # Classify
            if win_requires_ev:
                won = ev_hit
            else:
                won = ev_hit or not (stop_hit or fakeout)
            
            if fail_requires_stop_or_fakeout:
                failed = stop_hit or fakeout
            else:
                failed = not won
            
            results.append({
                'date': row['date'], 'side': row['side'],
                'won': won, 'failed': failed,
                'ev_hit': ev_hit, 'stop_hit': stop_hit, 'fakeout': fakeout,
                'p80': p80,
            })
            
            # Commit MAE to history (always anchored at BO px for now)
            mae_bo = row['max_mae_pct']
            hist_mae_all.append(mae_bo)
            if won:
                hist_mae_wins.append(mae_bo)
            else:
                hist_mae_fails.append(mae_bo)
    
    res = pd.DataFrame(results)
    return int(res['won'].sum()), int(res['failed'].sum()), res

# Build sessions
all_sessions = {}
for name, cfg in PRESETS.items():
    df = build_sessions(cfg)
    derived = df.apply(compute_derived, axis=1, result_type='expand')
    df = pd.concat([df, derived], axis=1)
    all_sessions[name] = df

# Theory grid
param_grid = {
    'ev_target_pct': [None, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50],
    'ev_precedence': [True, False],
    'stop_enabled': [True, False],
    'stop_type': ['touch', 'close'],
    'stop_anchor': ['bo_px', 'or_boundary'],
    'p80_sample': ['all', 'wins', 'fails'],
    'p80_pct': [75, 80, 85, 90],
    'fallback': [0.3, 0.5, 0.7, 1.0],
    'fakeout_enabled': [True, False],
    'win_requires_ev': [False],
    'fail_requires_stop_or_fakeout': [True, False],
}

# Reduce grid size by fixing some params per sweep
sweeps = []

# Sweep 1: Is there a universal rule with no fakeout?
sweeps.append({
    'name': 'No fakeout rule',
    'fixed': {'fakeout_enabled': False, 'ev_precedence': True, 'stop_enabled': True, 'stop_type': 'touch', 'stop_anchor': 'bo_px', 'p80_sample': 'all', 'p80_pct': 80, 'fallback': 0.5, 'win_requires_ev': False, 'fail_requires_stop_or_fakeout': True},
    'vary': {'ev_target_pct': param_grid['ev_target_pct']},
})

# Sweep 2: No stop-loss, only fakeout
sweeps.append({
    'name': 'No stop-loss, only fakeout',
    'fixed': {'stop_enabled': False, 'ev_precedence': True, 'fakeout_enabled': True, 'p80_sample': 'all', 'p80_pct': 80, 'fallback': 0.5, 'win_requires_ev': False, 'fail_requires_stop_or_fakeout': True},
    'vary': {'ev_target_pct': param_grid['ev_target_pct']},
})

# Sweep 3: EV only (no stop, no fakeout)
sweeps.append({
    'name': 'EV target only',
    'fixed': {'stop_enabled': False, 'fakeout_enabled': False, 'p80_sample': 'all', 'p80_pct': 80, 'fallback': 0.5, 'win_requires_ev': False, 'fail_requires_stop_or_fakeout': False},
    'vary': {'ev_target_pct': param_grid['ev_target_pct'], 'ev_precedence': [True, False]},
})

# Sweep 4: Stop + fakeout, vary EV target and precedence
sweeps.append({
    'name': 'Stop + fakeout, vary EV target',
    'fixed': {'stop_enabled': True, 'fakeout_enabled': True, 'stop_type': 'touch', 'stop_anchor': 'bo_px', 'p80_sample': 'all', 'p80_pct': 80, 'fallback': 0.5, 'win_requires_ev': False, 'fail_requires_stop_or_fakeout': True},
    'vary': {'ev_target_pct': param_grid['ev_target_pct'], 'ev_precedence': [True, False]},
})

# Sweep 5: Stop + fakeout, vary stop anchor and type
sweeps.append({
    'name': 'Vary stop anchor/type',
    'fixed': {'stop_enabled': True, 'fakeout_enabled': True, 'ev_target_pct': 0.30, 'ev_precedence': True, 'p80_sample': 'all', 'p80_pct': 80, 'fallback': 0.5, 'win_requires_ev': False, 'fail_requires_stop_or_fakeout': True},
    'vary': {'stop_type': ['touch', 'close'], 'stop_anchor': ['bo_px', 'or_boundary']},
})

# Sweep 6: Stop + fakeout, vary P80 source and percentile
sweeps.append({
    'name': 'Vary P80 source/percentile',
    'fixed': {'stop_enabled': True, 'fakeout_enabled': True, 'ev_target_pct': 0.30, 'ev_precedence': True, 'stop_type': 'touch', 'stop_anchor': 'bo_px', 'fallback': 0.5, 'win_requires_ev': False, 'fail_requires_stop_or_fakeout': True},
    'vary': {'p80_sample': ['all', 'wins', 'fails'], 'p80_pct': [75, 80, 85, 90]},
})

# Sweep 7: Stop + fakeout, vary fallback
sweeps.append({
    'name': 'Vary fallback',
    'fixed': {'stop_enabled': True, 'fakeout_enabled': True, 'ev_target_pct': 0.30, 'ev_precedence': True, 'stop_type': 'touch', 'stop_anchor': 'bo_px', 'p80_sample': 'all', 'p80_pct': 80, 'win_requires_ev': False, 'fail_requires_stop_or_fakeout': True},
    'vary': {'fallback': [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.5, 2.0]},
})

# Sweep 8: Close-based fakeout (instead of wick)
def close_fakeout(row):
    for bar in row['bar_data']:
        if row['side'] == 1 and bar['close'] < row['or_low']:
            return True
        elif row['side'] == -1 and bar['close'] > row['or_high']:
            return True
    return False

for name, df in all_sessions.items():
    df['fakeout_close'] = df.apply(close_fakeout, axis=1)

# Sweep 8: close-based fakeout
sweeps.append({
    'name': 'Close-based fakeout',
    'fixed': {'stop_enabled': True, 'fakeout_enabled': True, 'ev_target_pct': 0.30, 'ev_precedence': True, 'stop_type': 'touch', 'stop_anchor': 'bo_px', 'p80_sample': 'all', 'p80_pct': 80, 'fallback': 0.5, 'win_requires_ev': False, 'fail_requires_stop_or_fakeout': True},
    'vary': {'fakeout_type': ['close', 'wick']},
})

print("=" * 100)
print("GUNSHIP CLASSIFICATION THEORY GRID")
print("=" * 100)

all_matches = []

for sweep in sweeps:
    print(f"\n### {sweep['name']} ###")
    vary_keys = list(sweep['vary'].keys())
    vary_values = [sweep['vary'][k] for k in vary_keys]
    
    for combo in product(*vary_values):
        params = dict(sweep['fixed'])
        for k, v in zip(vary_keys, combo):
            params[k] = v
        
        # Handle fakeout_type specially
        fakeout_type = params.pop('fakeout_type', 'wick')
        
        row_parts = []
        all_match = True
        for name, cfg in PRESETS.items():
            df = all_sessions[name].copy()
            if fakeout_type == 'close':
                df['fakeout'] = df['fakeout_close']
            w, f, _ = classify_sessions(df, **params)
            target = f"{cfg['target_full']}/{cfg['target_failed']}"
            match = (w == cfg['target_full'] and f == cfg['target_failed'])
            if not match:
                all_match = False
            row_parts.append(f"{name}: {w}/{f} vs {target} {'MATCH' if match else 'x'}")
        
        param_str = ', '.join(f"{k}={v}" for k, v in zip(vary_keys, combo))
        status = "ALL MATCH" if all_match else ""
        print(f"  {param_str:<50} | {' | '.join(row_parts)} {status}")
        if all_match:
            all_matches.append((sweep['name'], params, combo))

print("\n" + "=" * 100)
print("ALL-MATCHING COMBINATIONS:")
print("=" * 100)
if all_matches:
    for sweep_name, params, combo in all_matches:
        print(f"  Sweep: {sweep_name}")
        print(f"  Params: {params}")
        print(f"  Combo: {combo}")
else:
    print("  No combination matched all 4 presets simultaneously.")
