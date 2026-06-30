"""
Theory validation v2: Fixed full-sample P80 MAE stop-loss.
The Gunship likely computes P80 MAE from the full historical sample of 
WINNING sessions and uses that as a fixed invalidation level for all sessions.

Target: 55 FULL / 18 Failed for 1100 BO preset.
"""
import pandas as pd
import numpy as np
import pytz

# Load NQ 1-min data
df_1m = pd.read_parquet('data/live/live_storage_-NQ.parquet')
df_1m['datetime'] = pd.to_datetime(df_1m['timestamp'], utc=True)
df_1m = df_1m.set_index('datetime')
df_1m = df_1m[['open', 'high', 'low', 'close', 'volume']].copy()

df_1m = df_1m[(df_1m.index >= '2026-03-16') & (df_1m.index < '2026-06-29')]
df_1m = df_1m[~df_1m.index.strftime('%Y-%m-%d').isin(['2026-05-25', '2026-06-19'])]

et = pytz.timezone('America/New_York')
df_1m['et_time'] = df_1m.index.tz_convert(et)
df_1m['et_hhmm'] = df_1m['et_time'].dt.hour * 100 + df_1m['et_time'].dt.minute
df_1m['date'] = df_1m['et_time'].dt.date

df_5m = df_1m.resample('5min', label='left', closed='left').agg(
    {'open':'first', 'high':'max', 'low':'min', 'close':'last', 'volume':'sum'}).dropna()
df_5m['et_time'] = df_5m.index.tz_convert(et)
df_5m['et_hhmm'] = df_5m['et_time'].dt.hour * 100 + df_5m['et_time'].dt.minute
df_5m['date'] = df_5m['et_time'].dt.date

OR_START = 1100; OR_END = 1115; CUTOFF = 1230; EV_TARGET_PCT = 0.30

sessions = []
for date, day_1m in df_1m.groupby('date'):
    rth_1m = day_1m[(day_1m['et_hhmm'] >= 930) & (day_1m['et_hhmm'] < 1600)]
    if rth_1m.empty: continue
    day_5m = df_5m[df_5m['date'] == date]
    rth_5m = day_5m[(day_5m['et_hhmm'] >= 930) & (day_5m['et_hhmm'] < 1600)]
    if rth_5m.empty: continue

    or_bars = rth_1m[(rth_1m['et_hhmm'] >= OR_START) & (rth_1m['et_hhmm'] < OR_END)]
    if or_bars.empty: continue
    or_high = or_bars['high'].max()
    or_low = or_bars['low'].min()

    data_1m = rth_1m[(rth_1m['et_hhmm'] >= OR_END) & (rth_1m['et_hhmm'] < CUTOFF)]
    data_5m = rth_5m[(rth_5m['et_hhmm'] >= OR_END) & (rth_5m['et_hhmm'] < CUTOFF)]
    if data_1m.empty or data_5m.empty: continue

    # Breakout on 5m close
    bo_side = 0; bo_px = None; bo_idx = None
    for idx, row in data_5m.iterrows():
        if row['close'] > or_high:
            bo_side = 1; bo_px = row['close']; bo_idx = idx; break
        elif row['close'] < or_low:
            bo_side = -1; bo_px = row['close']; bo_idx = idx; break
    if bo_side == 0: continue

    post_bo_5m = data_5m.loc[bo_idx:]
    
    if bo_side == 1:
        mfe = ((post_bo_5m['high'].max() - bo_px) / bo_px) * 100
        mae = ((bo_px - post_bo_5m['low'].min()) / bo_px) * 100
    else:
        mfe = ((bo_px - post_bo_5m['low'].min()) / bo_px) * 100
        mae = ((post_bo_5m['high'].max() - bo_px) / bo_px) * 100

    close_at_cutoff = data_5m['close'].iloc[-1]
    r1_fail = (bo_side == 1 and close_at_cutoff < or_low) or \
              (bo_side == -1 and close_at_cutoff > or_high)

    # EV target hit
    target_px = bo_px * (1 + bo_side * EV_TARGET_PCT / 100)
    ev_hit = False
    for idx, row in post_bo_5m.iterrows():
        if bo_side == 1 and row['high'] >= target_px:
            ev_hit = True; break
        elif bo_side == -1 and row['low'] <= target_px:
            ev_hit = True; break

    # Store bar data for stop-loss checking
    bar_data = []
    for idx, row in post_bo_5m.iterrows():
        bar_data.append({'high': row['high'], 'low': row['low'], 'close': row['close']})

    sessions.append({
        'date': date, 'side': bo_side, 'or_high': or_high, 'or_low': or_low,
        'bo_px': bo_px, 'mfe': mfe, 'mae': mae,
        'close_at_cutoff': close_at_cutoff, 'r1_fail': r1_fail,
        'ev_hit': ev_hit, 'bar_data': bar_data, 'target_px': target_px,
    })

df = pd.DataFrame(sessions)
print(f"Total sessions: {len(df)}")
print()

def p_nearest(series, p):
    if len(series) == 0: return np.nan
    return np.percentile(series, p, method='nearest')

# Step 1: Compute R1 baseline (57 wins / 16 fails)
r1_wins = df[~df['r1_fail']]
r1_fails = df[df['r1_fail']]
print(f"R1 baseline: {len(r1_wins)} wins / {len(r1_fails)} fails (target: 55/18)")
print(f"  Need to find {18 - len(r1_fails)} additional fails from R1-wins")
print()

# Step 2: Compute P80 MAE from R1-winning sessions (full sample)
bull_r1_wins = r1_wins[r1_wins['side'] == 1]
bear_r1_wins = r1_wins[r1_wins['side'] == -1]

bull_p80_mae = p_nearest(bull_r1_wins['mae'], 80)
bear_p80_mae = p_nearest(bear_r1_wins['mae'], 80)
print(f"Full-sample P80 MAE (R1 wins only):")
print(f"  Bull: {bull_p80_mae:.3f}%")
print(f"  Bear: {bear_p80_mae:.3f}%")
print()

# Step 3: Apply fixed P80 MAE stop-loss to R1-winning sessions
print("=" * 70)
print("THEORY H: R1 + Fixed full-sample P80 MAE stop-loss (from R1 wins)")
print("  Fail = R1 OR stop-loss hit (P80 MAE from full-sample R1 wins)")
print("=" * 70)

results_h = []
for i, row in df.iterrows():
    p80_mae = bull_p80_mae if row['side'] == 1 else bear_p80_mae
    invalid_px = row['bo_px'] * (1 - row['side'] * p80_mae / 100)
    
    stop_hit = False
    for bar in row['bar_data']:
        if row['side'] == 1 and bar['low'] <= invalid_px:
            stop_hit = True; break
        elif row['side'] == -1 and bar['high'] >= invalid_px:
            stop_hit = True; break
    
    failed = row['r1_fail'] or stop_hit
    won = not failed
    results_h.append({'date': row['date'], 'side': row['side'], 'won': won,
                      'r1_fail': row['r1_fail'], 'stop_hit': stop_hit,
                      'p80_mae_pct': p80_mae, 'invalid_px': invalid_px,
                      'mae': row['mae']})

res_h = pd.DataFrame(results_h)
wins_h = res_h['won'].sum()
fails_h = (~res_h['won']).sum()
stop_only_h = res_h[~res_h['won'] & ~res_h['r1_fail']]
print(f"  Wins: {wins_h}, Fails: {fails_h}  (target: 55/18)")
print(f"  R1 fails: {res_h['r1_fail'].sum()}, Stop-only fails: {len(stop_only_h)}")
print(f"  Delta: wins={wins_h-55}, fails={fails_h-18}")
print()
if len(stop_only_h) > 0:
    print("  Sessions failed by stop-loss only (not R1):")
    print(stop_only_h[['date', 'side', 'mae', 'p80_mae_pct', 'invalid_px', 'stop_hit']].to_string())
print()

# Step 4: Try different P80 MAE sources
print("=" * 70)
print("THEORY I: R1 + Fixed P80 MAE from ALL sessions (not just wins)")
print("=" * 70)
bull_all = df[df['side'] == 1]
bear_all = df[df['side'] == -1]
bull_p80_all = p_nearest(bull_all['mae'], 80)
bear_p80_all = p_nearest(bear_all['mae'], 80)
print(f"  Bull P80 MAE (all): {bull_p80_all:.3f}%")
print(f"  Bear P80 MAE (all): {bear_p80_all:.3f}%")

results_i = []
for i, row in df.iterrows():
    p80_mae = bull_p80_all if row['side'] == 1 else bear_p80_all
    invalid_px = row['bo_px'] * (1 - row['side'] * p80_mae / 100)
    stop_hit = False
    for bar in row['bar_data']:
        if row['side'] == 1 and bar['low'] <= invalid_px:
            stop_hit = True; break
        elif row['side'] == -1 and bar['high'] >= invalid_px:
            stop_hit = True; break
    failed = row['r1_fail'] or stop_hit
    won = not failed
    results_i.append({'date': row['date'], 'won': won, 'r1_fail': row['r1_fail'], 'stop_hit': stop_hit})

res_i = pd.DataFrame(results_i)
wins_i = res_i['won'].sum()
fails_i = (~res_i['won']).sum()
stop_only_i = res_i[~res_i['won'] & ~res_i['r1_fail']]
print(f"  Wins: {wins_i}, Fails: {fails_i}  (target: 55/18)")
print(f"  Delta: wins={wins_i-55}, fails={fails_i-18}")
if len(stop_only_i) > 0:
    print(f"  Stop-only fails: {len(stop_only_i)}")
    print(stop_only_i[['date', 'side', 'stop_hit']].to_string())
print()

# Step 5: Try P80 MAE from ALL sessions with EV target win requirement
print("=" * 70)
print("THEORY J: R1 + Fixed P80 MAE (all) + EV target required for win")
print("=" * 70)
results_j = []
for i, row in df.iterrows():
    p80_mae = bull_p80_all if row['side'] == 1 else bear_p80_all
    invalid_px = row['bo_px'] * (1 - row['side'] * p80_mae / 100)
    stop_hit = False
    for bar in row['bar_data']:
        if row['side'] == 1 and bar['low'] <= invalid_px:
            stop_hit = True; break
        elif row['side'] == -1 and bar['high'] >= invalid_px:
            stop_hit = True; break
    failed = row['r1_fail'] or stop_hit or not row['ev_hit']
    won = not failed
    results_j.append({'date': row['date'], 'won': won})

res_j = pd.DataFrame(results_j)
wins_j = res_j['won'].sum()
fails_j = (~res_j['won']).sum()
print(f"  Wins: {wins_j}, Fails: {fails_j}  (target: 55/18)")
print(f"  Delta: wins={wins_j-55}, fails={fails_j-18}")
print()

# Step 6: Try different MAE percentiles (P75, P85, P90) from all sessions
print("=" * 70)
print("THEORY K: R1 + Fixed P{X} MAE (all sessions) — sweep percentiles")
print("=" * 70)
for pct in [70, 75, 80, 85, 90, 95]:
    bull_p = p_nearest(bull_all['mae'], pct)
    bear_p = p_nearest(bear_all['mae'], pct)
    results = []
    for i, row in df.iterrows():
        p_mae = bull_p if row['side'] == 1 else bear_p
        invalid_px = row['bo_px'] * (1 - row['side'] * p_mae / 100)
        stop_hit = False
        for bar in row['bar_data']:
            if row['side'] == 1 and bar['low'] <= invalid_px:
                stop_hit = True; break
            elif row['side'] == -1 and bar['high'] >= invalid_px:
                stop_hit = True; break
        failed = row['r1_fail'] or stop_hit
        won = not failed
        results.append(won)
    w = sum(results)
    f = len(results) - w
    print(f"  P{pct}: bull={bull_p:.3f}%, bear={bear_p:.3f}% → wins={w}, fails={f}  (Δ={w-55}/{f-18})")
print()

# Step 7: Try P80 MAE from wins only, sweep percentiles
print("=" * 70)
print("THEORY L: R1 + Fixed P{X} MAE (R1 wins only) — sweep percentiles")
print("=" * 70)
for pct in [70, 75, 80, 85, 90, 95]:
    bull_p = p_nearest(bull_r1_wins['mae'], pct)
    bear_p = p_nearest(bear_r1_wins['mae'], pct)
    results = []
    for i, row in df.iterrows():
        p_mae = bull_p if row['side'] == 1 else bear_p
        invalid_px = row['bo_px'] * (1 - row['side'] * p_mae / 100)
        stop_hit = False
        for bar in row['bar_data']:
            if row['side'] == 1 and bar['low'] <= invalid_px:
                stop_hit = True; break
            elif row['side'] == -1 and bar['high'] >= invalid_px:
                stop_hit = True; break
        failed = row['r1_fail'] or stop_hit
        won = not failed
        results.append(won)
    w = sum(results)
    f = len(results) - w
    print(f"  P{pct}: bull={bull_p:.3f}%, bear={bear_p:.3f}% → wins={w}, fails={f}  (Δ={w-55}/{f-18})")
print()

# Step 8: Try session MAE (from OR boundary) instead of BO MAE
print("=" * 70)
print("THEORY M: R1 + Fixed P80 Session MAE (from OR, all sessions)")
print("=" * 70)
# Compute session MAE from OR boundary
for date_idx, row in df.iterrows():
    # Recompute session MAE from OR
    pass  # We already have mae from BO px; need session_mae from OR

# Actually let's compute session MAE from OR for each session
sessions_mae_or = []
for date, day_1m in df_1m.groupby('date'):
    rth_1m = day_1m[(day_1m['et_hhmm'] >= 930) & (day_1m['et_hhmm'] < 1600)]
    if rth_1m.empty: continue
    day_5m = df_5m[df_5m['date'] == date]
    rth_5m = day_5m[(day_5m['et_hhmm'] >= 930) & (day_5m['et_hhmm'] < 1600)]
    if rth_5m.empty: continue
    or_bars = rth_1m[(rth_1m['et_hhmm'] >= OR_START) & (rth_1m['et_hhmm'] < OR_END)]
    if or_bars.empty: continue
    or_high = or_bars['high'].max()
    or_low = or_bars['low'].min()
    data_5m = rth_5m[(rth_5m['et_hhmm'] >= OR_END) & (rth_5m['et_hhmm'] < CUTOFF)]
    if data_5m.empty: continue
    bo_side = 0; bo_px = None; bo_idx = None
    for idx, r in data_5m.iterrows():
        if r['close'] > or_high:
            bo_side = 1; bo_px = r['close']; bo_idx = idx; break
        elif r['close'] < or_low:
            bo_side = -1; bo_px = r['close']; bo_idx = idx; break
    if bo_side == 0: continue
    post_bo_5m = data_5m.loc[bo_idx:]
    if bo_side == 1:
        session_mae_or = ((or_high - post_bo_5m['low'].min()) / or_high) * 100
    else:
        session_mae_or = ((post_bo_5m['high'].max() - or_low) / or_low) * 100
    sessions_mae_or.append({'date': date, 'side': bo_side, 'session_mae_or': session_mae_or})

df_mae_or = pd.DataFrame(sessions_mae_or)
df = df.merge(df_mae_or, on=['date', 'side'], how='left')

bull_all_or = df[df['side'] == 1]
bear_all_or = df[df['side'] == -1]
for pct in [75, 80, 85, 90]:
    bull_p = p_nearest(bull_all_or['session_mae_or'], pct)
    bear_p = p_nearest(bear_all_or['session_mae_or'], pct)
    results = []
    for i, row in df.iterrows():
        p_mae = bull_p if row['side'] == 1 else bear_p
        # Anchor at OR boundary, not BO px
        ref = row['or_high'] if row['side'] == 1 else row['or_low']
        invalid_px = ref * (1 - row['side'] * p_mae / 100)
        stop_hit = False
        for bar in row['bar_data']:
            if row['side'] == 1 and bar['low'] <= invalid_px:
                stop_hit = True; break
            elif row['side'] == -1 and bar['high'] >= invalid_px:
                stop_hit = True; break
        failed = row['r1_fail'] or stop_hit
        won = not failed
        results.append(won)
    w = sum(results)
    f = len(results) - w
    print(f"  P{pct}: bull={bull_p:.3f}%, bear={bear_p:.3f}% → wins={w}, fails={f}  (Δ={w-55}/{f-18})")
print()

# === SUMMARY ===
print("=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"{'Theory':<55} {'Wins':>6} {'Fails':>6} {'Match':>12}")
print("-" * 70)
for name, w, f in [
    ("H: R1 + P80 MAE (R1 wins, BO px anchor)", wins_h, fails_h),
    ("I: R1 + P80 MAE (all, BO px anchor)", wins_i, fails_i),
    ("J: R1 + P80 MAE (all) + EV target", wins_j, fails_j),
]:
    match = "YES" if w == 55 and f == 18 else f"NO (Δ={w-55}/{f-18})"
    print(f"{name:<55} {w:>6} {f:>6} {match:>12}")