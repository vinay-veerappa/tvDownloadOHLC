"""
Theory validation v4: Fine-tuning to get exactly 55/18.
Best candidates from v3:
  - CLOSE-based P80 MAE from R1 wins: 55/17 (need 1 more fail)
  - Fixed 0.50% MAE close-based: 55/17 (need 1 more fail)

The missing fail is likely 2026-05-20 (confirmed from §6.8.3).
Let's investigate why it's not caught and test combined rules.
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

    # R2: any 5m close beyond opp OR
    r2_fail = False
    r2_fail_bar = None
    for idx, row in post_bo_5m.iterrows():
        if bo_side == 1 and row['close'] < or_low:
            r2_fail = True; r2_fail_bar = idx; break
        elif bo_side == -1 and row['close'] > or_high:
            r2_fail = True; r2_fail_bar = idx; break

    # R3: any 5m touch beyond opp OR
    r3_fail = False
    for idx, row in post_bo_5m.iterrows():
        if bo_side == 1 and row['low'] < or_low:
            r3_fail = True; break
        elif bo_side == -1 and row['high'] > or_high:
            r3_fail = True; break

    target_px = bo_px * (1 + bo_side * EV_TARGET_PCT / 100)
    ev_hit = False
    for idx, row in post_bo_5m.iterrows():
        if bo_side == 1 and row['high'] >= target_px:
            ev_hit = True; break
        elif bo_side == -1 and row['low'] <= target_px:
            ev_hit = True; break

    bar_data = []
    for idx, row in post_bo_5m.iterrows():
        bar_data.append({'idx': idx, 'high': row['high'], 'low': row['low'], 'close': row['close']})

    sessions.append({
        'date': date, 'side': bo_side, 'or_high': or_high, 'or_low': or_low,
        'bo_px': bo_px, 'mfe': mfe, 'mae': mae,
        'close_at_cutoff': close_at_cutoff, 'r1_fail': r1_fail,
        'r2_fail': r2_fail, 'r3_fail': r3_fail,
        'ev_hit': ev_hit, 'bar_data': bar_data,
    })

df = pd.DataFrame(sessions)
print(f"Total sessions: {len(df)}")
print(f"R1: {(~df['r1_fail']).sum()} wins / {df['r1_fail'].sum()} fails")
print(f"R2: {(~df['r2_fail']).sum()} wins / {df['r2_fail'].sum()} fails")
print(f"R3: {(~df['r3_fail']).sum()} wins / {df['r3_fail'].sum()} fails")
print(f"Target: 55/18")
print()

def p_nearest(series, p):
    if len(series) == 0: return np.nan
    return np.percentile(series, p, method='nearest')

r1_wins = df[~df['r1_fail']]
bull_r1_wins = r1_wins[r1_wins['side'] == 1]
bear_r1_wins = r1_wins[r1_wins['side'] == -1]
bull_p80 = p_nearest(bull_r1_wins['mae'], 80)
bear_p80 = p_nearest(bear_r1_wins['mae'], 80)
print(f"P80 MAE (R1 wins): bull={bull_p80:.3f}%, bear={bear_p80:.3f}%")
print()

# === Investigate 2026-05-20 ===
print("=" * 70)
print("INVESTIGATE: 2026-05-20 (confirmed Gunship fail from §6.8.3)")
print("=" * 70)
s = df[df['date'] == pd.Timestamp('2026-05-20').date()]
if len(s) > 0:
    s = s.iloc[0]
    print(f"  side={s['side']}, bo_px={s['bo_px']}, mae={s['mae']:.3f}%, mfe={s['mfe']:.3f}%")
    print(f"  or_high={s['or_high']}, or_low={s['or_low']}")
    print(f"  close_at_cutoff={s['close_at_cutoff']}")
    print(f"  r1_fail={s['r1_fail']}, r2_fail={s['r2_fail']}, r3_fail={s['r3_fail']}")
    print(f"  ev_hit={s['ev_hit']}")
    print(f"  Bull P80 MAE = {bull_p80:.3f}%")
    invalid_px = s['bo_px'] * (1 - s['side'] * bull_p80 / 100)
    print(f"  Invalidation level (P80 MAE): {invalid_px:.2f}")
    print(f"  Bar data (post-bo 5m bars):")
    for bar in s['bar_data']:
        hit = ""
        if s['side'] == 1:
            if bar['low'] <= invalid_px: hit = " ← TOUCH invalid"
            if bar['close'] <= invalid_px: hit += " ← CLOSE invalid"
            if bar['close'] < s['or_low']: hit += " ← R2 fail"
            if bar['low'] < s['or_low']: hit += " ← R3 fail"
        print(f"    {bar['idx']}: H={bar['high']:.2f} L={bar['low']:.2f} C={bar['close']:.2f}{hit}")
print()

# === Theory N: R1 + CLOSE P80 MAE (R1 wins) + R3 (touch opp OR) ===
print("=" * 70)
print("THEORY N: R1 + CLOSE P80 MAE (R1 wins) + R3 (touch opp OR)")
print("=" * 70)
results = []
for i, row in df.iterrows():
    p80_mae = bull_p80 if row['side'] == 1 else bear_p80
    invalid_px = row['bo_px'] * (1 - row['side'] * p80_mae / 100)
    stop_hit = False
    for bar in row['bar_data']:
        if row['side'] == 1 and bar['close'] <= invalid_px:
            stop_hit = True; break
        elif row['side'] == -1 and bar['close'] >= invalid_px:
            stop_hit = True; break
    failed = row['r1_fail'] or stop_hit or row['r3_fail']
    won = not failed
    results.append({'date': row['date'], 'won': won, 'r1_fail': row['r1_fail'],
                    'stop_hit': stop_hit, 'r3_fail': row['r3_fail']})

res = pd.DataFrame(results)
w = res['won'].sum()
f = (~res['won']).sum()
print(f"  wins={w}, fails={f}  (Δ={w-55}/{f-18})")
print()

# === Theory O: R1 + TOUCH P80 MAE (R1 wins) + close-based opp OR ===
print("=" * 70)
print("THEORY O: R1 + TOUCH P80 MAE (R1 wins) — but only count if 5m CLOSE beyond invalid")
print("=" * 70)
results = []
for i, row in df.iterrows():
    p80_mae = bull_p80 if row['side'] == 1 else bear_p80
    invalid_px = row['bo_px'] * (1 - row['side'] * p80_mae / 100)
    stop_hit = False
    for bar in row['bar_data']:
        if row['side'] == 1 and bar['close'] <= invalid_px:
            stop_hit = True; break
        elif row['side'] == -1 and bar['close'] >= invalid_px:
            stop_hit = True; break
    failed = row['r1_fail'] or stop_hit
    won = not failed
    results.append({'date': row['date'], 'won': won, 'r1_fail': row['r1_fail'], 'stop_hit': stop_hit})

res = pd.DataFrame(results)
w = res['won'].sum()
f = (~res['won']).sum()
stop_only = res[~res['won'] & ~res['r1_fail']]
print(f"  wins={w}, fails={f}  (Δ={w-55}/{f-18})")
print(f"  Stop-only fails: {len(stop_only)}")
if len(stop_only) > 0:
    for _, r in stop_only.iterrows():
        orig = df[df['date'] == r['date']].iloc[0]
        print(f"    {r['date']} side={orig['side']} mae={orig['mae']:.3f}%")
print()

# === Theory P: R1 + TOUCH P80 MAE (R1 wins) ===
print("=" * 70)
print("THEORY P: R1 + TOUCH P80 MAE (R1 wins, BO px anchor)")
print("=" * 70)
results = []
for i, row in df.iterrows():
    p80_mae = bull_p80 if row['side'] == 1 else bear_p80
    invalid_px = row['bo_px'] * (1 - row['side'] * p80_mae / 100)
    stop_hit = False
    for bar in row['bar_data']:
        if row['side'] == 1 and bar['low'] <= invalid_px:
            stop_hit = True; break
        elif row['side'] == -1 and bar['high'] >= invalid_px:
            stop_hit = True; break
    failed = row['r1_fail'] or stop_hit
    won = not failed
    results.append({'date': row['date'], 'won': won, 'r1_fail': row['r1_fail'], 'stop_hit': stop_hit})

res = pd.DataFrame(results)
w = res['won'].sum()
f = (~res['won']).sum()
stop_only = res[~res['won'] & ~res['r1_fail']]
print(f"  wins={w}, fails={f}  (Δ={w-55}/{f-18})")
print(f"  Stop-only fails: {len(stop_only)}")
if len(stop_only) > 0:
    for _, r in stop_only.iterrows():
        orig = df[df['date'] == r['date']].iloc[0]
        print(f"    {r['date']} side={orig['side']} mae={orig['mae']:.3f}%")
print()

# === Theory Q: R1 + TOUCH P80 MAE (R1 wins) + only count stop if MAE > P80 ===
# Maybe the stop is only triggered if the session's MAE exceeds P80, not if price touches the level
print("=" * 70)
print("THEORY Q: R1 + (MAE > P80 MAE of R1 wins) = fail")
print("  (Stop triggered by MAE exceeding P80, not by price touching level)")
print("=" * 70)
results = []
for i, row in df.iterrows():
    p80_mae = bull_p80 if row['side'] == 1 else bear_p80
    mae_exceeds = row['mae'] > p80_mae
    failed = row['r1_fail'] or mae_exceeds
    won = not failed
    results.append({'date': row['date'], 'won': won, 'r1_fail': row['r1_fail'], 'mae_exceeds': mae_exceeds})

res = pd.DataFrame(results)
w = res['won'].sum()
f = (~res['won']).sum()
mae_only = res[~res['won'] & ~res['r1_fail']]
print(f"  wins={w}, fails={f}  (Δ={w-55}/{f-18})")
print(f"  MAE-only fails: {len(mae_only)}")
if len(mae_only) > 0:
    for _, r in mae_only.iterrows():
        orig = df[df['date'] == r['date']].iloc[0]
        print(f"    {r['date']} side={orig['side']} mae={orig['mae']:.3f}% (P80={bull_p80 if orig['side']==1 else bear_p80:.3f}%)")
print()

# === Theory R: R1 + (MAE > P80 MAE of R1 wins) + R3 (touch opp OR) ===
print("=" * 70)
print("THEORY R: R1 + (MAE > P80 MAE of R1 wins) + R3 (touch opp OR)")
print("=" * 70)
results = []
for i, row in df.iterrows():
    p80_mae = bull_p80 if row['side'] == 1 else bear_p80
    mae_exceeds = row['mae'] > p80_mae
    failed = row['r1_fail'] or mae_exceeds or row['r3_fail']
    won = not failed
    results.append(won)
w = sum(results)
f = len(results) - w
print(f"  wins={w}, fails={f}  (Δ={w-55}/{f-18})")
print()

# === Theory S: R3 (touch opp OR) + (MAE > P80 MAE of R1 wins) ===
print("=" * 70)
print("THEORY S: R3 (touch opp OR) + (MAE > P80 MAE of R1 wins)")
print("=" * 70)
results = []
for i, row in df.iterrows():
    p80_mae = bull_p80 if row['side'] == 1 else bear_p80
    mae_exceeds = row['mae'] > p80_mae
    failed = row['r3_fail'] or mae_exceeds
    won = not failed
    results.append(won)
w = sum(results)
f = len(results) - w
print(f"  wins={w}, fails={f}  (Δ={w-55}/{f-18})")
print()

# === Theory T: R2 (close opp OR) + (MAE > P80 MAE of R1 wins) ===
print("=" * 70)
print("THEORY T: R2 (close opp OR) + (MAE > P80 MAE of R1 wins)")
print("=" * 70)
results = []
for i, row in df.iterrows():
    p80_mae = bull_p80 if row['side'] == 1 else bear_p80
    mae_exceeds = row['mae'] > p80_mae
    failed = row['r2_fail'] or mae_exceeds
    won = not failed
    results.append(won)
w = sum(results)
f = len(results) - w
print(f"  wins={w}, fails={f}  (Δ={w-55}/{f-18})")
print()

# === Theory U: R1 + (MAE > P80 MAE of ALL sessions) ===
print("=" * 70)
print("THEORY U: R1 + (MAE > P80 MAE of ALL sessions)")
print("=" * 70)
bull_all = df[df['side'] == 1]
bear_all = df[df['side'] == -1]
bull_p80_all = p_nearest(bull_all['mae'], 80)
bear_p80_all = p_nearest(bear_all['mae'], 80)
print(f"  P80 MAE (all): bull={bull_p80_all:.3f}%, bear={bear_p80_all:.3f}%")
results = []
for i, row in df.iterrows():
    p80_mae = bull_p80_all if row['side'] == 1 else bear_p80_all
    mae_exceeds = row['mae'] > p80_mae
    failed = row['r1_fail'] or mae_exceeds
    won = not failed
    results.append(won)
w = sum(results)
f = len(results) - w
print(f"  wins={w}, fails={f}  (Δ={w-55}/{f-18})")
print()

# === Theory V: R1 + (MAE > P80 MAE of ALL) + R3 ===
print("=" * 70)
print("THEORY V: R1 + (MAE > P80 MAE of ALL) + R3")
print("=" * 70)
results = []
for i, row in df.iterrows():
    p80_mae = bull_p80_all if row['side'] == 1 else bear_p80_all
    mae_exceeds = row['mae'] > p80_mae
    failed = row['r1_fail'] or mae_exceeds or row['r3_fail']
    won = not failed
    results.append(won)
w = sum(results)
f = len(results) - w
print(f"  wins={w}, fails={f}  (Δ={w-55}/{f-18})")
print()

# === SUMMARY ===
print("=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"{'Theory':<55} {'Wins':>6} {'Fails':>6} {'Match':>12}")
print("-" * 70)