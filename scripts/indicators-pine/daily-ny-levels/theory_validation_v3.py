"""
Theory validation v3: Close-based stop-loss + percentile sweep.
The Gunship likely uses a 5m CLOSE beyond invalidation (not touch).
Also tests: stop-loss only applies AFTER breakout is latched, and
the invalidation is computed from the full sample.
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

    target_px = bo_px * (1 + bo_side * EV_TARGET_PCT / 100)
    ev_hit = False
    for idx, row in post_bo_5m.iterrows():
        if bo_side == 1 and row['high'] >= target_px:
            ev_hit = True; break
        elif bo_side == -1 and row['low'] <= target_px:
            ev_hit = True; break

    bar_data = []
    for idx, row in post_bo_5m.iterrows():
        bar_data.append({'high': row['high'], 'low': row['low'], 'close': row['close']})

    sessions.append({
        'date': date, 'side': bo_side, 'or_high': or_high, 'or_low': or_low,
        'bo_px': bo_px, 'mfe': mfe, 'mae': mae,
        'close_at_cutoff': close_at_cutoff, 'r1_fail': r1_fail,
        'ev_hit': ev_hit, 'bar_data': bar_data,
    })

df = pd.DataFrame(sessions)
print(f"Total sessions: {len(df)}")
print(f"R1 baseline: {(~df['r1_fail']).sum()} wins / {df['r1_fail'].sum()} fails (target: 55/18)")
print()

def p_nearest(series, p):
    if len(series) == 0: return np.nan
    return np.percentile(series, p, method='nearest')

bull_all = df[df['side'] == 1]
bear_all = df[df['side'] == -1]
r1_wins = df[~df['r1_fail']]
bull_r1_wins = r1_wins[r1_wins['side'] == 1]
bear_r1_wins = r1_wins[r1_wins['side'] == -1]

# === TOUCH vs CLOSE stop-loss comparison ===
print("=" * 70)
print("TOUCH vs CLOSE stop-loss — P80 MAE from ALL sessions, BO px anchor")
print("=" * 70)
bull_p80 = p_nearest(bull_all['mae'], 80)
bear_p80 = p_nearest(bear_all['mae'], 80)
print(f"  Bull P80 MAE: {bull_p80:.3f}%, Bear P80 MAE: {bear_p80:.3f}%")

for stop_mode in ['touch', 'close']:
    results = []
    for i, row in df.iterrows():
        p80_mae = bull_p80 if row['side'] == 1 else bear_p80
        invalid_px = row['bo_px'] * (1 - row['side'] * p80_mae / 100)
        stop_hit = False
        for bar in row['bar_data']:
            if stop_mode == 'touch':
                if row['side'] == 1 and bar['low'] <= invalid_px:
                    stop_hit = True; break
                elif row['side'] == -1 and bar['high'] >= invalid_px:
                    stop_hit = True; break
            else:  # close
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
    print(f"  {stop_mode.upper()}-based stop: wins={w}, fails={f}  (Δ={w-55}/{f-18})  stop-only={len(stop_only)}")
    if len(stop_only) > 0 and stop_mode == 'close':
        print("    Stop-only fails:")
        for _, r in stop_only.iterrows():
            orig = df[df['date'] == r['date']].iloc[0]
            print(f"      {r['date']} side={orig['side']} mae={orig['mae']:.3f}%")
print()

# === Sweep: CLOSE-based stop, different percentiles, different MAE sources ===
print("=" * 70)
print("CLOSE-based stop-loss sweep — P{X} MAE from ALL sessions, BO px anchor")
print("=" * 70)
for pct in [75, 80, 85, 90, 95]:
    bull_p = p_nearest(bull_all['mae'], pct)
    bear_p = p_nearest(bear_all['mae'], pct)
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

# === Sweep: CLOSE-based stop, P{X} MAE from R1 WINS only ===
print("=" * 70)
print("CLOSE-based stop-loss sweep — P{X} MAE from R1 WINS, BO px anchor")
print("=" * 70)
for pct in [75, 80, 85, 90, 95]:
    bull_p = p_nearest(bull_r1_wins['mae'], pct)
    bear_p = p_nearest(bear_r1_wins['mae'], pct)
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

# === Try: R2 (any 5m close beyond opp OR) as the ONLY fail rule, no stop ===
print("=" * 70)
print("R2 only (any 5m close beyond opp OR) — no stop-loss")
print("=" * 70)
r2_fails = 0
r2_fail_dates = []
for i, row in df.iterrows():
    r2_fail = False
    for bar in row['bar_data']:
        if row['side'] == 1 and bar['close'] < row['or_low']:
            r2_fail = True; break
        elif row['side'] == -1 and bar['close'] > row['or_high']:
            r2_fail = True; break
    if r2_fail:
        r2_fails += 1
        r2_fail_dates.append(row['date'])
w = len(df) - r2_fails
print(f"  R2 only: wins={w}, fails={r2_fails}  (Δ={w-55}/{r2_fails-18})")
print()

# === Try: R2 + CLOSE-based P80 MAE stop ===
print("=" * 70)
print("R2 + CLOSE-based P80 MAE (all sessions, BO px anchor)")
print("=" * 70)
bull_p80 = p_nearest(bull_all['mae'], 80)
bear_p80 = p_nearest(bear_all['mae'], 80)
results = []
for i, row in df.iterrows():
    r2_fail = False
    for bar in row['bar_data']:
        if row['side'] == 1 and bar['close'] < row['or_low']:
            r2_fail = True; break
        elif row['side'] == -1 and bar['close'] > row['or_high']:
            r2_fail = True; break
    p80_mae = bull_p80 if row['side'] == 1 else bear_p80
    invalid_px = row['bo_px'] * (1 - row['side'] * p80_mae / 100)
    stop_hit = False
    for bar in row['bar_data']:
        if row['side'] == 1 and bar['close'] <= invalid_px:
            stop_hit = True; break
        elif row['side'] == -1 and bar['close'] >= invalid_px:
            stop_hit = True; break
    failed = r2_fail or stop_hit
    won = not failed
    results.append(won)
w = sum(results)
f = len(results) - w
print(f"  wins={w}, fails={f}  (Δ={w-55}/{f-18})")
print()

# === Try: EV target hit = win, R1 + close-based stop = fail, else fail ===
print("=" * 70)
print("EV target hit = win; R1 + CLOSE P80 MAE (all) = fail; else fail")
print("=" * 70)
for pct in [80, 85, 90, 95]:
    bull_p = p_nearest(bull_all['mae'], pct)
    bear_p = p_nearest(bear_all['mae'], pct)
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
        failed = row['r1_fail'] or stop_hit or not row['ev_hit']
        won = not failed
        results.append(won)
    w = sum(results)
    f = len(results) - w
    print(f"  P{pct}: wins={w}, fails={f}  (Δ={w-55}/{f-18})")
print()

# === Try: Session MFE from OR > 0 = win, R1 + close stop = fail ===
print("=" * 70)
print("Session MFE > 0 = win; R1 + CLOSE P80 MAE (all) = fail")
print("=" * 70)
# Need session_mfe — recompute
for pct in [80, 85, 90]:
    bull_p = p_nearest(bull_all['mae'], pct)
    bear_p = p_nearest(bear_all['mae'], pct)
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
        # Win = MFE > 0 and not failed
        failed = row['r1_fail'] or stop_hit
        won = (row['mfe'] > 0) and not failed
        results.append(won)
    w = sum(results)
    f = len(results) - w
    print(f"  P{pct}: wins={w}, fails={f}  (Δ={w-55}/{f-18})")
print()

# === Detailed: Show the 3 sessions that need to be caught ===
print("=" * 70)
print("R1-win sessions sorted by MAE (lowest 15) — candidates for stop-loss")
print("=" * 70)
r1_wins_sorted = r1_wins.sort_values('mae')
cols = ['date', 'side', 'bo_px', 'mae', 'mfe', 'close_at_cutoff', 'or_high', 'or_low']
print(r1_wins_sorted[cols].head(15).to_string())
print()

# === Try: Fixed MAE threshold sweep (not percentile-based) ===
print("=" * 70)
print("R1 + CLOSE-based fixed MAE threshold sweep (BO px anchor)")
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
        failed = row['r1_fail'] or stop_hit
        won = not failed
        results.append(won)
    w = sum(results)
    f = len(results) - w
    print(f"  thresh={thresh:.2f}%: wins={w}, fails={f}  (Δ={w-55}/{f-18})")