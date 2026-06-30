"""
Test the CORRECTED DailyNYLevelsAnalytics classification rule with rolling P80.
Matches the Pine Script fixes applied 2026-06-29:
- Breakout: 1m CLOSE beyond OR (unchanged)
- EV target hit (WICK) takes FULL precedence over stop/fakeout
- P80 MAE invalidation (WICK) checked second
- Fakeout = WICK beyond opposite OR boundary checked third
- P80 MAE computed from ALL prior sessions (not wins-only)
- P80 MAE anchored at BO px (from breakout close)
- Cold-start fallback: 0.5%
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
        
        # Store 5m bar data for CLOSE-based stop-loss checking
        bar_data = []
        for idx, row in post_bo_5m.iterrows():
            bar_data.append({'high': row['high'], 'low': row['low'], 'close': row['close']})
        
        # R3: any 5m wick beyond opp OR (wick-based fakeout per user clarification)
        r3_fail = False
        for bar in bar_data:
            if bo_side == 1 and bar['low'] < or_low:
                r3_fail = True; break
            elif bo_side == -1 and bar['high'] > or_high:
                r3_fail = True; break
        
        # EV target hit (WICK-based, 0.30% from BO px)
        ev_target_pct = 0.30
        ev_hit = False
        for bar in bar_data:
            if bo_side == 1 and bar['high'] >= bo_px * (1 + ev_target_pct / 100):
                ev_hit = True; break
            elif bo_side == -1 and bar['low'] <= bo_px * (1 - ev_target_pct / 100):
                ev_hit = True; break
        
        sessions.append({
            'date': date, 'side': bo_side, 'or_high': or_high, 'or_low': or_low,
            'bo_px': bo_px, 'mae_bo': mae_bo,
            'r3_fail': r3_fail, 'ev_hit': ev_hit, 'bar_data': bar_data,
        })
    return pd.DataFrame(sessions)

def test_rolling_classification(df_p, p80_sample='all', stop_type='touch', fallback=0.5):
    """
    Rolling classification with corrected Pine Script logic:
    - Process sessions chronologically
    - For each session, compute P80 from prior history (default ALL sessions)
    - EV target hit (WICK) → FULL (takes precedence)
    - FAIL = stop-loss hit (WICK) OR fakeout (WICK beyond opposite OR)
    - WIN = NOT failed
    - After classification, commit MAE to history
    
    p80_sample: 'wins' = P80 from prior wins only
                'all' = P80 from all prior sessions (corrected default)
                'fails' = P80 from prior fails only
    stop_type: 'close' = 5m CLOSE reaches invalidation level
               'touch' = 5m HIGH/LOW reaches invalidation level (corrected default)
    fallback: cold-start P80 MAE value (default 0.5%)
    """
    results = []
    
    for side_val in [1, -1]:
        side_sessions = df_p[df_p['side'] == side_val].reset_index(drop=True)
        hist_mae_wins = []
        hist_mae_all = []
        hist_mae_fails = []
        
        for i, row in side_sessions.iterrows():
            # Compute P80 from rolling history
            if p80_sample == 'wins':
                hist = hist_mae_wins
            elif p80_sample == 'all':
                hist = hist_mae_all
            elif p80_sample == 'fails':
                hist = hist_mae_fails
            
            if len(hist) > 0:
                p80 = p_nearest(hist, 80)
            else:
                p80 = fallback
            
            # Compute invalidation level (BO px anchor)
            invalid_px = row['bo_px'] * (1 - row['side'] * p80 / 100)
            
            # 1. EV target hit takes precedence
            ev_hit = row['ev_hit']
            
            # 2. Check stop-loss hit (only if EV not hit)
            stop_hit = False
            if not ev_hit:
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
            
            # 3. Check fakeout (only if EV not hit)
            fakeout = False
            if not ev_hit:
                fakeout = row['r3_fail']
            
            # Classify
            failed = stop_hit or fakeout
            won = ev_hit or not failed
            
            results.append({
                'date': row['date'], 'side': row['side'],
                'won': won, 'failed': failed,
                'ev_hit': ev_hit, 'r3_fail': fakeout, 'stop_hit': stop_hit,
                'p80_mae': p80, 'mae_bo': row['mae_bo'],
            })
            
            # Commit to history
            hist_mae_all.append(row['mae_bo'])
            if won:
                hist_mae_wins.append(row['mae_bo'])
            else:
                hist_mae_fails.append(row['mae_bo'])
    
    res = pd.DataFrame(results).sort_values('date').reset_index(drop=True)
    wins = res['won'].sum()
    fails = res['failed'].sum()
    return wins, fails, res

# Build sessions
all_sessions = {}
for name, cfg in PRESETS.items():
    all_sessions[name] = build_sessions(cfg)

# Test all combinations
print("=" * 90)
print("ROLLING CLASSIFICATION: CORRECTED Pine logic (EV precedence, WICK fakeout/stop, P80 ALL)")
print("=" * 90)

for stop_type in ['touch', 'close']:
    for p80_sample in ['all', 'wins', 'fails']:
        print(f"\n  Stop={stop_type.upper()}, P80 from {p80_sample.upper()}, fallback=0.5%:")
        print(f"  {'Preset':<15} {'Wins':>6} {'Fails':>6} {'Target':>12} {'Match':>8}")
        print(f"  {'-'*55}")
        
        for name, cfg in PRESETS.items():
            df_p = all_sessions[name]
            w, f, res = test_rolling_classification(df_p, p80_sample, stop_type, 0.5)
            target = f"{cfg['target_full']}/{cfg['target_failed']}"
            match = "✅" if w == cfg['target_full'] and f == cfg['target_failed'] else "❌"
            print(f"    {name:<13} {w:>6} {f:>6} {target:>12} {match:>8}")

# Also test with different fallback values
print(f"\n  --- Fallback sweep (Stop=TOUCH, P80 from ALL) ---")
for fb in [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
    print(f"\n  Fallback={fb}%:")
    print(f"  {'Preset':<15} {'Wins':>6} {'Fails':>6} {'Target':>12} {'Match':>8}")
    print(f"  {'-'*55}")
    for name, cfg in PRESETS.items():
        df_p = all_sessions[name]
        w, f, res = test_rolling_classification(df_p, 'all', 'touch', fb)
        target = f"{cfg['target_full']}/{cfg['target_failed']}"
        match = "✅" if w == cfg['target_full'] and f == cfg['target_failed'] else "❌"
        print(f"    {name:<13} {w:>6} {f:>6} {target:>12} {match:>8}")

# Show detailed session-by-session for 1100 BO with corrected default config
print("\n" + "=" * 90)
print("DETAILED: 1100 BO (Stop=TOUCH, P80 from ALL, fallback=0.5%)")
print("=" * 90)
df_p = all_sessions['1100 BO']
w, f, res = test_rolling_classification(df_p, 'all', 'touch', 0.5)
print(f"  Total: {w} wins / {f} fails (target 55/18)")
print()
print(f"  {'Date':<12} {'Side':>4} {'Result':>6} {'EV':>3} {'R3':>3} {'Stop':>5} {'P80%':>7} {'MAE%':>7}")
for _, r in res.iterrows():
    result = 'FULL' if r['won'] else 'FAIL'
    print(f"  {str(r['date']):<12} {'bull' if r['side']==1 else 'bear':>4} {result:>6} "
          f"{'Y' if r['ev_hit'] else 'N':>3} {'Y' if r['r3_fail'] else 'N':>3} "
          f"{'Y' if r['stop_hit'] else 'N':>5} {r['p80_mae']:>6.3f}% {r['mae_bo']:>6.3f}%")