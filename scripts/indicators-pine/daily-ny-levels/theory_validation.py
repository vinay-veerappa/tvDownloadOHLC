"""
Theory validation: Find the exact Gunship classification rule.
Target: 55 FULL / 18 Failed for 1100 BO preset.

Key insight from §6.8.3: Gunship marks a session as Failed if the P80 MAE
invalidation level is hit intraday, even if price recovers by cutoff.

Theories to test:
  A: R1 (cutoff close beyond opp OR) + Rolling P80 MAE stop-loss hit
  B: R2 (any 5m close beyond opp OR) + Rolling P80 MAE stop-loss hit
  C: Stop-loss only (P80 MAE hit) — no opposite OR check
  D: R1 + Fixed 0.5% MAE stop-loss
  E: "Not failed" = win (R1 + stop-loss, no EV target needed)
  F: R1 + Rolling P80 MAE stop-loss + EV target hit for win
"""
import pandas as pd
import numpy as np
import pytz

# Load NQ 1-min data
df_1m = pd.read_parquet('data/live/live_storage_-NQ.parquet')
df_1m['datetime'] = pd.to_datetime(df_1m['timestamp'], utc=True)
df_1m = df_1m.set_index('datetime')
df_1m = df_1m[['open', 'high', 'low', 'close', 'volume']].copy()

# Use 1m for OR building, 5m for chart bars (matches DNL hybrid approach)
df_1m = df_1m[(df_1m.index >= '2026-03-16') & (df_1m.index < '2026-06-29')]
df_1m = df_1m[~df_1m.index.strftime('%Y-%m-%d').isin(['2026-05-25', '2026-06-19'])]

et = pytz.timezone('America/New_York')
df_1m['et_time'] = df_1m.index.tz_convert(et)
df_1m['et_hour'] = df_1m['et_time'].dt.hour
df_1m['et_minute'] = df_1m['et_time'].dt.minute
df_1m['et_hhmm'] = df_1m['et_hour'] * 100 + df_1m['et_minute']
df_1m['date'] = df_1m['et_time'].dt.date

df_5m = df_1m.resample('5min', label='left', closed='left').agg(
    {'open':'first', 'high':'max', 'low':'min', 'close':'last', 'volume':'sum'}).dropna()
df_5m['et_time'] = df_5m.index.tz_convert(et)
df_5m['et_hhmm'] = df_5m['et_time'].dt.hour * 100 + df_5m['et_time'].dt.minute
df_5m['date'] = df_5m['et_time'].dt.date

OR_START = 1100
OR_END = 1115
CUTOFF = 1230
EV_TARGET_PCT = 0.30

# Build sessions with 5m bar-level data for stop-loss checking
sessions = []
for date, day_1m in df_1m.groupby('date'):
    rth_1m = day_1m[(day_1m['et_hhmm'] >= 930) & (day_1m['et_hhmm'] < 1600)]
    if rth_1m.empty:
        continue
    day_5m = df_5m[df_5m['date'] == date]
    rth_5m = day_5m[(day_5m['et_hhmm'] >= 930) & (day_5m['et_hhmm'] < 1600)]
    if rth_5m.empty:
        continue

    or_bars = rth_1m[(rth_1m['et_hhmm'] >= OR_START) & (rth_1m['et_hhmm'] < OR_END)]
    if or_bars.empty:
        continue
    or_high = or_bars['high'].max()
    or_low = or_bars['low'].min()

    data_1m = rth_1m[(rth_1m['et_hhmm'] >= OR_END) & (rth_1m['et_hhmm'] < CUTOFF)]
    data_5m = rth_5m[(rth_5m['et_hhmm'] >= OR_END) & (rth_5m['et_hhmm'] < CUTOFF)]
    if data_1m.empty or data_5m.empty:
        continue

    # Breakout on 5m close (matches DNL chart-level signal logic)
    bo_side = 0
    bo_px = None
    bo_idx = None
    for idx, row in data_5m.iterrows():
        if row['close'] > or_high:
            bo_side = 1; bo_px = row['close']; bo_idx = idx; break
        elif row['close'] < or_low:
            bo_side = -1; bo_px = row['close']; bo_idx = idx; break

    if bo_side == 0:
        continue

    # Post-breakout 5m bars
    post_bo_5m = data_5m.loc[bo_idx:]
    
    # MFE/MAE from BO px (using 5m bars)
    if bo_side == 1:
        mfe = ((post_bo_5m['high'].max() - bo_px) / bo_px) * 100
        mae = ((bo_px - post_bo_5m['low'].min()) / bo_px) * 100
    else:
        mfe = ((bo_px - post_bo_5m['low'].min()) / bo_px) * 100
        mae = ((post_bo_5m['high'].max() - bo_px) / bo_px) * 100

    # Session MFE from OR (using 1m for max precision)
    if bo_side == 1:
        session_mfe = ((data_1m['high'].max() - or_high) / or_high) * 100
        session_mae = ((or_high - data_1m['low'].min()) / or_high) * 100
    else:
        session_mfe = ((or_low - data_1m['low'].min()) / or_low) * 100
        session_mae = ((data_1m['high'].max() - or_low) / or_low) * 100

    close_at_cutoff = data_5m['close'].iloc[-1]

    # R1: cutoff close beyond opposite OR
    r1_fail = (bo_side == 1 and close_at_cutoff < or_low) or \
              (bo_side == -1 and close_at_cutoff > or_high)

    # R2: any 5m close beyond opposite OR
    r2_fail = False
    for idx, row in post_bo_5m.iterrows():
        if bo_side == 1 and row['close'] < or_low:
            r2_fail = True; break
        elif bo_side == -1 and row['close'] > or_high:
            r2_fail = True; break

    # R3: any 5m touch beyond opposite OR
    r3_fail = False
    for idx, row in post_bo_5m.iterrows():
        if bo_side == 1 and row['low'] < or_low:
            r3_fail = True; break
        elif bo_side == -1 and row['high'] > or_high:
            r3_fail = True; break

    # EV target hit
    target_px = bo_px * (1 + bo_side * EV_TARGET_PCT / 100)
    ev_hit = False
    for idx, row in post_bo_5m.iterrows():
        if bo_side == 1 and row['high'] >= target_px:
            ev_hit = True; break
        elif bo_side == -1 and row['low'] <= target_px:
            ev_hit = True; break

    # Store 5m bar lows/highs for stop-loss checking
    bar_data = []
    for idx, row in post_bo_5m.iterrows():
        bar_data.append({'idx': idx, 'high': row['high'], 'low': row['low'], 'close': row['close']})

    sessions.append({
        'date': date, 'side': bo_side, 'or_high': or_high, 'or_low': or_low,
        'bo_px': bo_px, 'mfe': mfe, 'mae': mae,
        'session_mfe': session_mfe, 'session_mae': session_mae,
        'close_at_cutoff': close_at_cutoff,
        'r1_fail': r1_fail, 'r2_fail': r2_fail, 'r3_fail': r3_fail,
        'ev_hit': ev_hit, 'bar_data': bar_data,
        'target_px': target_px,
    })

df = pd.DataFrame(sessions)
print(f"Total sessions: {len(df)} (target: 73)")
print(f"  Bull: {(df['side']==1).sum()}, Bear: {(df['side']==-1).sum()}")
print()

def p_nearest(series, p):
    if len(series) == 0: return np.nan
    return np.percentile(series, p, method='nearest')

# === THEORY A: R1 + Rolling P80 MAE stop-loss ===
print("=" * 70)
print("THEORY A: R1 (cutoff close beyond opp OR) + Rolling P80 MAE stop-loss")
print("  Win = not failed (no EV target requirement)")
print("  Fail = R1 OR stop-loss hit (rolling P80 MAE from prior wins)")
print("=" * 70)

results_a = []
prior_mae_wins = []  # MAE of prior winning sessions (rolling)
for i, row in df.iterrows():
    # Compute rolling P80 MAE from prior wins
    if len(prior_mae_wins) >= 1:
        p80_mae = p_nearest(prior_mae_wins, 80) / 100
    else:
        p80_mae = 0.5 / 100  # cold start fallback
    
    # Compute invalidation level
    invalid_px = row['bo_px'] * (1 - row['side'] * p80_mae)
    
    # Check if any 5m bar hit invalidation
    stop_hit = False
    for bar in row['bar_data']:
        if row['side'] == 1 and bar['low'] <= invalid_px:
            stop_hit = True; break
        elif row['side'] == -1 and bar['high'] >= invalid_px:
            stop_hit = True; break
    
    failed = row['r1_fail'] or stop_hit
    won = not failed
    
    results_a.append({'date': row['date'], 'side': row['side'], 'won': won,
                      'r1_fail': row['r1_fail'], 'stop_hit': stop_hit,
                      'p80_mae_pct': p80_mae * 100, 'invalid_px': invalid_px})
    
    if won:
        prior_mae_wins.append(row['mae'])

res_a = pd.DataFrame(results_a)
wins_a = res_a['won'].sum()
fails_a = (~res_a['won']).sum()
stop_only_fails = res_a[~res_a['won'] & ~res_a['r1_fail']]['stop_hit'].sum()
print(f"  Wins: {wins_a}, Fails: {fails_a}  (target: 55/18)")
print(f"  R1 fails: {res_a['r1_fail'].sum()}, Stop-only fails: {stop_only_fails}")
print(f"  Delta: wins={wins_a-55}, fails={fails_a-18}")
print()

# === THEORY B: R2 + Rolling P80 MAE stop-loss ===
print("=" * 70)
print("THEORY B: R2 (any 5m close beyond opp OR) + Rolling P80 MAE stop-loss")
print("=" * 70)

results_b = []
prior_mae_wins_b = []
for i, row in df.iterrows():
    if len(prior_mae_wins_b) >= 1:
        p80_mae = p_nearest(prior_mae_wins_b, 80) / 100
    else:
        p80_mae = 0.5 / 100
    
    invalid_px = row['bo_px'] * (1 - row['side'] * p80_mae)
    stop_hit = False
    for bar in row['bar_data']:
        if row['side'] == 1 and bar['low'] <= invalid_px:
            stop_hit = True; break
        elif row['side'] == -1 and bar['high'] >= invalid_px:
            stop_hit = True; break
    
    failed = row['r2_fail'] or stop_hit
    won = not failed
    
    results_b.append({'date': row['date'], 'won': won, 'r2_fail': row['r2_fail'], 'stop_hit': stop_hit})
    if won:
        prior_mae_wins_b.append(row['mae'])

res_b = pd.DataFrame(results_b)
wins_b = res_b['won'].sum()
fails_b = (~res_b['won']).sum()
print(f"  Wins: {wins_b}, Fails: {fails_b}  (target: 55/18)")
print(f"  Delta: wins={wins_b-55}, fails={fails_b-18}")
print()

# === THEORY C: Stop-loss only (no opposite OR check) ===
print("=" * 70)
print("THEORY C: Stop-loss only (P80 MAE rolling) — no opposite OR check")
print("  Fail = stop-loss hit OR neither target nor stop hit by cutoff")
print("=" * 70)

results_c = []
prior_mae_wins_c = []
for i, row in df.iterrows():
    if len(prior_mae_wins_c) >= 1:
        p80_mae = p_nearest(prior_mae_wins_c, 80) / 100
    else:
        p80_mae = 0.5 / 100
    
    invalid_px = row['bo_px'] * (1 - row['side'] * p80_mae)
    stop_hit = False
    for bar in row['bar_data']:
        if row['side'] == 1 and bar['low'] <= invalid_px:
            stop_hit = True; break
        elif row['side'] == -1 and bar['high'] >= invalid_px:
            stop_hit = True; break
    
    # Win = EV target hit and no stop hit; Fail = stop hit or no target
    failed = stop_hit or not row['ev_hit']
    won = not failed
    
    results_c.append({'date': row['date'], 'won': won, 'stop_hit': stop_hit, 'ev_hit': row['ev_hit']})
    if won:
        prior_mae_wins_c.append(row['mae'])

res_c = pd.DataFrame(results_c)
wins_c = res_c['won'].sum()
fails_c = (~res_c['won']).sum()
print(f"  Wins: {wins_c}, Fails: {fails_c}  (target: 55/18)")
print(f"  Delta: wins={wins_c-55}, fails={fails_c-18}")
print()

# === THEORY D: R1 + Fixed 0.5% MAE stop-loss ===
print("=" * 70)
print("THEORY D: R1 + Fixed 0.5% MAE stop-loss (cold start default)")
print("=" * 70)

results_d = []
for i, row in df.iterrows():
    invalid_px = row['bo_px'] * (1 - row['side'] * 0.5 / 100)
    stop_hit = False
    for bar in row['bar_data']:
        if row['side'] == 1 and bar['low'] <= invalid_px:
            stop_hit = True; break
        elif row['side'] == -1 and bar['high'] >= invalid_px:
            stop_hit = True; break
    
    failed = row['r1_fail'] or stop_hit
    won = not failed
    results_d.append({'date': row['date'], 'won': won, 'r1_fail': row['r1_fail'], 'stop_hit': stop_hit})

res_d = pd.DataFrame(results_d)
wins_d = res_d['won'].sum()
fails_d = (~res_d['won']).sum()
stop_only_d = res_d[~res_d['won'] & ~res_d['r1_fail']]['stop_hit'].sum()
print(f"  Wins: {wins_d}, Fails: {fails_d}  (target: 55/18)")
print(f"  R1 fails: {res_d['r1_fail'].sum()}, Stop-only fails: {stop_only_d}")
print(f"  Delta: wins={wins_d-55}, fails={fails_d-18}")
print()

# === THEORY E: R1 + Rolling P80 MAE stop-loss + EV target for win ===
print("=" * 70)
print("THEORY E: R1 + Rolling P80 MAE stop-loss + EV target hit required for win")
print("  Win = EV target hit AND not failed")
print("  Fail = R1 OR stop-loss hit OR no EV target by cutoff")
print("=" * 70)

results_e = []
prior_mae_wins_e = []
for i, row in df.iterrows():
    if len(prior_mae_wins_e) >= 1:
        p80_mae = p_nearest(prior_mae_wins_e, 80) / 100
    else:
        p80_mae = 0.5 / 100
    
    invalid_px = row['bo_px'] * (1 - row['side'] * p80_mae)
    stop_hit = False
    for bar in row['bar_data']:
        if row['side'] == 1 and bar['low'] <= invalid_px:
            stop_hit = True; break
        elif row['side'] == -1 and bar['high'] >= invalid_px:
            stop_hit = True; break
    
    failed = row['r1_fail'] or stop_hit or not row['ev_hit']
    won = not failed
    
    results_e.append({'date': row['date'], 'won': won, 'r1_fail': row['r1_fail'], 
                      'stop_hit': stop_hit, 'ev_hit': row['ev_hit']})
    if won:
        prior_mae_wins_e.append(row['mae'])

res_e = pd.DataFrame(results_e)
wins_e = res_e['won'].sum()
fails_e = (~res_e['won']).sum()
print(f"  Wins: {wins_e}, Fails: {fails_e}  (target: 55/18)")
print(f"  Delta: wins={wins_e-55}, fails={fails_e-18}")
print()

# === THEORY F: R1 + Rolling P80 MAE (from ALL sessions, not just wins) ===
print("=" * 70)
print("THEORY F: R1 + Rolling P80 MAE (from ALL prior sessions, not just wins)")
print("=" * 70)

results_f = []
prior_mae_all = []
for i, row in df.iterrows():
    if len(prior_mae_all) >= 1:
        p80_mae = p_nearest(prior_mae_all, 80) / 100
    else:
        p80_mae = 0.5 / 100
    
    invalid_px = row['bo_px'] * (1 - row['side'] * p80_mae)
    stop_hit = False
    for bar in row['bar_data']:
        if row['side'] == 1 and bar['low'] <= invalid_px:
            stop_hit = True; break
        elif row['side'] == -1 and bar['high'] >= invalid_px:
            stop_hit = True; break
    
    failed = row['r1_fail'] or stop_hit
    won = not failed
    
    results_f.append({'date': row['date'], 'won': won, 'r1_fail': row['r1_fail'], 'stop_hit': stop_hit,
                      'p80_mae_pct': p80_mae * 100})
    prior_mae_all.append(row['mae'])

res_f = pd.DataFrame(results_f)
wins_f = res_f['won'].sum()
fails_f = (~res_f['won']).sum()
stop_only_f = res_f[~res_f['won'] & ~res_f['r1_fail']]['stop_hit'].sum()
print(f"  Wins: {wins_f}, Fails: {fails_f}  (target: 55/18)")
print(f"  R1 fails: {res_f['r1_fail'].sum()}, Stop-only fails: {stop_only_f}")
print(f"  Delta: wins={wins_f-55}, fails={fails_f-18}")
print()

# === THEORY G: R1 + Rolling P80 MAE from ALL sessions + EV target for win ===
print("=" * 70)
print("THEORY G: R1 + Rolling P80 MAE (ALL) + EV target required for win")
print("=" * 70)

results_g = []
prior_mae_all_g = []
for i, row in df.iterrows():
    if len(prior_mae_all_g) >= 1:
        p80_mae = p_nearest(prior_mae_all_g, 80) / 100
    else:
        p80_mae = 0.5 / 100
    
    invalid_px = row['bo_px'] * (1 - row['side'] * p80_mae)
    stop_hit = False
    for bar in row['bar_data']:
        if row['side'] == 1 and bar['low'] <= invalid_px:
            stop_hit = True; break
        elif row['side'] == -1 and bar['high'] >= invalid_px:
            stop_hit = True; break
    
    failed = row['r1_fail'] or stop_hit or not row['ev_hit']
    won = not failed
    
    results_g.append({'date': row['date'], 'won': won})
    prior_mae_all_g.append(row['mae'])

res_g = pd.DataFrame(results_g)
wins_g = res_g['won'].sum()
fails_g = (~res_g['won']).sum()
print(f"  Wins: {wins_g}, Fails: {fails_g}  (target: 55/18)")
print(f"  Delta: wins={wins_g-55}, fails={fails_g-18}")
print()

# === SUMMARY ===
print("=" * 70)
print("SUMMARY: All theories vs Gunship (55 FULL, 18 Failed)")
print("=" * 70)
print(f"{'Theory':<55} {'Wins':>6} {'Fails':>6} {'Match':>8}")
print("-" * 70)
theories = [
    ("A: R1 + Rolling P80 MAE (wins) stop, no EV", wins_a, fails_a),
    ("B: R2 + Rolling P80 MAE (wins) stop, no EV", wins_b, fails_b),
    ("C: Stop-only + EV target required", wins_c, fails_c),
    ("D: R1 + Fixed 0.5% MAE stop, no EV", wins_d, fails_d),
    ("E: R1 + Rolling P80 MAE (wins) + EV target", wins_e, fails_e),
    ("F: R1 + Rolling P80 MAE (ALL) stop, no EV", wins_f, fails_f),
    ("G: R1 + Rolling P80 MAE (ALL) + EV target", wins_g, fails_g),
]
for name, w, f in theories:
    match = "YES" if w == 55 and f == 18 else f"NO (Δ={w-55}/{f-18})"
    print(f"{name:<55} {w:>6} {f:>6} {match:>8}")

# === Detail dump for best theory ===
print()
print("=" * 70)
print("THEORY A DETAILS (sessions that differ from R1 baseline)")
print("=" * 70)
# Show sessions where stop_hit added a fail
stop_fails_a = res_a[~res_a['won'] & ~res_a['r1_fail']]
print("Sessions failed by stop-loss (not caught by R1):")
print(stop_fails_a[['date', 'side', 'stop_hit', 'p80_mae_pct', 'invalid_px']].to_string())
print()

# Show sessions where R1 caught the fail
r1_fails_a = res_a[res_a['r1_fail']]
print("Sessions failed by R1 (cutoff close beyond opp OR):")
print(r1_fails_a[['date', 'side', 'r1_fail', 'stop_hit']].to_string())