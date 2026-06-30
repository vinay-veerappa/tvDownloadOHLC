"""
Test: FAIL = (R2 AND NOT EV_hit) OR P80 CLOSE stop
      WIN = NOT failed

This matches the DNL Pine Script precedence:
  1. If EV target hit → WIN (takes precedence over R2)
  2. If R2 (close beyond opp OR) and EV NOT hit → FAIL (fakeout)
  3. If P80 stop hit → FAIL (loss)
  4. Otherwise → WIN (didn't fail by cutoff)

The key insight: R2 is only a fail if the session DIDN'T hit the EV target first.
If the EV target was hit, the session is a WIN even if price later crossed the opposite OR.
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

def classify(df_p, p80_sample, stop_type, fallback, ev_pct=0.30):
    """
    FAIL = (R2 AND NOT EV_hit) OR P80 stop
    WIN = NOT failed
    
    EV target hit = any 5m bar high/low TOUCHES the EV target price
    R2 = any 5m bar CLOSE beyond opposite OR
    P80 stop = any 5m bar CLOSE reaches invalidation level
    """
    results = []
    for side_val in [1, -1]:
        side_sessions = df_p[df_p['side'] == side_val].reset_index(drop=True)
        hist_wins = []
        hist_all = []
        
        for i, row in side_sessions.iterrows():
            # P80 from rolling history
            if p80_sample == 'wins':
                hist = hist_wins
            else:
                hist = hist_all
            
            p80 = p_nearest(hist, 80) if len(hist) > 0 else fallback
            target_px = row['bo_px'] * (1 + row['side'] * ev_pct / 100)
            invalid_px = row['bo_px'] * (1 - row['side'] * p80 / 100)
            
            # Process bars in order — check EV hit, R2, and stop
            ev_hit = False
            r2_fail = False
            stop_hit = False
            
            for bar in row['bar_data']:
                # Check EV target hit (TOUCH)
                if not ev_hit:
                    if row['side'] == 1 and bar['high'] >= target_px:
                        ev_hit = True
                    elif row['side'] == -1 and bar['low'] <= target_px:
                        ev_hit = True
                
                # Check R2 (CLOSE beyond opp OR)
                if not r2_fail:
                    if row['side'] == 1 and bar['close'] < row['or_low']:
                        r2_fail = True
                    elif row['side'] == -1 and bar['close'] > row['or_high']:
                        r2_fail = True
                
                # Check P80 stop (CLOSE reaches invalidation)
                if not stop_hit:
                    if stop_type == 'close':
                        if row['side'] == 1 and bar['close'] <= invalid_px:
                            stop_hit = True
                        elif row['side'] == -1 and bar['close'] >= invalid_px:
                            stop_hit = True
                    else:  # touch
                        if row['side'] == 1 and bar['low'] <= invalid_px:
                            stop_hit = True
                        elif row['side'] == -1 and bar['high'] >= invalid_px:
                            stop_hit = True
            
            # Classification: FAIL = (R2 AND NOT EV_hit) OR stop_hit
            failed = (r2_fail and not ev_hit) or stop_hit
            won = not failed
            
            results.append({
                'date': row['date'], 'side': row['side'], 'won': won,
                'ev_hit': ev_hit, 'r2_fail': r2_fail, 'stop_hit': stop_hit,
                'p80_mae': p80, 'mae_bo': row['mae_bo'],
            })
            
            # Commit to history
            hist_all.append(row['mae_bo'])
            if won:
                hist_wins.append(row['mae_bo'])
    
    res = pd.DataFrame(results).sort_values('date').reset_index(drop=True)
    return res['won'].sum(), (~res['won']).sum(), res

# Build sessions
all_sessions = {}
for name, cfg in PRESETS.items():
    all_sessions[name] = build_sessions(cfg)

# Test the main rule: FAIL = (R2 AND NOT EV_hit) OR P80 CLOSE stop
print("=" * 90)
print("RULE: FAIL = (R2 AND NOT EV_hit) OR P80 CLOSE stop")
print("      WIN = NOT failed")
print("=" * 90)

for p80_sample in ['all', 'wins']:
    for stop_type in ['close', 'touch']:
        for fb in [0.5]:
            print(f"\n  P80 from {p80_sample.upper()}, Stop={stop_type.upper()}, fb={fb}%:")
            print(f"  {'Preset':<15} {'Wins':>6} {'Fails':>6} {'Target':>12} {'Match':>8}")
            print(f"  {'-'*55}")
            for name, cfg in PRESETS.items():
                w, f, res = classify(all_sessions[name], p80_sample, stop_type, fb)
                target = f"{cfg['target_full']}/{cfg['target_failed']}"
                match = "✅" if w == cfg['target_full'] and f == cfg['target_failed'] else "❌"
                print(f"    {name:<13} {w:>6} {f:>6} {target:>12} {match:>8}")

# Fallback sweep for P80 from ALL, CLOSE
print(f"\n  --- Fallback sweep (P80 from ALL, CLOSE) ---")
for fb in [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
    print(f"\n  Fallback={fb}%:")
    print(f"  {'Preset':<15} {'Wins':>6} {'Fails':>6} {'Target':>12} {'Match':>8}")
    print(f"  {'-'*55}")
    for name, cfg in PRESETS.items():
        w, f, res = classify(all_sessions[name], 'all', 'close', fb)
        target = f"{cfg['target_full']}/{cfg['target_failed']}"
        match = "✅" if w == cfg['target_full'] and f == cfg['target_failed'] else "❌"
        print(f"    {name:<13} {w:>6} {f:>6} {target:>12} {match:>8}")

# Fallback sweep for P80 from ALL, TOUCH
print(f"\n  --- Fallback sweep (P80 from ALL, TOUCH) ---")
for fb in [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
    print(f"\n  Fallback={fb}%:")
    print(f"  {'Preset':<15} {'Wins':>6} {'Fails':>6} {'Target':>12} {'Match':>8}")
    print(f"  {'-'*55}")
    for name, cfg in PRESETS.items():
        w, f, res = classify(all_sessions[name], 'all', 'touch', fb)
        target = f"{cfg['target_full']}/{cfg['target_failed']}"
        match = "✅" if w == cfg['target_full'] and f == cfg['target_failed'] else "❌"
        print(f"    {name:<13} {w:>6} {f:>6} {target:>12} {match:>8}")

# Show detailed for best config
print("\n" + "=" * 90)
print("DETAILED: All presets (P80 from ALL, CLOSE, fb=0.5%)")
print("=" * 90)
for name, cfg in PRESETS.items():
    w, f, res = classify(all_sessions[name], 'all', 'close', 0.5)
    match = "✅" if w == cfg['target_full'] and f == cfg['target_failed'] else "❌"
    print(f"\n  {name}: {w}/{f} (target {cfg['target_full']}/{cfg['target_failed']}) {match}")
    print(f"  {'Date':<12} {'Side':>4} {'Result':>6} {'EV':>4} {'R2':>4} {'Stop':>5} {'P80%':>7} {'MAE%':>7}")
    for _, r in res.iterrows():
        result = 'FULL' if r['won'] else 'FAIL'
        print(f"  {str(r['date']):<12} {'bull' if r['side']==1 else 'bear':>4} {result:>6} "
              f"{'Y' if r['ev_hit'] else 'N':>4} {'Y' if r['r2_fail'] else 'N':>4} "
              f"{'Y' if r['stop_hit'] else 'N':>5} {r['p80_mae']:>6.3f}% {r['mae_bo']:>6.3f}%")