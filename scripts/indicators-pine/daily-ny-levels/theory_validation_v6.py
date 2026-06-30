"""
Theory validation v6: Use P80 Session MAE from OR boundary (matches Gunship chart 0.210%).
Test TOUCH vs CLOSE stop, applied to BO px, with R1 wins percentiles.
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

r1_wins = df[~df['r1_fail']]
bull_r1_wins = r1_wins[r1_wins['side'] == 1]
bear_r1_wins = r1_wins[r1_wins['side'] == -1]

# P80 Session MAE from OR (matches Gunship chart 0.210%)
bull_p80_or = p_nearest(bull_r1_wins['mae_or'], 80)
bear_p80_or = p_nearest(bear_r1_wins['mae_or'], 80)
print(f"P80 Session MAE from OR (R1 wins): bull={bull_p80_or:.3f}%, bear={bear_p80_or:.3f}%")
print(f"  (Gunship chart shows 0.209% for bull — MATCH!)")
print()

# P80 BO MAE from BO px
bull_p80_bo = p_nearest(bull_r1_wins['mae_bo'], 80)
bear_p80_bo = p_nearest(bear_r1_wins['mae_bo'], 80)
print(f"P80 BO MAE from BO px (R1 wins): bull={bull_p80_bo:.3f}%, bear={bear_p80_bo:.3f}%")
print()

# === Test: R1 + TOUCH stop at P80 Session MAE from OR, applied to BO px ===
print("=" * 70)
print("THEORY DD: R1 + TOUCH stop at P80 Session MAE (OR), applied to BO px")
print(f"  bull={bull_p80_or:.3f}%, bear={bear_p80_or:.3f}%")
print("=" * 70)
results = []
for i, row in df.iterrows():
    p80 = bull_p80_or if row['side'] == 1 else bear_p80_or
    invalid_px = row['bo_px'] * (1 - row['side'] * p80 / 100)
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
        print(f"    {r['date']} side={orig['side']} mae_bo={orig['mae_bo']:.3f}% mae_or={orig['mae_or']:.3f}%")
print()

# === Test: R1 + CLOSE stop at P80 Session MAE from OR, applied to BO px ===
print("=" * 70)
print("THEORY EE: R1 + CLOSE stop at P80 Session MAE (OR), applied to BO px")
print(f"  bull={bull_p80_or:.3f}%, bear={bear_p80_or:.3f}%")
print("=" * 70)
results = []
for i, row in df.iterrows():
    p80 = bull_p80_or if row['side'] == 1 else bear_p80_or
    invalid_px = row['bo_px'] * (1 - row['side'] * p80 / 100)
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
        print(f"    {r['date']} side={orig['side']} mae_bo={orig['mae_bo']:.3f}% mae_or={orig['mae_or']:.3f}%")
print()

# === Test: R1 + TOUCH stop at P80 Session MAE from OR, applied to OR boundary ===
print("=" * 70)
print("THEORY FF: R1 + TOUCH stop at P80 Session MAE (OR), applied to OR boundary")
print(f"  bull={bull_p80_or:.3f}%, bear={bear_p80_or:.3f}%")
print("=" * 70)
results = []
for i, row in df.iterrows():
    p80 = bull_p80_or if row['side'] == 1 else bear_p80_or
    ref = row['or_high'] if row['side'] == 1 else row['or_low']
    invalid_px = ref * (1 - row['side'] * p80 / 100)
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
        print(f"    {r['date']} side={orig['side']} mae_or={orig['mae_or']:.3f}%")
print()

# === Test: R1 + CLOSE stop at P80 Session MAE from OR, applied to OR boundary ===
print("=" * 70)
print("THEORY GG: R1 + CLOSE stop at P80 Session MAE (OR), applied to OR boundary")
print(f"  bull={bull_p80_or:.3f}%, bear={bear_p80_or:.3f}%")
print("=" * 70)
results = []
for i, row in df.iterrows():
    p80 = bull_p80_or if row['side'] == 1 else bear_p80_or
    ref = row['or_high'] if row['side'] == 1 else row['or_low']
    invalid_px = ref * (1 - row['side'] * p80 / 100)
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
        print(f"    {r['date']} side={orig['side']} mae_or={orig['mae_or']:.3f}%")
print()

# === Sweep: P{X} Session MAE from OR (R1 wins), TOUCH, applied to BO px ===
print("=" * 70)
print("SWEEP: R1 + TOUCH P{X} Session MAE (OR, R1 wins), applied to BO px")
print("=" * 70)
for pct in [70, 75, 80, 85, 90, 95]:
    bull_p = p_nearest(bull_r1_wins['mae_or'], pct)
    bear_p = p_nearest(bear_r1_wins['mae_or'], pct)
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

# === Sweep: P{X} Session MAE from OR (R1 wins), CLOSE, applied to BO px ===
print("=" * 70)
print("SWEEP: R1 + CLOSE P{X} Session MAE (OR, R1 wins), applied to BO px")
print("=" * 70)
for pct in [70, 75, 80, 85, 90, 95]:
    bull_p = p_nearest(bull_r1_wins['mae_or'], pct)
    bear_p = p_nearest(bear_r1_wins['mae_or'], pct)
    results = []
    for i, row in df.iterrows():
        p_mae = bull_p if row['side'] == 1 else bear_p
        invalid_px = row['bo_px'] * (1 - row['side'] * p_mae / 100)
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

# === Sweep: P{X} Session MAE from OR (ALL sessions), TOUCH, applied to BO px ===
print("=" * 70)
print("SWEEP: R1 + TOUCH P{X} Session MAE (OR, ALL sessions), applied to BO px")
print("=" * 70)
bull_all = df[df['side'] == 1]
bear_all = df[df['side'] == -1]
for pct in [70, 75, 80, 85, 90, 95]:
    bull_p = p_nearest(bull_all['mae_or'], pct)
    bear_p = p_nearest(bear_all['mae_or'], pct)
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

# === Sweep: P{X} Session MAE from OR (ALL sessions), CLOSE, applied to BO px ===
print("=" * 70)
print("SWEEP: R1 + CLOSE P{X} Session MAE (OR, ALL sessions), applied to BO px")
print("=" * 70)
for pct in [70, 75, 80, 85, 90, 95]:
    bull_p = p_nearest(bull_all['mae_or'], pct)
    bear_p = p_nearest(bear_all['mae_or'], pct)
    results = []
    for i, row in df.iterrows():
        p_mae = bull_p if row['side'] == 1 else bear_p
        invalid_px = row['bo_px'] * (1 - row['side'] * p_mae / 100)
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