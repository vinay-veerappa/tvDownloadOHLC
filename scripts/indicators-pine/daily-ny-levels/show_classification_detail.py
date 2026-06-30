"""
Show detailed session-by-session for 1100 BO with the EXACT MATCH config:
  Stop=CLOSE, P80 from ALL, fallback=0.5%, no R2

Also show details for the other 3 presets to identify which sessions
are classified differently from the Gunship.
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
        
        # R2 for reference
        r2_fail = False
        for bar in bar_data:
            if bo_side == 1 and bar['close'] < or_low:
                r2_fail = True; break
            elif bo_side == -1 and bar['close'] > or_high:
                r2_fail = True; break
        
        sessions.append({
            'date': date, 'side': bo_side, 'or_high': or_high, 'or_low': or_low,
            'bo_px': bo_px, 'mae_bo': mae_bo, 'r2_fail': r2_fail, 'bar_data': bar_data,
        })
    return pd.DataFrame(sessions)

def classify_rolling(df_p, fallback=0.5):
    """P80 CLOSE stop ONLY, P80 from ALL, no R2."""
    results = []
    for side_val in [1, -1]:
        side_sessions = df_p[df_p['side'] == side_val].reset_index(drop=True)
        hist_all = []
        
        for i, row in side_sessions.iterrows():
            p80 = p_nearest(hist_all, 80) if len(hist_all) > 0 else fallback
            invalid_px = row['bo_px'] * (1 - row['side'] * p80 / 100)
            
            stop_hit = False
            for bar in row['bar_data']:
                if row['side'] == 1 and bar['close'] <= invalid_px:
                    stop_hit = True; break
                elif row['side'] == -1 and bar['close'] >= invalid_px:
                    stop_hit = True; break
            
            won = not stop_hit
            results.append({
                'date': row['date'], 'side': row['side'], 'won': won,
                'stop_hit': stop_hit, 'r2_fail': row['r2_fail'],
                'p80_mae': p80, 'mae_bo': row['mae_bo'],
                'invalid_px': invalid_px, 'bo_px': row['bo_px'],
            })
            hist_all.append(row['mae_bo'])
    
    return pd.DataFrame(results).sort_values('date').reset_index(drop=True)

# Build and classify all presets
for name, cfg in PRESETS.items():
    df_p = build_sessions(cfg)
    res = classify_rolling(df_p, 0.5)
    w = res['won'].sum()
    f = (~res['won']).sum()
    
    print("=" * 90)
    print(f"{name}: {w} wins / {f} fails (target {cfg['target_full']}/{cfg['target_failed']})")
    match = "✅ EXACT MATCH" if w == cfg['target_full'] and f == cfg['target_failed'] else f"❌ Δ={w-cfg['target_full']}/{f-cfg['target_failed']}"
    print(f"  {match}")
    print("=" * 90)
    
    # Show all sessions
    print(f"  {'Date':<12} {'Side':>4} {'Result':>6} {'Stop':>5} {'R2':>4} {'P80%':>7} {'MAE%':>7} {'BO px':>10} {'Invalid':>10}")
    for _, r in res.iterrows():
        result = 'FULL' if r['won'] else 'FAIL'
        print(f"  {str(r['date']):<12} {'bull' if r['side']==1 else 'bear':>4} {result:>6} "
              f"{'Y' if r['stop_hit'] else 'N':>5} {'Y' if r['r2_fail'] else 'N':>4} "
              f"{r['p80_mae']:>6.3f}% {r['mae_bo']:>6.3f}% {r['bo_px']:>10.2f} {r['invalid_px']:>10.2f}")
    print()