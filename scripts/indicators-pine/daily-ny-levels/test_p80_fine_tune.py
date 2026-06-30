"""
Fine-tune P80 MAE from ALL breakouts, BO px anchor.
Test different percentiles and stop triggers.
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

def p_linear(series, p):
    if len(series) == 0: return np.nan
    return np.percentile(series, p, method='linear')

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

def classify_fine(df_p, pct=80, sample='all', stop_type='touch', anchor='bo_px', fallback=0.5, interp='nearest'):
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
            
            if len(hist) == 0:
                pval = fallback
            else:
                pval = p_nearest(hist, pct) if interp == 'nearest' else p_linear(hist, pct)
            
            if anchor == 'bo_px':
                invalid_px = row['bo_px'] * (1 - row['side'] * pval / 100)
            else:
                invalid_px = row['or_high'] * (1 - pval / 100) if row['side'] == 1 else row['or_low'] * (1 + pval / 100)
            
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
            
            results.append({'won': won, 'failed': failed})
            
            hist_all.append(row['bo_mae'])
            if won:
                hist_wins.append(row['bo_mae'])
            else:
                hist_fails.append(row['bo_mae'])
    
    res = pd.DataFrame(results)
    return int(res['won'].sum()), int(res['failed'].sum())

all_sessions = {}
for name, cfg in PRESETS.items():
    all_sessions[name] = build_sessions(cfg)

print("=" * 100)
print("FINE TUNE: P80 MAE from breakout, BO px anchor")
print("=" * 100)

for interp in ['nearest', 'linear']:
    for stop_type in ['touch', 'close']:
        for sample in ['all', 'wins', 'fails']:
            for anchor in ['bo_px', 'or_boundary']:
                print(f"\nInterp={interp.upper()}, Stop={stop_type.upper()}, Sample={sample.upper()}, Anchor={anchor}:")
                print(f"  {'Pct':<6} {'1100 BO':<12} {'MO Break':<12} {'1800 Break':<12} {'Q1 Break':<12}")
                for pct in [70, 75, 80, 85, 90, 95]:
                    row = []
                    for name, cfg in PRESETS.items():
                        w, f = classify_fine(all_sessions[name], pct, sample, stop_type, anchor, 0.5, interp)
                        match = "M" if w == cfg['target_full'] and f == cfg['target_failed'] else ""
                        row.append(f"{w}/{f}{match}")
                    print(f"  P{pct:<3} {row[0]:<12} {row[1]:<12} {row[2]:<12} {row[3]:<12}")

# Detailed percentile sweep for promising configs
print("\n" + "=" * 100)
print("DETAILED SWEEP: Sample=ALL, Anchor=BO_PX, Stop=TOUCH")
print("=" * 100)
print(f"  {'Pct':<6} {'1100 BO':<12} {'MO Break':<12} {'1800 Break':<12} {'Q1 Break':<12}")
for pct in range(60, 101):
    row = []
    for name, cfg in PRESETS.items():
        w, f = classify_fine(all_sessions[name], pct, 'all', 'touch', 'bo_px', 0.5, 'nearest')
        match = "✓" if w == cfg['target_full'] and f == cfg['target_failed'] else ""
        row.append(f"{w}/{f}{match}")
    # Only print rows with at least one match or near-match
    if any('✓' in r for r in row):
        print(f"  P{pct:<3} {row[0]:<12} {row[1]:<12} {row[2]:<12} {row[3]:<12}")
