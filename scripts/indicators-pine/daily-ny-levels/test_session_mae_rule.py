"""
Test Session MAE from OR boundary with various percentiles.
This mirrors the older verified hypothesis from repo memory.
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
        
        # Compute session MAE from OR boundary
        if bo_side == 1:
            session_mae = (or_high - min(b['low'] for b in bar_data)) / or_high * 100
        else:
            session_mae = (max(b['high'] for b in bar_data) - or_low) / or_low * 100
        
        # R1: cutoff close beyond opposite OR boundary
        last_close = bar_data[-1]['close']
        r1_fail = (bo_side == 1 and last_close < or_low) or (bo_side == -1 and last_close > or_high)
        
        sessions.append({
            'date': date, 'side': bo_side, 'or_high': or_high, 'or_low': or_low,
            'bo_px': bo_px, 'bar_data': bar_data, 'session_mae': session_mae, 'r1_fail': r1_fail,
        })
    return pd.DataFrame(sessions)

all_sessions = {}
for name, cfg in PRESETS.items():
    all_sessions[name] = build_sessions(cfg)

def classify_session_mae_rule(df_p, pct=95, sample='all', stop_type='touch', anchor='or_boundary', ev_precedence=False, ev_target_pct=0.30):
    """
    FAIL = R1 (cutoff close beyond opposite OR) OR stop-loss hit
    Stop-loss = Session MAE percentile from OR boundary, TOUCH
    WIN = NOT failed
    """
    results = []
    
    for side_val in [1, -1]:
        side_sessions = df_p[df_p['side'] == side_val].reset_index(drop=True)
        hist_all = []
        hist_wins = []
        hist_fails = []
        
        for i, row in side_sessions.iterrows():
            if sample == 'all':
                hist = hist_all
            elif sample == 'wins':
                hist = hist_wins
            else:
                hist = hist_fails
            
            pval = 0.5 if len(hist) == 0 else p_nearest(hist, pct)
            
            if anchor == 'or_boundary':
                invalid_px = row['or_high'] * (1 - pval / 100) if row['side'] == 1 else row['or_low'] * (1 + pval / 100)
            else:
                invalid_px = row['bo_px'] * (1 - row['side'] * pval / 100)
            
            # EV target hit?
            target_px = row['bo_px'] * (1 + row['side'] * ev_target_pct / 100)
            ev_hit = any(
                (row['side'] == 1 and bar['high'] >= target_px) or
                (row['side'] == -1 and bar['low'] <= target_px)
                for bar in row['bar_data']
            )
            
            # R1 fail
            r1_fail = row['r1_fail']
            
            # Stop-loss
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
            
            if ev_precedence and ev_hit:
                won = True; failed = False
            else:
                failed = r1_fail or stop_hit
                won = not failed
            
            results.append({
                'date': row['date'], 'side': row['side'],
                'won': won, 'failed': failed,
                'r1_fail': r1_fail, 'stop_hit': stop_hit, 'ev_hit': ev_hit,
                'pval': pval,
            })
            
            hist_all.append(row['session_mae'])
            if won:
                hist_wins.append(row['session_mae'])
            else:
                hist_fails.append(row['session_mae'])
    
    res = pd.DataFrame(results)
    return int(res['won'].sum()), int(res['failed'].sum()), res

print("=" * 100)
print("SESSION MAE FROM OR BOUNDARY — percentile sweep")
print("=" * 100)

for pct in [75, 80, 85, 90, 95]:
    for sample in ['all', 'wins', 'fails']:
        for stop_type in ['touch', 'close']:
            for anchor in ['or_boundary', 'bo_px']:
                for ev_prec in [True, False]:
                    print(f"\nPct={pct}, Sample={sample}, Stop={stop_type}, Anchor={anchor}, EV_prec={ev_prec}:")
                    print(f"  {'Preset':<15} {'Wins':>6} {'Fails':>6} {'Target':>12} {'Match':>8}")
                    for name, cfg in PRESETS.items():
                        w, f, _ = classify_session_mae_rule(all_sessions[name], pct, sample, stop_type, anchor, ev_prec, 0.30)
                        target = f"{cfg['target_full']}/{cfg['target_failed']}"
                        match = "MATCH" if w == cfg['target_full'] and f == cfg['target_failed'] else "x"
                        print(f"    {name:<13} {w:>6} {f:>6} {target:>12} {match:>8}")
