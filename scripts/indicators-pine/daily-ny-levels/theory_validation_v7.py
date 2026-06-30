"""
Theory validation v7: Fine-tune to exactly 55/18.
Best candidate: R1 + CLOSE P90 Session MAE (OR, ALL), applied to BO px → 55/17
Need 1 more fail (2026-05-20, an R3 fail).

Test: combine R1 + CLOSE P90 stop + selective R3 (touch opp OR only if MAE exceeds threshold)
Also test: applied to OR boundary with various percentiles.
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

OR_START = 1100; OR_END = 1115; CUTOFF = 1230

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
        mae_bo = ((bo_px - post_bo_5m['low'].min()) / bo_px) * 100
        mae_or = ((or_high - post_bo_5m['low'].min()) / or_high) * 100
    else:
        mfe = ((bo_px - post_bo_5m['low'].min()) / bo_px) * 100
        mae_bo = ((post_bo_5m['high'].max() - bo_px) / bo_px) * 100
        mae_or = ((post_bo_5m['high'].max() - or_low) / or_low) * 100

    close_at_cutoff = data_5m['close'].iloc[-1]
    r1_fail = (bo_side == 1 and close_at_cutoff < or_low) or \
              (bo_side == -1 and close_at_cutoff > or_high)

    r3_fail = False
    r3_low = None; r3_high = None
    for idx, row in post_bo_5m.iterrows():
        if bo_side == 1 and row['low'] < or_low:
            r3_fail = True; r3_low = row['low']; break
        elif bo_side == -1 and row['high'] > or_high:
            r3_fail = True; r3_high = row['high']; break

    bar_data = []
    for idx, row in post_bo_5m.iterrows():
        bar_data.append({'high': row['high'], 'low': row['low'], 'close': row['close']})

    sessions.append({
        'date': date, 'side': bo_side, 'or_high': or_high, 'or_low': or_low,
        'bo_px': bo_px, 'mfe': mfe, 'mae_bo': mae_bo, 'mae_or': mae_or,
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

bull_all = df[df['side'] == 1]
bear_all = df[df['side'] == -1]

# === Best candidate: R1 + CLOSE P90 Session MAE (OR, ALL), applied to BO px ===
bull_p90 = p_nearest(bull_all['mae_or'], 90)
bear_p90 = p_nearest(bear_all['mae_or'], 90)
print(f"P90 Session MAE (OR, ALL): bull={bull_p90:.3f}%, bear={bear_p90:.3f}%")
print()

# Show the 2 stop-only fails at P90
print("=" * 70)
print("R1 + CLOSE P90 Session MAE (OR, ALL), applied to BO px — DETAILS")
print("=" * 70)
results = []
for i, row in df.iterrows():
    p90 = bull_p90 if row['side'] == 1 else bear_p90
    invalid_px = row['bo_px'] * (1 - row['side'] * p90 / 100)
    stop_hit = False
    for bar in row['bar_data']:
        if row['side'] == 1 and bar['close'] <= invalid_px:
            stop_hit = True; break
        elif row['side'] == -1 and bar['close'] >= invalid_px:
            stop_hit = True; break
    failed = row['r1_fail'] or stop_hit
    won = not failed
    results.append({'date': row['date'], 'won': won, 'r1_fail': row['r1_fail'],
                    'stop_hit': stop_hit, 'r3_fail': row['r3_fail'],
                    'side': row['side'], 'mae_or': row['mae_or']})

res = pd.DataFrame(results)
w = res['won'].sum()
f = (~res['won']).sum()
stop_only = res[~res['won'] & ~res['r1_fail']]
print(f"  wins={w}, fails={f}  (Δ={w-55}/{f-18})")
print(f"  Stop-only fails: {len(stop_only)}")
for _, r in stop_only.iterrows():
    print(f"    {r['date']} side={r['side']} mae_or={r['mae_or']:.3f}% r3_fail={r['r3_fail']}")

# R3-only fails (not R1, not stop)
r3_only = res[~res['won'] & res['r3_fail'] & ~res['r1_fail'] & ~res['stop_hit']]
print(f"\n  R3-only fails (not caught by R1 or stop): {len(r3_only)}")
for _, r in r3_only.iterrows():
    print(f"    {r['date']} side={r['side']} mae_or={r['mae_or']:.3f}%")
print()

# === Theory HH: R1 + CLOSE P90 stop + R3 (but only for sessions where stop doesn't catch) ===
# This is just R1 + CLOSE P90 stop + R3 = R1 + R3 + CLOSE P90 stop
print("=" * 70)
print("THEORY HH: R1 + R3 + CLOSE P90 Session MAE (OR, ALL), applied to BO px")
print("=" * 70)
results = []
for i, row in df.iterrows():
    p90 = bull_p90 if row['side'] == 1 else bear_p90
    invalid_px = row['bo_px'] * (1 - row['side'] * p90 / 100)
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
print(f"  wins={w}, fails={f}  (Δ={w-55}/{f-18})")
print()

# === Theory II: R1 + CLOSE P90 stop + selective R3 (only if MAE > P80) ===
print("=" * 70)
print("THEORY II: R1 + CLOSE P90 stop + R3 (only if mae_or > P80 Session MAE)")
print("=" * 70)
bull_p80 = p_nearest(bull_all['mae_or'], 80)
bear_p80 = p_nearest(bear_all['mae_or'], 80)
print(f"  P80 Session MAE (OR, ALL): bull={bull_p80:.3f}%, bear={bear_p80:.3f}%")
results = []
for i, row in df.iterrows():
    p90 = bull_p90 if row['side'] == 1 else bear_p90
    invalid_px = row['bo_px'] * (1 - row['side'] * p90 / 100)
    stop_hit = False
    for bar in row['bar_data']:
        if row['side'] == 1 and bar['close'] <= invalid_px:
            stop_hit = True; break
        elif row['side'] == -1 and bar['close'] >= invalid_px:
            stop_hit = True; break
    p80 = bull_p80 if row['side'] == 1 else bear_p80
    selective_r3 = row['r3_fail'] and (row['mae_or'] > p80)
    failed = row['r1_fail'] or stop_hit or selective_r3
    won = not failed
    results.append(won)
w = sum(results)
f = len(results) - w
print(f"  wins={w}, fails={f}  (Δ={w-55}/{f-18})")
print()

# === Theory JJ: R1 + CLOSE P90 stop + selective R3 (only if MAE > P90) ===
print("=" * 70)
print("THEORY JJ: R1 + CLOSE P90 stop + R3 (only if mae_or > P90 Session MAE)")
print("=" * 70)
results = []
for i, row in df.iterrows():
    p90 = bull_p90 if row['side'] == 1 else bear_p90
    invalid_px = row['bo_px'] * (1 - row['side'] * p90 / 100)
    stop_hit = False
    for bar in row['bar_data']:
        if row['side'] == 1 and bar['close'] <= invalid_px:
            stop_hit = True; break
        elif row['side'] == -1 and bar['close'] >= invalid_px:
            stop_hit = True; break
    selective_r3 = row['r3_fail'] and (row['mae_or'] > p90)
    failed = row['r1_fail'] or stop_hit or selective_r3
    won = not failed
    results.append(won)
w = sum(results)
f = len(results) - w
print(f"  wins={w}, fails={f}  (Δ={w-55}/{f-18})")
print()

# === Theory KK: R1 + CLOSE P90 stop + selective R3 (only if MAE > P95) ===
bull_p95 = p_nearest(bull_all['mae_or'], 95)
bear_p95 = p_nearest(bear_all['mae_or'], 95)
print("=" * 70)
print("THEORY KK: R1 + CLOSE P90 stop + R3 (only if mae_or > P95 Session MAE)")
print(f"  P95: bull={bull_p95:.3f}%, bear={bear_p95:.3f}%")
print("=" * 70)
results = []
for i, row in df.iterrows():
    p90 = bull_p90 if row['side'] == 1 else bear_p90
    invalid_px = row['bo_px'] * (1 - row['side'] * p90 / 100)
    stop_hit = False
    for bar in row['bar_data']:
        if row['side'] == 1 and bar['close'] <= invalid_px:
            stop_hit = True; break
        elif row['side'] == -1 and bar['close'] >= invalid_px:
            stop_hit = True; break
    p95 = bull_p95 if row['side'] == 1 else bear_p95
    selective_r3 = row['r3_fail'] and (row['mae_or'] > p95)
    failed = row['r1_fail'] or stop_hit or selective_r3
    won = not failed
    results.append(won)
w = sum(results)
f = len(results) - w
print(f"  wins={w}, fails={f}  (Δ={w-55}/{f-18})")
print()

# === Theory LL: R1 + TOUCH P90 stop (applied to OR boundary, not BO px) ===
print("=" * 70)
print("SWEEP: R1 + TOUCH P{X} Session MAE (OR, ALL), applied to OR boundary")
print("=" * 70)
for pct in [80, 85, 90, 95]:
    bull_p = p_nearest(bull_all['mae_or'], pct)
    bear_p = p_nearest(bear_all['mae_or'], pct)
    results = []
    for i, row in df.iterrows():
        p_mae = bull_p if row['side'] == 1 else bear_p
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

# === Theory MM: R1 + CLOSE P{X} Session MAE (OR, ALL), applied to OR boundary ===
print("=" * 70)
print("SWEEP: R1 + CLOSE P{X} Session MAE (OR, ALL), applied to OR boundary")
print("=" * 70)
for pct in [80, 85, 90, 95]:
    bull_p = p_nearest(bull_all['mae_or'], pct)
    bear_p = p_nearest(bear_all['mae_or'], pct)
    results = []
    for i, row in df.iterrows():
        p_mae = bull_p if row['side'] == 1 else bear_p
        ref = row['or_high'] if row['side'] == 1 else row['or_low']
        invalid_px = ref * (1 - row['side'] * p_mae / 100)
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
    print(f"  P{pct}: bull={bull_p:.3f}%, bear={bear_p:.3f}% → wins={w}, fails={f}  (Δ={w-55}/{f-18})")
print()

# === Theory NN: R1 + CLOSE P90 stop + R3 (touch opp OR) — but R3 only if close also beyond opp OR ===
# i.e., R3 fail only counts if the touching bar also CLOSES beyond opp OR
print("=" * 70)
print("THEORY NN: R1 + CLOSE P90 stop + R2 (any 5m close beyond opp OR)")
print("=" * 70)
results = []
for i, row in df.iterrows():
    p90 = bull_p90 if row['side'] == 1 else bear_p90
    invalid_px = row['bo_px'] * (1 - row['side'] * p90 / 100)
    stop_hit = False
    for bar in row['bar_data']:
        if row['side'] == 1 and bar['close'] <= invalid_px:
            stop_hit = True; break
        elif row['side'] == -1 and bar['close'] >= invalid_px:
            stop_hit = True; break
    # R2: any 5m close beyond opp OR
    r2_fail = False
    for bar in row['bar_data']:
        if row['side'] == 1 and bar['close'] < row['or_low']:
            r2_fail = True; break
        elif row['side'] == -1 and bar['close'] > row['or_high']:
            r2_fail = True; break
    failed = row['r1_fail'] or stop_hit or r2_fail
    won = not failed
    results.append(won)
w = sum(results)
f = len(results) - w
print(f"  wins={w}, fails={f}  (Δ={w-55}/{f-18})")
print()

# === Theory OO: R1 + CLOSE P90 stop + R3 (touch) — but only count R3 if the touch bar's close is within X% of opp OR ===
print("=" * 70)
print("THEORY OO: R1 + CLOSE P90 stop + R3 (touch opp OR, any)")
print("=" * 70)
results = []
for i, row in df.iterrows():
    p90 = bull_p90 if row['side'] == 1 else bear_p90
    invalid_px = row['bo_px'] * (1 - row['side'] * p90 / 100)
    stop_hit = False
    for bar in row['bar_data']:
        if row['side'] == 1 and bar['close'] <= invalid_px:
            stop_hit = True; break
        elif row['side'] == -1 and bar['close'] >= invalid_px:
            stop_hit = True; break
    failed = row['r1_fail'] or stop_hit or row['r3_fail']
    won = not failed
    results.append(won)
w = sum(results)
f = len(results) - w
print(f"  wins={w}, fails={f}  (Δ={w-55}/{f-18})")
print()

# === Show all R3-only fails (not R1, not stop at P90) ===
print("=" * 70)
print("R3-only fails at P90 CLOSE stop (not caught by R1 or stop)")
print("=" * 70)
r3_only_sessions = []
for i, row in df.iterrows():
    if row['r1_fail']: continue
    p90 = bull_p90 if row['side'] == 1 else bear_p90
    invalid_px = row['bo_px'] * (1 - row['side'] * p90 / 100)
    stop_hit = False
    for bar in row['bar_data']:
        if row['side'] == 1 and bar['close'] <= invalid_px:
            stop_hit = True; break
        elif row['side'] == -1 and bar['close'] >= invalid_px:
            stop_hit = True; break
    if row['r3_fail'] and not stop_hit:
        r3_only_sessions.append({
            'date': row['date'], 'side': row['side'],
            'mae_or': row['mae_or'], 'mae_bo': row['mae_bo'],
            'close_at_cutoff': row['close_at_cutoff'],
            'or_low': row['or_low'], 'or_high': row['or_high'],
        })

r3_df = pd.DataFrame(r3_only_sessions)
print(r3_df.to_string())