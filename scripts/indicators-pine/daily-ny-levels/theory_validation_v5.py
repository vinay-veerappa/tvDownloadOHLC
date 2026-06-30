"""
Theory validation v5: Use ACTUAL Gunship P80 MAE value from chart (0.209% for 1100 BO).
Also test: the Gunship may use the P80 MAE from the FULL sample (including today),
not just R1 wins. And it may use TOUCH-based stop with the Gunship's actual P80 value.

From §6.2: BO Inval = 29,711.25, BO px = 29,773.50
  → P80 MAE = (29773.50 - 29711.25) / 29773.50 * 100 = 0.209%
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

    r3_fail = False
    for idx, row in post_bo_5m.iterrows():
        if bo_side == 1 and row['low'] < or_low:
            r3_fail = True; break
        elif bo_side == -1 and row['high'] > or_high:
            r3_fail = True; break

    bar_data = []
    for idx, row in post_bo_5m.iterrows():
        bar_data.append({'high': row['high'], 'low': row['low'], 'close': row['close']})

    sessions.append({
        'date': date, 'side': bo_side, 'or_high': or_high, 'or_low': or_low,
        'bo_px': bo_px, 'mfe': mfe, 'mae': mae,
        'close_at_cutoff': close_at_cutoff, 'r1_fail': r1_fail, 'r3_fail': r3_fail,
        'bar_data': bar_data,
    })

df = pd.DataFrame(sessions)
print(f"Total sessions: {len(df)}")
print(f"R1: {(~df['r1_fail']).sum()} wins / {df['r1_fail'].sum()} fails (target: 55/18)")
print()

def p_nearest(series, p):
    if len(series) == 0: return np.nan
    return np.percentile(series, p, method='nearest')

# The Gunship's actual P80 MAE from chart = 0.209% (from §6.2)
# But this is for the FULL sample including today. Let's compute P80 MAE from
# the full sample of ALL sessions (not just R1 wins) and see what we get.
bull_all = df[df['side'] == 1]
bear_all = df[df['side'] == -1]
r1_wins = df[~df['r1_fail']]
bull_r1_wins = r1_wins[r1_wins['side'] == 1]
bear_r1_wins = r1_wins[r1_wins['side'] == -1]

print("P80 MAE values from different sources:")
print(f"  Bull R1 wins: {p_nearest(bull_r1_wins['mae'], 80):.3f}%")
print(f"  Bear R1 wins: {p_nearest(bear_r1_wins['mae'], 80):.3f}%")
print(f"  Bull ALL:     {p_nearest(bull_all['mae'], 80):.3f}%")
print(f"  Bear ALL:     {p_nearest(bear_all['mae'], 80):.3f}%")
print()

# The chart shows 0.209% for bull. Let's find what sample produces 0.209%.
# Maybe it's P80 of ALL sessions (wins + losses + fakeouts)?
# Or maybe it's computed differently — from session MAE (OR boundary) not BO MAE?

# Let's compute session MAE from OR boundary
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

bull_r1_wins_or = df[(df['side']==1) & ~df['r1_fail']]
bear_r1_wins_or = df[(df['side']==-1) & ~df['r1_fail']]

bull_all_or = df[df['side']==1]
bear_all_or = df[df['side']==-1]
print("P80 Session MAE (from OR boundary):")
print(f"  Bull R1 wins: {p_nearest(bull_r1_wins_or['session_mae_or'], 80):.3f}%")
print(f"  Bear R1 wins: {p_nearest(bear_r1_wins_or['session_mae_or'], 80):.3f}%")
print(f"  Bull ALL:     {p_nearest(bull_all_or['session_mae_or'], 80):.3f}%")
print(f"  Bear ALL:     {p_nearest(bear_all_or['session_mae_or'], 80):.3f}%")
print()

# === Test with actual Gunship P80 MAE = 0.209% (from chart) ===
print("=" * 70)
print("THEORY W: R1 + TOUCH stop at Gunship's actual P80 MAE (0.209% bull, from chart)")
print("=" * 70)
# Use 0.209% for bull (from chart), and compute bear from R1 wins
bear_p80 = p_nearest(bear_r1_wins['mae'], 80)
gunship_bull_p80 = 0.209  # from chart §6.2
print(f"  Bull P80 MAE: {gunship_bull_p80:.3f}% (from chart)")
print(f"  Bear P80 MAE: {bear_p80:.3f}% (from R1 wins)")

results = []
for i, row in df.iterrows():
    p80_mae = gunship_bull_p80 if row['side'] == 1 else bear_p80
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
print(f"  TOUCH stop: wins={w}, fails={f}  (Δ={w-55}/{f-18})")
print(f"  Stop-only fails: {len(stop_only)}")
if len(stop_only) > 0:
    for _, r in stop_only.iterrows():
        orig = df[df['date'] == r['date']].iloc[0]
        print(f"    {r['date']} side={orig['side']} mae={orig['mae']:.3f}%")
print()

# === Same but CLOSE-based ===
print("=" * 70)
print("THEORY X: R1 + CLOSE stop at Gunship's actual P80 MAE (0.209% bull)")
print("=" * 70)
results = []
for i, row in df.iterrows():
    p80_mae = gunship_bull_p80 if row['side'] == 1 else bear_p80
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
print(f"  CLOSE stop: wins={w}, fails={f}  (Δ={w-55}/{f-18})")
print(f"  Stop-only fails: {len(stop_only)}")
if len(stop_only) > 0:
    for _, r in stop_only.iterrows():
        orig = df[df['date'] == r['date']].iloc[0]
        print(f"    {r['date']} side={orig['side']} mae={orig['mae']:.3f}%")
print()

# === Sweep TOUCH stop with different fixed thresholds ===
print("=" * 70)
print("THEORY Y: R1 + TOUCH fixed MAE threshold sweep (BO px anchor)")
print("=" * 70)
for thresh in [0.15, 0.18, 0.20, 0.21, 0.22, 0.25, 0.26, 0.28, 0.30]:
    results = []
    for i, row in df.iterrows():
        invalid_px = row['bo_px'] * (1 - row['side'] * thresh / 100)
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
    print(f"  thresh={thresh:.2f}%: wins={w}, fails={f}  (Δ={w-55}/{f-18})")
print()

# === Sweep CLOSE stop with different fixed thresholds ===
print("=" * 70)
print("THEORY Z: R1 + CLOSE fixed MAE threshold sweep (BO px anchor)")
print("=" * 70)
for thresh in [0.15, 0.18, 0.20, 0.21, 0.22, 0.25, 0.26, 0.28, 0.30, 0.35, 0.40, 0.45, 0.50]:
    results = []
    for i, row in df.iterrows():
        invalid_px = row['bo_px'] * (1 - row['side'] * thresh / 100)
        stop_hit = False
        for bar in row['bar_data']:
            if row['side'] == 1 and bar['close'] <= invalid_px:
                stop_hit = True; break
            elif row['side'] == -1 and bar['close'] >= invalid_px:
                stop_hit = True; break
        failed = row['r1_fail'] or stop_hit
        won = not failed
        results.append(won)
    w = sum(results)
    f = len(results) - w
    print(f"  thresh={thresh:.2f}%: wins={w}, fails={f}  (Δ={w-55}/{f-18})")
print()

# === Combined: R1 + TOUCH stop + R3, with threshold sweep ===
print("=" * 70)
print("THEORY AA: R1 + R3(touch opp OR) + TOUCH fixed MAE threshold sweep")
print("=" * 70)
for thresh in [0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50]:
    results = []
    for i, row in df.iterrows():
        invalid_px = row['bo_px'] * (1 - row['side'] * thresh / 100)
        stop_hit = False
        for bar in row['bar_data']:
            if row['side'] == 1 and bar['low'] <= invalid_px:
                stop_hit = True; break
            elif row['side'] == -1 and bar['high'] >= invalid_px:
                stop_hit = True; break
        failed = row['r1_fail'] or row['r3_fail'] or stop_hit
        won = not failed
        results.append(won)
    w = sum(results)
    f = len(results) - w
    print(f"  thresh={thresh:.2f}%: wins={w}, fails={f}  (Δ={w-55}/{f-18})")
print()

# === Try: R3 + CLOSE fixed MAE threshold (no R1) ===
print("=" * 70)
print("THEORY BB: R3(touch opp OR) + CLOSE fixed MAE threshold sweep")
print("=" * 70)
for thresh in [0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50]:
    results = []
    for i, row in df.iterrows():
        invalid_px = row['bo_px'] * (1 - row['side'] * thresh / 100)
        stop_hit = False
        for bar in row['bar_data']:
            if row['side'] == 1 and bar['close'] <= invalid_px:
                stop_hit = True; break
            elif row['side'] == -1 and bar['close'] >= invalid_px:
                stop_hit = True; break
        failed = row['r3_fail'] or stop_hit
        won = not failed
        results.append(won)
    w = sum(results)
    f = len(results) - w
    print(f"  thresh={thresh:.2f}%: wins={w}, fails={f}  (Δ={w-55}/{f-18})")
print()

# === Try: R1 + R3 + CLOSE fixed MAE threshold ===
print("=" * 70)
print("THEORY CC: R1 + R3(touch opp OR) + CLOSE fixed MAE threshold sweep")
print("=" * 70)
for thresh in [0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50]:
    results = []
    for i, row in df.iterrows():
        invalid_px = row['bo_px'] * (1 - row['side'] * thresh / 100)
        stop_hit = False
        for bar in row['bar_data']:
            if row['side'] == 1 and bar['close'] <= invalid_px:
                stop_hit = True; break
            elif row['side'] == -1 and bar['close'] >= invalid_px:
                stop_hit = True; break
        failed = row['r1_fail'] or row['r3_fail'] or stop_hit
        won = not failed
        results.append(won)
    w = sum(results)
    f = len(results) - w
    print(f"  thresh={thresh:.2f}%: wins={w}, fails={f}  (Δ={w-55}/{f-18})")