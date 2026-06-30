"""
Cross-preset validation v5: Test the EXACT DNL Pine Script rule.
From reading the code (L463-510):
  - Fakeout (outcome=2): R2 (any 5m close beyond opp OR) — checked FIRST, takes precedence
  - Win (outcome=1): EV target (0.30%) hit by TOUCH — checked second
  - Loss (outcome=-1): P80 MAE invalidation hit by TOUCH — checked third
  - Pending (outcome=0): none of the above

The invalidation uses ROLLING P80 BO MAE from wins, with fallback to ALL, then 0.5%.
The Gunship has 0 pending, so pending sessions must be resolved somehow.

Test: 
  A) Exact DNL rule with pending counted as pending
  B) Same but pending = fail (Gunship resolves all)
  C) Same but pending = win (Gunship counts unresolved as full)
"""
import pandas as pd
import numpy as np
import pytz

df_1m = pd.read_parquet('data/live/live_storage_-NQ.parquet')
df_1m['datetime'] = pd.to_datetime(df_1m['timestamp'], utc=True)
df_1m = df_1m.set_index('datetime')
df_1m = df_1m[['open', 'high', 'low', 'close', 'volume']].copy()

df_1m = df_1m[(df_1m.index >= '2026-03-16') & (df_1m.index < '2026-06-29')]
df_1m = df_1m[~df_1m.index.strftime('%Y-%m-%d').isin(['2026-05-25', '2026-06-19'])]

et = pytz.timezone('America/New_York')
df_1m['et_time'] = df_1m.index.tz_convert(et)
df_1m['et_hhmm'] = df_1m['et_time'].dt.hour * 100 + df_1m['et_time'].dt.minute
df_1m['et_dow'] = df_1m['et_time'].dt.dayofweek
df_1m['date'] = df_1m['et_time'].dt.date

df_5m = df_1m.resample('5min', label='left', closed='left').agg(
    {'open':'first', 'high':'max', 'low':'min', 'close':'last', 'volume':'sum'}).dropna()
df_5m['et_time'] = df_5m.index.tz_convert(et)
df_5m['et_hhmm'] = df_5m['et_time'].dt.hour * 100 + df_5m['et_time'].dt.minute
df_5m['et_dow'] = df_5m['et_time'].dt.dayofweek
df_5m['date'] = df_5m['et_time'].dt.date

def p_nearest(series, p):
    if len(series) == 0: return np.nan
    return np.percentile(series, p, method='nearest')

PRESETS = {
    '1100 BO':     {'or_start': 1100, 'or_end': 1115, 'cutoff': 1230, 'days': '23456',
                    'target_wins': 55, 'target_fails': 18, 'target_n': 73, 'crosses_midnight': False},
    'MO Break':    {'or_start': 930,  'or_end': 935,  'cutoff': 1200, 'days': '23456',
                    'target_wins': 32, 'target_fails': 42, 'target_n': 74, 'crosses_midnight': False},
    '1800 Break':  {'or_start': 1800, 'or_end': 1815, 'cutoff': 300,  'days': '12345',
                    'target_wins': 35, 'target_fails': 40, 'target_n': 75, 'crosses_midnight': True},
    'Magic Hour':  {'or_start': 300,  'or_end': 700,  'cutoff': 830,  'days': '23456',
                    'target_wins': 54, 'target_fails': 6,  'target_n': 60, 'crosses_midnight': False},
}

def days_to_python_dow(days_str):
    pine_to_python = {1: 6, 2: 0, 3: 1, 4: 2, 5: 3, 6: 4, 7: 5}
    return set(pine_to_python[int(d)] for d in days_str)

def build_sessions(preset_name, or_start, or_end, cutoff, days_str, crosses_midnight):
    valid_dows = days_to_python_dow(days_str)
    sessions = []
    for date, day_1m in df_1m.groupby('date'):
        if date.weekday() not in valid_dows: continue
        if crosses_midnight:
            next_date = date + pd.Timedelta(days=1)
            session_1m = pd.concat([
                df_1m[(df_1m['date'] == date) & (df_1m['et_hhmm'] >= or_start)],
                df_1m[(df_1m['date'] == next_date) & (df_1m['et_hhmm'] < cutoff)]
            ])
            session_5m = pd.concat([
                df_5m[(df_5m['date'] == date) & (df_5m['et_hhmm'] >= or_start)],
                df_5m[(df_5m['date'] == next_date) & (df_5m['et_hhmm'] < cutoff)]
            ])
        else:
            session_1m = df_1m[(df_1m['date'] == date) & (df_1m['et_hhmm'] >= or_start) & (df_1m['et_hhmm'] < cutoff)]
            session_5m = df_5m[(df_5m['date'] == date) & (df_5m['et_hhmm'] >= or_start) & (df_5m['et_hhmm'] < cutoff)]
        if session_1m.empty or session_5m.empty: continue
        or_bars = session_1m[(session_1m['et_hhmm'] >= or_start) & (session_1m['et_hhmm'] < or_end)]
        if or_bars.empty: continue
        or_high = or_bars['high'].max()
        or_low = or_bars['low'].min()
        data_5m = session_5m[session_5m['et_hhmm'] >= or_end]
        if data_5m.empty: continue

        # 5m breakout detection (matches Pine Script's f_process_signal_logic which uses chart TF close)
        bo_side = 0; bo_px = None; bo_idx = None
        for idx, row in data_5m.iterrows():
            if row['close'] > or_high:
                bo_side = 1; bo_px = row['close']; bo_idx = idx; break
            elif row['close'] < or_low:
                bo_side = -1; bo_px = row['close']; bo_idx = idx; break
        if bo_side == 0: continue

        post_bo_5m = data_5m.loc[bo_idx:]
        if bo_side == 1:
            mae_bo = ((bo_px - post_bo_5m['low'].min()) / bo_px) * 100
        else:
            mae_bo = ((post_bo_5m['high'].max() - bo_px) / bo_px) * 100

        bar_data = []
        for idx, row in post_bo_5m.iterrows():
            bar_data.append({'high': row['high'], 'low': row['low'], 'close': row['close']})

        sessions.append({
            'date': date, 'side': bo_side, 'or_high': or_high, 'or_low': or_low,
            'bo_px': bo_px, 'mae_bo': mae_bo,
            'bar_data': bar_data,
        })
    return pd.DataFrame(sessions)

# Build sessions
all_sessions = {}
for name, cfg in PRESETS.items():
    df_p = build_sessions(name, cfg['or_start'], cfg['or_end'], cfg['cutoff'], cfg['days'], cfg['crosses_midnight'])
    all_sessions[name] = df_p
    print(f"  {name:15s}: N={len(df_p)} (tgt {cfg['target_n']})")
print()

def test_exact_dnl_rule(df, ev_pct=0.30, p80_fallback=0.5, pending_as='pending'):
    """
    Exact DNL Pine Script rule:
    1. Fakeout (R2): any 5m close beyond opp OR → outcome=2 (checked first, takes precedence)
    2. Win: EV target hit by TOUCH → outcome=1
    3. Loss: P80 MAE invalidation hit by TOUCH → outcome=-1
    4. Pending: none of the above → outcome=0
    
    Uses ROLLING P80 BO MAE from wins, fallback to ALL, then 0.5%.
    """
    results = []
    prior_mae_wins = []  # Rolling: MAE of prior winning sessions
    prior_mae_all = []   # Rolling: MAE of ALL prior sessions
    
    for i, row in df.iterrows():
        # Compute rolling P80
        if len(prior_mae_wins) > 0:
            p80_wins = p_nearest(prior_mae_wins, 80)
        else:
            p80_wins = None
        
        if len(prior_mae_all) > 0:
            p80_all = p_nearest(prior_mae_all, 80)
        else:
            p80_all = None
        
        # Fallback chain: wins → all → 0.5%
        if p80_wins is not None and not np.isnan(p80_wins):
            p80_mae = p80_wins
        elif p80_all is not None and not np.isnan(p80_all):
            p80_mae = p80_all
        else:
            p80_mae = p80_fallback
        
        # Compute levels
        target_px = row['bo_px'] * (1 + row['side'] * ev_pct / 100)
        invalid_px = row['bo_px'] * (1 - row['side'] * p80_mae / 100)
        
        # Process each 5m bar in order (matches Pine Script's per-bar evaluation)
        outcome = 0  # pending
        for bar in row['bar_data']:
            # 1. Check fakeout FIRST (takes precedence)
            crossed_opposite = (row['side'] == 1 and bar['close'] < row['or_low']) or \
                              (row['side'] == -1 and bar['close'] > row['or_high'])
            if crossed_opposite:
                outcome = 2  # fakeout
                break  # fakeout takes precedence and locks
            
            # 2. If not crossed, check win
            if outcome == 0:
                target_hit = (row['side'] == 1 and bar['high'] >= target_px) or \
                            (row['side'] == -1 and bar['low'] <= target_px)
                if target_hit:
                    outcome = 1  # win
                    # Don't break — a later bar could still cross opposite (fakeout takes precedence)
            
            # 3. If not crossed and not won, check loss
            if outcome == 0:
                invalid_hit = (row['side'] == 1 and bar['low'] <= invalid_px) or \
                              (row['side'] == -1 and bar['high'] >= invalid_px)
                if invalid_hit:
                    outcome = -1  # loss
                    # Don't break — a later bar could still cross opposite (fakeout takes precedence)
        
        # After all bars, if outcome is 1 (win) but a later bar crossed opposite, it's already
        # caught by the break in the loop. But if we didn't break, we need to re-check.
        # Actually, the Pine Script checks crossed_opposite FIRST on each bar. If crossed,
        # it sets outcome=2 and breaks. So if a win was set on bar 5, and bar 10 crosses
        # opposite, the crossed check on bar 10 would set outcome=2 and break.
        # But in our loop, we break on crossed_opposite, so we never reach bar 10 if
        # crossed happens. But we DON'T break on win or loss — we continue checking.
        # Wait, the Pine Script code says:
        #   if crossed_opposite: outcome = 2 (break? No, it doesn't break in the code)
        # Actually, looking at the Pine Script code again:
        #   if crossed_opposite: st.sig_outcome := 2
        #   else if st.sig_outcome == 0: check target and invalidation
        # So once outcome is set to 2, the else-if won't execute. But outcome=2 doesn't
        # prevent future bars from being processed — the `if crossed_opposite` will keep
        # being true, but `else if` won't run. So outcome stays at 2.
        # Once outcome=1 (win), the `else if st.sig_outcome == 0` won't run, so target
        # and invalidation won't be re-checked. But `crossed_opposite` WILL still be checked.
        # So a win can be upgraded to fakeout if a later bar crosses opposite.
        
        # Re-process: if outcome is 1 (win) or -1 (loss), check if any LATER bar crosses opposite
        if outcome == 1 or outcome == -1:
            for bar in row['bar_data']:
                crossed = (row['side'] == 1 and bar['close'] < row['or_low']) or \
                          (row['side'] == -1 and bar['close'] > row['or_high'])
                if crossed:
                    outcome = 2  # upgrade to fakeout
                    break
        
        results.append({'date': row['date'], 'side': row['side'], 'outcome': outcome,
                         'p80_mae': p80_mae, 'mae_bo': row['mae_bo']})
        
        # Update rolling histories
        prior_mae_all.append(row['mae_bo'])
        if outcome == 1:  # win
            prior_mae_wins.append(row['mae_bo'])
    
    res = pd.DataFrame(results)
    wins = (res['outcome'] == 1).sum()
    losses = (res['outcome'] == -1).sum()
    fakeouts = (res['outcome'] == 2).sum()
    pending = (res['outcome'] == 0).sum()
    
    if pending_as == 'fail':
        w = wins
        f = losses + fakeouts + pending
    elif pending_as == 'win':
        w = wins + pending
        f = losses + fakeouts
    else:  # pending
        w = wins
        f = losses + fakeouts
    
    return w, f, pending, wins, losses, fakeouts

# === Test EXACT DNL rule ===
print("=" * 80)
print("EXACT DNL RULE: R2(fakeout) > EV target(win) > P80 MAE(loss) > pending")
print("  Rolling P80 BO MAE from wins, fallback to ALL, then 0.5%")
print("  5m breakout detection, TOUCH-based target/invalidation")
print("=" * 80)

for pending_as in ['pending', 'fail', 'win']:
    print(f"\n  Pending counted as: {pending_as.upper()}")
    print(f"  {'Preset':<15} {'N':>4} {'Wins':>6} {'Fails':>6} {'Pend':>6} {'Target':>12} {'Match':>8}")
    print("  " + "-" * 65)
    for name, cfg in PRESETS.items():
        df_p = all_sessions[name]
        w, f, pend, wins, losses, fakeouts = test_exact_dnl_rule(df_p, pending_as=pending_as)
        target = f"{cfg['target_wins']}/{cfg['target_fails']}"
        match = "YES" if w == cfg['target_wins'] and f == cfg['target_fails'] else f"Δ={w-cfg['target_wins']}/{f-cfg['target_fails']}"
        print(f"  {name:<13} {len(df_p):>4} {w:>6} {f:>6} {pend:>6} {target:>12} {match:>8}")
    print()

# === Show detailed breakdown for 1100 BO ===
print("=" * 80)
print("DETAILED BREAKDOWN: 1100 BO (exact DNL rule)")
print("=" * 80)
df_p = all_sessions['1100 BO']
results = []
prior_mae_wins = []
prior_mae_all = []
for i, row in df_p.iterrows():
    if len(prior_mae_wins) > 0:
        p80_wins = p_nearest(prior_mae_wins, 80)
    else:
        p80_wins = None
    if len(prior_mae_all) > 0:
        p80_all = p_nearest(prior_mae_all, 80)
    else:
        p80_all = None
    if p80_wins is not None and not np.isnan(p80_wins):
        p80_mae = p80_wins
    elif p80_all is not None and not np.isnan(p80_all):
        p80_mae = p80_all
    else:
        p80_mae = 0.5
    target_px = row['bo_px'] * (1 + row['side'] * 0.30 / 100)
    invalid_px = row['bo_px'] * (1 - row['side'] * p80_mae / 100)
    outcome = 0
    for bar in row['bar_data']:
        crossed = (row['side'] == 1 and bar['close'] < row['or_low']) or \
                  (row['side'] == -1 and bar['close'] > row['or_high'])
        if crossed:
            outcome = 2; break
        if outcome == 0:
            if (row['side'] == 1 and bar['high'] >= target_px) or \
               (row['side'] == -1 and bar['low'] <= target_px):
                outcome = 1
        if outcome == 0:
            if (row['side'] == 1 and bar['low'] <= invalid_px) or \
               (row['side'] == -1 and bar['high'] >= invalid_px):
                outcome = -1
    # Re-check for fakeout upgrade
    if outcome == 1 or outcome == -1:
        for bar in row['bar_data']:
            crossed = (row['side'] == 1 and bar['close'] < row['or_low']) or \
                      (row['side'] == -1 and bar['close'] > row['or_high'])
            if crossed:
                outcome = 2; break
    results.append({'date': row['date'], 'side': row['side'], 'outcome': outcome,
                    'p80_mae': p80_mae, 'mae_bo': row['mae_bo']})
    prior_mae_all.append(row['mae_bo'])
    if outcome == 1:
        prior_mae_wins.append(row['mae_bo'])

res = pd.DataFrame(results)
print(f"  Wins (outcome=1): {(res['outcome']==1).sum()}")
print(f"  Losses (outcome=-1): {(res['outcome']==-1).sum()}")
print(f"  Fakeouts (outcome=2): {(res['outcome']==2).sum()}")
print(f"  Pending (outcome=0): {(res['outcome']==0).sum()}")
print(f"  Target: 55/18/0 pending")
print()
print("  Outcome distribution:")
print(res['outcome'].value_counts().sort_index())
print()
print("  First 10 sessions:")
print(res.head(10).to_string())
print()
print("  Last 10 sessions:")
print(res.tail(10).to_string())