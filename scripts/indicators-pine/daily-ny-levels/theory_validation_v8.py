"""
Theory validation v8: Mixed percentiles + final tuning.
Key finding: R1 + TOUCH P90 Session MAE (OR, ALL), applied to OR boundary → 54/18
             R1 + TOUCH P95 Session MAE (OR, ALL), applied to OR boundary → 55/17
Need 55/18. Test mixed bull/bear percentiles.
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
        mae_or = ((or_high - post_bo_5m['low'].min()) / or_high) * 100
    else:
        mae_or = ((post_bo_5m['high'].max() - or_low) / or_low) * 100

    close_at_cutoff = data_5m['close'].iloc[-1]
    r1_fail = (bo_side == 1 and close_at_cutoff < or_low) or \
              (bo_side == -1 and close_at_cutoff > or_high)

    bar_data = []
    for idx, row in post_bo_5m.iterrows():
        bar_data.append({'high': row['high'], 'low': row['low'], 'close': row['close']})

    sessions.append({
        'date': date, 'side': bo_side, 'or_high': or_high, 'or_low': or_low,
        'bo_px': bo_px, 'mae_or': mae_or,
        'close_at_cutoff': close_at_cutoff, 'r1_fail': r1_fail,
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

# Print all available percentile values
print("Session MAE from OR (ALL sessions) percentile values:")
for pct in [70, 75, 80, 85, 90, 92, 95, 97, 98, 99, 100]:
    bull_p = p_nearest(bull_all['mae_or'], pct)
    bear_p = p_nearest(bear_all['mae_or'], pct)
    print(f"  P{pct}: bull={bull_p:.4f}%, bear={bear_p:.4f}%")
print()

# === Mixed percentile sweep: TOUCH, applied to OR boundary ===
print("=" * 70)
print("MIXED PERCENTILE: R1 + TOUCH Session MAE (OR, ALL), applied to OR boundary")
print("=" * 70)
print(f"{'Bull Pct':>10} {'Bear Pct':>10} {'Bull MAE':>10} {'Bear MAE':>10} {'Wins':>6} {'Fails':>6} {'Match':>12}")
print("-" * 70)

for bull_pct in [85, 90, 92, 95, 97]:
    for bear_pct in [85, 90, 92, 95, 97]:
        bull_p = p_nearest(bull_all['mae_or'], bull_pct)
        bear_p = p_nearest(bear_all['mae_or'], bear_pct)
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
        match = "YES" if w == 55 and f == 18 else f"Δ={w-55}/{f-18}"
        print(f"  P{bull_pct:>3}    P{bear_pct:>3}   {bull_p:>8.3f}% {bear_p:>8.3f}%   {w:>4}   {f:>4}   {match:>12}")
print()

# === Mixed percentile sweep: TOUCH, applied to BO px ===
print("=" * 70)
print("MIXED PERCENTILE: R1 + TOUCH Session MAE (OR, ALL), applied to BO px")
print("=" * 70)
print(f"{'Bull Pct':>10} {'Bear Pct':>10} {'Bull MAE':>10} {'Bear MAE':>10} {'Wins':>6} {'Fails':>6} {'Match':>12}")
print("-" * 70)

for bull_pct in [85, 90, 92, 95, 97]:
    for bear_pct in [85, 90, 92, 95, 97]:
        bull_p = p_nearest(bull_all['mae_or'], bull_pct)
        bear_p = p_nearest(bear_all['mae_or'], bear_pct)
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
        match = "YES" if w == 55 and f == 18 else f"Δ={w-55}/{f-18}"
        print(f"  P{bull_pct:>3}    P{bear_pct:>3}   {bull_p:>8.3f}% {bear_p:>8.3f}%   {w:>4}   {f:>4}   {match:>12}")
print()

# === Mixed percentile sweep: CLOSE, applied to OR boundary ===
print("=" * 70)
print("MIXED PERCENTILE: R1 + CLOSE Session MAE (OR, ALL), applied to OR boundary")
print("=" * 70)
print(f"{'Bull Pct':>10} {'Bear Pct':>10} {'Bull MAE':>10} {'Bear MAE':>10} {'Wins':>6} {'Fails':>6} {'Match':>12}")
print("-" * 70)

for bull_pct in [80, 85, 90, 92, 95]:
    for bear_pct in [80, 85, 90, 92, 95]:
        bull_p = p_nearest(bull_all['mae_or'], bull_pct)
        bear_p = p_nearest(bear_all['mae_or'], bear_pct)
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
        match = "YES" if w == 55 and f == 18 else f"Δ={w-55}/{f-18}"
        print(f"  P{bull_pct:>3}    P{bear_pct:>3}   {bull_p:>8.3f}% {bear_p:>8.3f}%   {w:>4}   {f:>4}   {match:>12}")
print()

# === Mixed percentile sweep: CLOSE, applied to BO px ===
print("=" * 70)
print("MIXED PERCENTILE: R1 + CLOSE Session MAE (OR, ALL), applied to BO px")
print("=" * 70)
print(f"{'Bull Pct':>10} {'Bear Pct':>10} {'Bull MAE':>10} {'Bear MAE':>10} {'Wins':>6} {'Fails':>6} {'Match':>12}")
print("-" * 70)

for bull_pct in [80, 85, 90, 92, 95]:
    for bear_pct in [80, 85, 90, 92, 95]:
        bull_p = p_nearest(bull_all['mae_or'], bull_pct)
        bear_p = p_nearest(bear_all['mae_or'], bear_pct)
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
        match = "YES" if w == 55 and f == 18 else f"Δ={w-55}/{f-18}"
        print(f"  P{bull_pct:>3}    P{bear_pct:>3}   {bull_p:>8.3f}% {bear_p:>8.3f}%   {w:>4}   {f:>4}   {match:>12}")