"""
Rolling percentile verification: Process sessions chronologically.
Each session's levels are computed from ONLY prior sessions' history.
The LAST session's levels (June 26) are compared against the Gunship's drawn levels.

This matches how Pine Script works:
- hist.bo_mae_bull accumulates session-by-session via f_commit_daily
- array.percentile_nearest_rank is called on the accumulated history
- Cold-start fallback: 0.5% MAE, 0.15% pullback when history is empty

Classification (for determining wins/fakes sample):
- The DNL Pine Script uses: R2 (fakeout) > EV target (win) > P80 MAE (loss)
- But we discovered the Gunship uses a different rule
- For rolling levels, we need to classify each session to know which
  history arrays to add it to (wins, fakes, etc.)
- We'll use R3 (any 5m touch beyond opp OR) as the fail rule, since that
  was the closest match in cross-preset validation
- Fakeout = R2 (any 5m close beyond opp OR)
- Win = NOT R3 fail
- Fail = R3 fail

Levels to verify (non-Red only):
  PB Entry:       P25 MAE from breakout (BO px anchor, MAE direction)
  BO Cashflow:    P20 MFE from breakout (BO px anchor, MFE direction)
  BO Inval:       P80 MAE from breakout (BO px anchor, MAE direction)
  Pivot:          P50 MFE of fakes (BO px anchor, MFE direction)
  BO Confirm:     P75 MFE of fakes (BO px anchor, MFE direction)
  Reversal Zone:  P25-P50 MAE of fakes (BO px anchor, MAE direction)
  Max Reversal:   P90 MAE of fakes (BO px anchor, MAE direction)

For each level, test multiple sample populations:
  ALL: all prior same-side sessions
  WINS: prior same-side sessions that didn't fail (not R3)
  FAILS: prior same-side sessions that failed (R3)
  FAKES: prior same-side sessions that are fakeouts (R2)
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
                    'target_n': 73, 'crosses_midnight': False, 'start_date': '2026-03-13'},
    'MO Break':    {'or_start': 930,  'or_end': 935,  'cutoff': 1200, 'days': '23456',
                    'target_n': 74, 'crosses_midnight': False, 'start_date': '2026-03-12'},
    '1800 Break':  {'or_start': 1800, 'or_end': 1815, 'cutoff': 300,  'days': '12345',
                    'target_n': 75, 'crosses_midnight': True, 'start_date': '2026-03-12'},
    'Q1 Break':    {'or_start': 600,  'or_end': 830,  'cutoff': 1200, 'days': '23456',
                    'target_n': 73, 'crosses_midnight': False, 'start_date': '2026-03-12'},
}

# Gunship captured levels (for the LAST session = June 26)
GUNSHIP = {
    '1100 BO': {
        'bo_px': 29773.50, 'side': 1,
        'PB Entry': 29742.25, 'BO Cashflow': 29785.50, 'BO Inval': 29711.25,
        'Pivot': 29835.50, 'BO Confirm': 29888.50,
        'Reversal Zone': 29611.69, 'Max Reversal': 29346.84,
    },
    'MO Break': {
        'bo_px': 29785.00, 'side': 1,
        'PB Entry': 29767.84, 'BO Cashflow': 29882.68, 'BO Inval': 29698.40,
        'Pivot': 29835.50, 'BO Confirm': 29888.50,
        'Reversal Zone': 29611.69, 'Max Reversal': 29346.84,
    },
    '1800 Break': {
        'bo_px': 29558.75, 'side': 1,
        'PB Entry': 29549.17, 'BO Cashflow': 29637.80, 'BO Inval': 29522.76,
        'Pivot': 29614.61, 'BO Confirm': 29677.51,
        'Reversal Zone': 29442.70, 'Max Reversal': 29231.37,
    },
    'Q1 Break': {
        'bo_px': 29643.25, 'side': -1,
        'PB Entry': 29690.67, 'BO Cashflow': 29567.70, 'BO Inval': 29796.00,
        'Pivot': 29559.16, 'BO Confirm': 29530.73,
        'Reversal Zone': 29833.64, 'Max Reversal': 30013.53,
    },
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
            mfe = ((post_bo_5m['high'].max() - bo_px) / bo_px) * 100
            mae_bo = ((bo_px - post_bo_5m['low'].min()) / bo_px) * 100
        else:
            mfe = ((bo_px - post_bo_5m['low'].min()) / bo_px) * 100
            mae_bo = ((post_bo_5m['high'].max() - bo_px) / bo_px) * 100
        
        close_at_cutoff = data_5m['close'].iloc[-1]
        r2_fail = False
        for idx, row in post_bo_5m.iterrows():
            if bo_side == 1 and row['close'] < or_low:
                r2_fail = True; break
            elif bo_side == -1 and row['close'] > or_high:
                r2_fail = True; break
        r3_fail = False
        for idx, row in post_bo_5m.iterrows():
            if bo_side == 1 and row['low'] < or_low:
                r3_fail = True; break
            elif bo_side == -1 and row['high'] > or_high:
                r3_fail = True; break
        
        sessions.append({
            'date': date, 'side': bo_side, 'or_high': or_high, 'or_low': or_low,
            'bo_px': bo_px, 'mfe': mfe, 'mae_bo': mae_bo,
            'r2_fail': r2_fail, 'r3_fail': r3_fail,
        })
    return pd.DataFrame(sessions)

# Build sessions for all presets
all_sessions = {}
for name, cfg in PRESETS.items():
    all_sessions[name] = build_sessions(cfg)
    print(f"  {name:15s}: N={len(all_sessions[name])} (target {cfg['target_n']})")
print()

# Rolling verification for each preset
for preset_name, gunship in GUNSHIP.items():
    df_p = all_sessions[preset_name]
    side = gunship['side']
    bo_px_last = gunship['bo_px']  # Last session's BO px
    
    # Filter to same-side sessions only (bull levels use bull history, bear uses bear)
    same_side = df_p[df_p['side'] == side].reset_index(drop=True)
    
    print("=" * 90)
    print(f"{preset_name} (side={'bull' if side==1 else 'bear'}, last BO px={bo_px_last})")
    print(f"  Same-side sessions: {len(same_side)}")
    print(f"  Gunship levels: PB={gunship['PB Entry']:.2f}, CF={gunship['BO Cashflow']:.2f}, "
          f"Inval={gunship['BO Inval']:.2f}, Pivot={gunship['Pivot']:.2f}, "
          f"Confirm={gunship['BO Confirm']:.2f}")
    print(f"  RevZone={gunship['Reversal Zone']:.2f}, MaxRev={gunship['Max Reversal']:.2f}")
    print("=" * 90)
    
    # Rolling history arrays (same-side only)
    hist_mae_all = []     # MAE of all prior same-side sessions
    hist_mae_wins = []    # MAE of prior same-side winning sessions (not R3 fail)
    hist_mae_fails = []   # MAE of prior same-side failed sessions (R3 fail)
    hist_mae_fakes = []   # MAE of prior same-side fakeout sessions (R2 fail)
    hist_mfe_all = []     # MFE of all prior same-side sessions
    hist_mfe_wins = []    # MFE of prior same-side winning sessions
    hist_mfe_fakes = []   # MFE of prior same-side fakeout sessions
    
    # Process sessions chronologically
    for i, row in same_side.iterrows():
        # This is session i. Its levels are computed from sessions 0..i-1.
        # After processing, its MAE/MFE is committed to history.
        
        # If this is the LAST session, compute and store levels
        is_last = (i == len(same_side) - 1)
        
        if is_last:
            # Compute levels from rolling history (sessions 0..i-1)
            levels = {}
            
            # Helper: get percentile or fallback
            def get_pct(arr, pct, fallback):
                if len(arr) == 0: return fallback
                return p_nearest(arr, pct)
            
            # PB Entry: P25 MAE from breakout
            # Test: ALL, WINS, FAILS
            for label, hist in [('ALL', hist_mae_all), ('Wins', hist_mae_wins), ('Fails', hist_mae_fails)]:
                p25 = get_pct(hist, 25, 0.15)  # cold-start fallback 0.15%
                price = bo_px_last * (1 - side * p25 / 100)
                g = gunship['PB Entry']
                delta = price - g
                match = "✅" if abs(delta) < 2.0 else "❌"
                print(f"  PB Entry  P25 MAE ({label:>5}): {p25:.3f}% → {price:.2f} (Gunship={g:.2f}, Δ={delta:+.2f}) {match}")
            
            # BO Cashflow: P20 MFE from breakout
            for label, hist in [('ALL', hist_mfe_all), ('Wins', hist_mfe_wins), ('Fakes', hist_mfe_fakes)]:
                p20 = get_pct(hist, 20, 0.10)
                price = bo_px_last * (1 + side * p20 / 100)
                g = gunship['BO Cashflow']
                delta = price - g
                match = "✅" if abs(delta) < 2.0 else "❌"
                print(f"  BO Cashflow P20 MFE ({label:>5}): {p20:.3f}% → {price:.2f} (Gunship={g:.2f}, Δ={delta:+.2f}) {match}")
            
            # BO Inval: P80 MAE from breakout
            for label, hist in [('ALL', hist_mae_all), ('Wins', hist_mae_wins), ('Fails', hist_mae_fails)]:
                p80 = get_pct(hist, 80, 0.50)
                price = bo_px_last * (1 - side * p80 / 100)
                g = gunship['BO Inval']
                delta = price - g
                match = "✅" if abs(delta) < 2.0 else "❌"
                print(f"  BO Inval  P80 MAE ({label:>5}): {p80:.3f}% → {price:.2f} (Gunship={g:.2f}, Δ={delta:+.2f}) {match}")
            
            # Pivot: P50 MFE of fakes
            for label, hist in [('Fakes', hist_mfe_fakes), ('ALL', hist_mfe_all), ('Wins', hist_mfe_wins)]:
                p50 = get_pct(hist, 50, 0.10)
                price = bo_px_last * (1 + side * p50 / 100)
                g = gunship['Pivot']
                delta = price - g
                match = "✅" if abs(delta) < 2.0 else "❌"
                print(f"  Pivot     P50 MFE ({label:>5}): {p50:.3f}% → {price:.2f} (Gunship={g:.2f}, Δ={delta:+.2f}) {match}")
            
            # BO Confirm: P75 MFE of fakes
            for label, hist in [('Fakes', hist_mfe_fakes), ('ALL', hist_mfe_all), ('Wins', hist_mfe_wins)]:
                p75 = get_pct(hist, 75, 0.15)
                price = bo_px_last * (1 + side * p75 / 100)
                g = gunship['BO Confirm']
                delta = price - g
                match = "✅" if abs(delta) < 2.0 else "❌"
                print(f"  BO Confirm P75 MFE ({label:>5}): {p75:.3f}% → {price:.2f} (Gunship={g:.2f}, Δ={delta:+.2f}) {match}")
            
            # Reversal Zone: P25-P50 MAE of fakes (MAE direction = opposite of breakout)
            g_rev = gunship['Reversal Zone']
            print(f"  Reversal Zone (Gunship={g_rev:.2f}):")
            for pct in [25, 50, 75]:
                for label, hist in [('Fakes', hist_mae_fakes), ('ALL', hist_mae_all), ('Fails', hist_mae_fails)]:
                    p = get_pct(hist, pct, 0.30)
                    price = bo_px_last * (1 - side * p / 100)
                    delta = price - g_rev
                    match = "✅" if abs(delta) < 2.0 else "❌"
                    print(f"    P{pct} MAE ({label:>5}): {p:.3f}% → {price:.2f} (Δ={delta:+.2f}) {match}")
            
            # Max Reversal: P90 MAE of fakes
            g_maxrev = gunship['Max Reversal']
            for label, hist in [('Fakes', hist_mae_fakes), ('ALL', hist_mae_all), ('Fails', hist_mae_fails)]:
                p90 = get_pct(hist, 90, 0.50)
                price = bo_px_last * (1 - side * p90 / 100)
                delta = price - g_maxrev
                match = "✅" if abs(delta) < 2.0 else "❌"
                print(f"  Max Rev   P90 MAE ({label:>5}): {p90:.3f}% → {price:.2f} (Gunship={g_maxrev:.2f}, Δ={delta:+.2f}) {match}")
            
            print(f"\n  Rolling history sizes: ALL={len(hist_mae_all)}, Wins={len(hist_mae_wins)}, "
                  f"Fails={len(hist_mae_fails)}, Fakes={len(hist_mae_fakes)}")
        
        # Commit this session to history
        is_win = not row['r3_fail']
        is_fake = row['r2_fail']
        is_fail = row['r3_fail']
        
        hist_mae_all.append(row['mae_bo'])
        hist_mfe_all.append(row['mfe'])
        if is_win:
            hist_mae_wins.append(row['mae_bo'])
            hist_mfe_wins.append(row['mfe'])
        if is_fail:
            hist_mae_fails.append(row['mae_bo'])
        if is_fake:
            hist_mae_fakes.append(row['mae_bo'])
            hist_mfe_fakes.append(row['mfe'])
    
    print()