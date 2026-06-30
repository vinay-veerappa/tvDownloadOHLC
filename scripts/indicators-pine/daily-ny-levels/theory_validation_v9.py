"""
Theory validation v9: 
1. Use 1m breakout detection (73 sessions, matching Gunship)
2. Test linear interpolation percentile (not nearest-rank)
3. Test combined bull+bear percentile (not split by side)
4. Test the exact Gunship configuration from the Pine Script
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

    # Use 1m breakout detection (catches 73 sessions, matching Gunship)
    bo_side = 0; bo_px = None; bo_idx = None
    for idx, row in data_1m.iterrows():
        if row['close'] > or_high:
            bo_side = 1; bo_px = row['close']; bo_idx = idx; break
        elif row['close'] < or_low:
            bo_side = -1; bo_px = row['close']; bo_idx = idx; break
    if bo_side == 0: continue

    # Use 5m bars for post-bo tracking (matches chart-level signal logic)
    # Find the 5m bar that contains the 1m breakout
    bo_5m_idx = None
    for idx, row in data_5m.iterrows():
        if idx >= bo_idx:
            bo_5m_idx = idx; break
    if bo_5m_idx is None: bo_5m_idx = data_5m.index[0]
    
    post_bo_5m = data_5m.loc[bo_5m_idx:]
    if bo_side == 1:
        mae_or = ((or_high - post_bo_5m['low'].min()) / or_high) * 100
        mae_bo = ((bo_px - post_bo_5m['low'].min()) / bo_px) * 100
    else:
        mae_or = ((post_bo_5m['high'].max() - or_low) / or_low) * 100
        mae_bo = ((post_bo_5m['high'].max() - bo_px) / bo_px) * 100

    close_at_cutoff = data_5m['close'].iloc[-1]
    r1_fail = (bo_side == 1 and close_at_cutoff < or_low) or \
              (bo_side == -1 and close_at_cutoff > or_high)

    bar_data = []
    for idx, row in post_bo_5m.iterrows():
        bar_data.append({'high': row['high'], 'low': row['low'], 'close': row['close']})

    sessions.append({
        'date': date, 'side': bo_side, 'or_high': or_high, 'or_low': or_low,
        'bo_px': bo_px, 'mae_or': mae_or, 'mae_bo': mae_bo,
        'close_at_cutoff': close_at_cutoff, 'r1_fail': r1_fail,
        'bar_data': bar_data,
    })

df = pd.DataFrame(sessions)
print(f"Total sessions: {len(df)} (target: 73)")
print(f"R1: {(~df['r1_fail']).sum()} wins / {df['r1_fail'].sum()} fails (target: 55/18)")
print()

def p_nearest(series, p):
    if len(series) == 0: return np.nan
    return np.percentile(series, p, method='nearest')

def p_linear(series, p):
    if len(series) == 0: return np.nan
    return np.percentile(series, p, method='linear')

bull_all = df[df['side'] == 1]
bear_all = df[df['side'] == -1]
all_sessions = df

# === Test with 73 sessions: R1 + TOUCH P90 Session MAE (OR, ALL), applied to OR boundary ===
print("=" * 70)
print("73-SESSION: R1 + TOUCH P{X} Session MAE (OR, ALL), applied to OR boundary")
print("=" * 70)
for pct in [80, 85, 90, 92, 95, 97]:
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

# === Test with LINEAR interpolation percentile ===
print("=" * 70)
print("73-SESSION + LINEAR: R1 + TOUCH P{X} Session MAE (OR, ALL), applied to OR boundary")
print("=" * 70)
for pct in [80, 85, 88, 89, 90, 91, 92, 93, 94, 95]:
    bull_p = p_linear(bull_all['mae_or'], pct)
    bear_p = p_linear(bear_all['mae_or'], pct)
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
    print(f"  P{pct}: bull={bull_p:.4f}%, bear={bear_p:.4f}% → wins={w}, fails={f}  (Δ={w-55}/{f-18})")
print()

# === Test with COMBINED percentile (bull+bear together) ===
print("=" * 70)
print("73-SESSION + COMBINED: R1 + TOUCH P{X} Session MAE (ALL combined), applied to OR boundary")
print("=" * 70)
for pct in [80, 85, 88, 89, 90, 91, 92, 93, 94, 95]:
    combined_p = p_nearest(all_sessions['mae_or'], pct)
    results = []
    for i, row in df.iterrows():
        ref = row['or_high'] if row['side'] == 1 else row['or_low']
        invalid_px = ref * (1 - row['side'] * combined_p / 100)
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
    print(f"  P{pct}: combined={combined_p:.4f}% → wins={w}, fails={f}  (Δ={w-55}/{f-18})")
print()

# === Test with COMBINED + LINEAR ===
print("=" * 70)
print("73-SESSION + COMBINED + LINEAR: R1 + TOUCH P{X} Session MAE (ALL), applied to OR boundary")
print("=" * 70)
for pct in [80, 85, 88, 89, 90, 91, 92, 93, 94, 95]:
    combined_p = p_linear(all_sessions['mae_or'], pct)
    results = []
    for i, row in df.iterrows():
        ref = row['or_high'] if row['side'] == 1 else row['or_low']
        invalid_px = ref * (1 - row['side'] * combined_p / 100)
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
    print(f"  P{pct}: combined={combined_p:.4f}% → wins={w}, fails={f}  (Δ={w-55}/{f-18})")
print()

# === Test CLOSE-based with 73 sessions + combined + linear ===
print("=" * 70)
print("73-SESSION + COMBINED + LINEAR: R1 + CLOSE P{X} Session MAE (ALL), applied to OR boundary")
print("=" * 70)
for pct in [80, 85, 88, 89, 90, 91, 92, 93, 94, 95]:
    combined_p = p_linear(all_sessions['mae_or'], pct)
    results = []
    for i, row in df.iterrows():
        ref = row['or_high'] if row['side'] == 1 else row['or_low']
        invalid_px = ref * (1 - row['side'] * combined_p / 100)
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
    print(f"  P{pct}: combined={combined_p:.4f}% → wins={w}, fails={f}  (Δ={w-55}/{f-18})")
print()

# === Test CLOSE-based with 73 sessions + combined + linear, applied to BO px ===
print("=" * 70)
print("73-SESSION + COMBINED + LINEAR: R1 + CLOSE P{X} Session MAE (ALL), applied to BO px")
print("=" * 70)
for pct in [80, 85, 88, 89, 90, 91, 92, 93, 94, 95]:
    combined_p = p_linear(all_sessions['mae_or'], pct)
    results = []
    for i, row in df.iterrows():
        invalid_px = row['bo_px'] * (1 - row['side'] * combined_p / 100)
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
    print(f"  P{pct}: combined={combined_p:.4f}% → wins={w}, fails={f}  (Δ={w-55}/{f-18})")
print()

# === Test TOUCH-based with 73 sessions + combined + linear, applied to BO px ===
print("=" * 70)
print("73-SESSION + COMBINED + LINEAR: R1 + TOUCH P{X} Session MAE (ALL), applied to BO px")
print("=" * 70)
for pct in [80, 85, 88, 89, 90, 91, 92, 93, 94, 95]:
    combined_p = p_linear(all_sessions['mae_or'], pct)
    results = []
    for i, row in df.iterrows():
        invalid_px = row['bo_px'] * (1 - row['side'] * combined_p / 100)
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
    print(f"  P{pct}: combined={combined_p:.4f}% → wins={w}, fails={f}  (Δ={w-55}/{f-18})")