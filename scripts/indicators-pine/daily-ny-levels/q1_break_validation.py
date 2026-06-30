"""
Q1 Break validation: Test classification rules against Gunship.
Q1 Break: OR=0600-0830, cutoff=1200, days=23456 (Mon-Fri)

Gunship target: 44 FULL / 29 Failed (N=73)

Gunship live session levels (x=56, bear breakout, BO px=29643.25):
  BO Entry:       29,643.25
  PB Entry:       29,690.67  (PB entry — p25 MAE)
  BO Cashflow:    29,567.70  (BO Cashflow — p20 MFE, 0.255%)
  MED MFE:        29,495.59  (MED MFE — p50 Red)
  MAX MFE:        29,469.52  (MAX MFE — p75 Red)
  BO Inval:       29,796.00  (PB/BO Invalidation — p80 MAE from breakout)
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

# Q1 Break preset
OR_START = 600   # 06:00 ET
OR_END = 830     # 08:30 ET
CUTOFF = 1200    # 12:00 ET
TARGET_WINS = 44
TARGET_FAILS = 29
TARGET_N = 73

# Build sessions
sessions = []
for date, day_1m in df_1m.groupby('date'):
    if date.weekday() not in [0, 1, 2, 3, 4]:  # Mon-Fri
        continue
    session_1m = df_1m[(df_1m['date'] == date) & (df_1m['et_hhmm'] >= OR_START) & (df_1m['et_hhmm'] < CUTOFF)]
    session_5m = df_5m[(df_5m['date'] == date) & (df_5m['et_hhmm'] >= OR_START) & (df_5m['et_hhmm'] < CUTOFF)]
    if session_1m.empty or session_5m.empty:
        continue
    
    or_bars = session_1m[(session_1m['et_hhmm'] >= OR_START) & (session_1m['et_hhmm'] < OR_END)]
    if or_bars.empty:
        continue
    or_high = or_bars['high'].max()
    or_low = or_bars['low'].min()
    
    data_1m = session_1m[session_1m['et_hhmm'] >= OR_END]
    data_5m = session_5m[session_5m['et_hhmm'] >= OR_END]
    if data_1m.empty or data_5m.empty:
        continue
    
    # 1m breakout detection
    bo_side = 0; bo_px = None; bo_idx = None
    for idx, row in data_1m.iterrows():
        if row['close'] > or_high:
            bo_side = 1; bo_px = row['close']; bo_idx = idx; break
        elif row['close'] < or_low:
            bo_side = -1; bo_px = row['close']; bo_idx = idx; break
    if bo_side == 0:
        continue
    
    # Find 5m bar containing the 1m breakout
    bo_5m_idx = None
    for idx in data_5m.index:
        if idx >= bo_idx:
            bo_5m_idx = idx; break
    if bo_5m_idx is None:
        bo_5m_idx = data_5m.index[0]
    
    post_bo_5m = data_5m.loc[bo_5m_idx:]
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
    
    # R2: any 5m close beyond opp OR
    r2_fail = False
    for idx, row in post_bo_5m.iterrows():
        if bo_side == 1 and row['close'] < or_low:
            r2_fail = True; break
        elif bo_side == -1 and row['close'] > or_high:
            r2_fail = True; break
    
    # R3: any 5m touch beyond opp OR
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
        'close_at_cutoff': close_at_cutoff, 'r1_fail': r1_fail,
        'r2_fail': r2_fail, 'r3_fail': r3_fail,
        'bar_data': bar_data,
    })

df = pd.DataFrame(sessions)
print(f"Q1 Break: N={len(df)} (target {TARGET_N})")
print(f"  Bull: {(df['side']==1).sum()}, Bear: {(df['side']==-1).sum()}")
print(f"  R1: {(~df['r1_fail']).sum()}/{df['r1_fail'].sum()}")
print(f"  R2: {(~df['r2_fail']).sum()}/{df['r2_fail'].sum()}")
print(f"  R3: {(~df['r3_fail']).sum()}/{df['r3_fail'].sum()}")
print(f"  Target: {TARGET_WINS}/{TARGET_FAILS}")
print()

# === Verify Gunship levels ===
print("=" * 80)
print("GUNSHIP LEVEL VERIFICATION (Bear breakout, BO px=29643.25)")
print("=" * 80)

# Today's bear breakout: BO px = 29643.25
# Gunship levels:
#   BO Inval = 29796.00 → P80 MAE = (29796 - 29643.25) / 29643.25 * 100 = 0.515%
#   PB Entry = 29690.67 → P25 MAE = (29690.67 - 29643.25) / 29643.25 * 100 = 0.160%
#   BO Cashflow = 29567.70 → P20 MFE = (29643.25 - 29567.70) / 29643.25 * 100 = 0.255%
#   MED MFE = 29495.59 → P50 Red MFE = (29643.25 - 29495.59) / 29643.25 * 100 = 0.498%
#   MAX MFE = 29469.52 → P75 Red MFE = (29643.25 - 29469.52) / 29643.25 * 100 = 0.586%

gunship_bo_px = 29643.25
gunship_levels = {
    'BO Inval':    29796.00,
    'PB Entry':    29690.67,
    'BO Cashflow': 29567.70,
    'MED MFE':     29495.59,
    'MAX MFE':     29469.52,
}

print(f"  Gunship BO px: {gunship_bo_px}")
for name, price in gunship_levels.items():
    if 'Inval' in name or 'PB' in name:
        pct = (price - gunship_bo_px) / gunship_bo_px * 100
        print(f"  {name:15s}: {price:>10.2f}  ({pct:+.3f}%)")
    else:
        pct = (gunship_bo_px - price) / gunship_bo_px * 100
        print(f"  {name:15s}: {price:>10.2f}  ({pct:+.3f}%)")

# Compute Python percentiles for bear sessions
bear_all = df[df['side'] == -1]
bear_r1_wins = df[(df['side'] == -1) & ~df['r1_fail']]
print(f"\n  Bear sessions: {len(bear_all)} (ALL), {len(bear_r1_wins)} (R1 wins)")
print(f"\n  Python BO MAE percentiles (bear, ALL):")
for pct in [20, 25, 50, 75, 80, 85, 90, 95]:
    p = p_nearest(bear_all['mae_bo'], pct)
    print(f"    P{pct}: {p:.3f}%")

print(f"\n  Python BO MAE percentiles (bear, R1 wins):")
for pct in [20, 25, 50, 75, 80, 85, 90, 95]:
    p = p_nearest(bear_r1_wins['mae_bo'], pct)
    print(f"    P{pct}: {p:.3f}%")

# Gunship P80 MAE = 0.515% → check which sample/percentile matches
gunship_p80_mae = (29796.00 - 29643.25) / 29643.25 * 100
print(f"\n  Gunship P80 MAE from chart: {gunship_p80_mae:.3f}%")
print(f"  Python P80 BO MAE (bear, ALL): {p_nearest(bear_all['mae_bo'], 80):.3f}%")
print(f"  Python P80 BO MAE (bear, R1 wins): {p_nearest(bear_r1_wins['mae_bo'], 80):.3f}%")

# Gunship P25 MAE = 0.160% → PB Entry
gunship_p25_mae = (29690.67 - 29643.25) / 29643.25 * 100
print(f"\n  Gunship P25 MAE (PB Entry): {gunship_p25_mae:.3f}%")
print(f"  Python P25 BO MAE (bear, ALL): {p_nearest(bear_all['mae_bo'], 25):.3f}%")
print(f"  Python P25 BO MAE (bear, R1 wins): {p_nearest(bear_r1_wins['mae_bo'], 25):.3f}%")

# Gunship P20 MFE = 0.255% → BO Cashflow
gunship_p20_mfe = (29643.25 - 29567.70) / 29643.25 * 100
print(f"\n  Gunship P20 MFE (BO Cashflow): {gunship_p20_mfe:.3f}%")
print(f"  Python P20 MFE (bear, ALL): {p_nearest(bear_all['mfe'], 20):.3f}%")
print(f"  Python P20 MFE (bear, R1 wins): {p_nearest(bear_r1_wins['mfe'], 20):.3f}%")

# Gunship P50 Red MFE = 0.498% → MED MFE
gunship_p50_red_mfe = (29643.25 - 29495.59) / 29643.25 * 100
bear_fails = df[(df['side'] == -1) & (df['r1_fail'] | df['r2_fail'] | df['r3_fail'])]
print(f"\n  Gunship P50 Red MFE (MED MFE): {gunship_p50_red_mfe:.3f}%")
print(f"  Python P50 MFE (bear, ALL): {p_nearest(bear_all['mfe'], 50):.3f}%")
print(f"  Python P50 MFE (bear, R1 wins): {p_nearest(bear_r1_wins['mfe'], 50):.3f}%")
if len(bear_fails) > 0:
    print(f"  Python P50 MFE (bear, fails): {p_nearest(bear_fails['mfe'], 50):.3f}%")

# Gunship P75 Red MFE = 0.586% → MAX MFE
gunship_p75_red_mfe = (29643.25 - 29469.52) / 29643.25 * 100
print(f"\n  Gunship P75 Red MFE (MAX MFE): {gunship_p75_red_mfe:.3f}%")
print(f"  Python P75 MFE (bear, ALL): {p_nearest(bear_all['mfe'], 75):.3f}%")
print(f"  Python P75 MFE (bear, R1 wins): {p_nearest(bear_r1_wins['mfe'], 75):.3f}%")
if len(bear_fails) > 0:
    print(f"  Python P75 MFE (bear, fails): {p_nearest(bear_fails['mfe'], 75):.3f}%")

print()

# === Test classification rules ===
print("=" * 80)
print("CLASSIFICATION RULE TESTING")
print("=" * 80)

# R1/R2/R3 baselines
print(f"\n  R1: {(~df['r1_fail']).sum()}/{df['r1_fail'].sum()} (target {TARGET_WINS}/{TARGET_FAILS})")
print(f"  R2: {(~df['r2_fail']).sum()}/{df['r2_fail'].sum()}")
print(f"  R3: {(~df['r3_fail']).sum()}/{df['r3_fail'].sum()}")
print()

# Sweep: R1 + P{X} BO MAE (ALL, TOUCH, BO px)
print("=" * 80)
print("SWEEP: R1 + P{X} BO MAE (ALL, TOUCH, BO px) — nearest-rank")
print("=" * 80)
bull_all = df[df['side'] == 1]
bear_all = df[df['side'] == -1]
for pct in [75, 80, 85, 90, 92, 95, 97]:
    bull_p = p_nearest(bull_all['mae_bo'], pct)
    bear_p = p_nearest(bear_all['mae_bo'], pct)
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
        results.append(not failed)
    w = sum(results)
    f = len(results) - w
    match = "✅" if w == TARGET_WINS and f == TARGET_FAILS else "❌"
    print(f"  P{pct}: bull={bull_p:.3f}%, bear={bear_p:.3f}% → {w}/{f} {match} (Δ={w-TARGET_WINS}/{f-TARGET_FAILS})")
print()

# Sweep: R2 + P{X} BO MAE (ALL, TOUCH, BO px)
print("=" * 80)
print("SWEEP: R2 + P{X} BO MAE (ALL, TOUCH, BO px) — nearest-rank")
print("=" * 80)
for pct in [75, 80, 85, 90, 92, 95, 97]:
    bull_p = p_nearest(bull_all['mae_bo'], pct)
    bear_p = p_nearest(bear_all['mae_bo'], pct)
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
        failed = row['r2_fail'] or stop_hit
        results.append(not failed)
    w = sum(results)
    f = len(results) - w
    match = "✅" if w == TARGET_WINS and f == TARGET_FAILS else "❌"
    print(f"  P{pct}: bull={bull_p:.3f}%, bear={bear_p:.3f}% → {w}/{f} {match} (Δ={w-TARGET_WINS}/{f-TARGET_FAILS})")
print()

# Sweep: R3 + P{X} BO MAE (ALL, TOUCH, BO px)
print("=" * 80)
print("SWEEP: R3 + P{X} BO MAE (ALL, TOUCH, BO px) — nearest-rank")
print("=" * 80)
for pct in [75, 80, 85, 90, 92, 95, 97]:
    bull_p = p_nearest(bull_all['mae_bo'], pct)
    bear_p = p_nearest(bear_all['mae_bo'], pct)
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
        failed = row['r3_fail'] or stop_hit
        results.append(not failed)
    w = sum(results)
    f = len(results) - w
    match = "✅" if w == TARGET_WINS and f == TARGET_FAILS else "❌"
    print(f"  P{pct}: bull={bull_p:.3f}%, bear={bear_p:.3f}% → {w}/{f} {match} (Δ={w-TARGET_WINS}/{f-TARGET_FAILS})")
print()

# Sweep: R1 + P{X} Session MAE from OR (ALL, TOUCH, OR boundary)
print("=" * 80)
print("SWEEP: R1 + P{X} Session MAE from OR (ALL, TOUCH, OR boundary) — nearest-rank")
print("=" * 80)
for pct in [75, 80, 85, 90, 92, 95, 97]:
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
        results.append(not failed)
    w = sum(results)
    f = len(results) - w
    match = "✅" if w == TARGET_WINS and f == TARGET_FAILS else "❌"
    print(f"  P{pct}: bull={bull_p:.3f}%, bear={bear_p:.3f}% → {w}/{f} {match} (Δ={w-TARGET_WINS}/{f-TARGET_FAILS})")
print()

# Sweep: R2 + P{X} Session MAE from OR (ALL, TOUCH, OR boundary)
print("=" * 80)
print("SWEEP: R2 + P{X} Session MAE from OR (ALL, TOUCH, OR boundary) — nearest-rank")
print("=" * 80)
for pct in [75, 80, 85, 90, 92, 95, 97]:
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
        failed = row['r2_fail'] or stop_hit
        results.append(not failed)
    w = sum(results)
    f = len(results) - w
    match = "✅" if w == TARGET_WINS and f == TARGET_FAILS else "❌"
    print(f"  P{pct}: bull={bull_p:.3f}%, bear={bear_p:.3f}% → {w}/{f} {match} (Δ={w-TARGET_WINS}/{f-TARGET_FAILS})")
print()

# Sweep: R3 + P{X} Session MAE from OR (ALL, TOUCH, OR boundary)
print("=" * 80)
print("SWEEP: R3 + P{X} Session MAE from OR (ALL, TOUCH, OR boundary) — nearest-rank")
print("=" * 80)
for pct in [75, 80, 85, 90, 92, 95, 97]:
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
        failed = row['r3_fail'] or stop_hit
        results.append(not failed)
    w = sum(results)
    f = len(results) - w
    match = "✅" if w == TARGET_WINS and f == TARGET_FAILS else "❌"
    print(f"  P{pct}: bull={bull_p:.3f}%, bear={bear_p:.3f}% → {w}/{f} {match} (Δ={w-TARGET_WINS}/{f-TARGET_FAILS})")
print()

# MFE > 0 AND not R2
print("=" * 80)
print("MFE > 0 AND not R2 = Win")
print("=" * 80)
wins = (df['mfe'] > 0) & (~df['r2_fail'])
w = wins.sum()
f = (~wins).sum()
match = "✅" if w == TARGET_WINS and f == TARGET_FAILS else "❌"
print(f"  {w}/{f} {match} (Δ={w-TARGET_WINS}/{f-TARGET_FAILS})")
print()

# MFE > 0 AND not R3
print("=" * 80)
print("MFE > 0 AND not R3 = Win")
print("=" * 80)
wins = (df['mfe'] > 0) & (~df['r3_fail'])
w = wins.sum()
f = (~wins).sum()
match = "✅" if w == TARGET_WINS and f == TARGET_FAILS else "❌"
print(f"  {w}/{f} {match} (Δ={w-TARGET_WINS}/{f-TARGET_FAILS})")