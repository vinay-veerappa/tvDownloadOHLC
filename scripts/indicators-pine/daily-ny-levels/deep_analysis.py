"""
Deep analysis of session classification discrepancies vs Gunship.
Goal: Find the exact rule that produces 55 FULL / 18 Failed (Gunship baseline).
"""
import pandas as pd
import numpy as np
import pytz

# Load NQ 1-min data
df_1m = pd.read_parquet('data/live/live_storage_-NQ.parquet')
df_1m['datetime'] = pd.to_datetime(df_1m['timestamp'], utc=True)
df_1m = df_1m.set_index('datetime')
df_1m = df_1m[['open', 'high', 'low', 'close', 'volume']].copy()

USE_1M_TIMEFRAME = True

if not USE_1M_TIMEFRAME:
    df_5m = df_1m.resample('5min', label='left', closed='left').agg(
        {'open':'first', 'high':'max', 'low':'min', 'close':'last', 'volume':'sum'}).dropna()
    df_1m = df_5m.copy()

# Filter to historical data (exclude today)
df_1m = df_1m[(df_1m.index >= '2026-03-16') & (df_1m.index < '2026-06-29')]
df_1m = df_1m[~df_1m.index.strftime('%Y-%m-%d').isin(['2026-05-25', '2026-06-19'])]

et = pytz.timezone('America/New_York')
df_1m['et_time'] = df_1m.index.tz_convert(et)
df_1m['et_hour'] = df_1m['et_time'].dt.hour
df_1m['et_minute'] = df_1m['et_time'].dt.minute
df_1m['et_hhmm'] = df_1m['et_hour'] * 100 + df_1m['et_minute']
df_1m['date'] = df_1m['et_time'].dt.date

if USE_1M_TIMEFRAME:
    df_5m = df_1m.resample('5min', label='left', closed='left').agg(
        {'open':'first', 'high':'max', 'low':'min', 'close':'last', 'volume':'sum'}).dropna()
    df_5m['et_time'] = df_5m.index.tz_convert(et)
    df_5m['et_hour'] = df_5m['et_time'].dt.hour
    df_5m['et_minute'] = df_5m['et_time'].dt.minute
    df_5m['et_hhmm'] = df_5m['et_hour'] * 100 + df_5m['et_minute']
else:
    df_5m = df_1m.copy()
df_5m['date'] = df_5m['et_time'].dt.date

OR_START = 1100
OR_END = 1115
CUTOFF = 1230
EV_TARGET_PCT = 0.30

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

    # Breakout detection on 1m
    bo_side = 0
    bo_px = None
    bo_idx = None
    for idx, row in data_1m.iterrows():
        if row['close'] > or_high:
            bo_side = 1; bo_px = row['close']; bo_idx = idx; break
        elif row['close'] < or_low:
            bo_side = -1; bo_px = row['close']; bo_idx = idx; break

    # Also detect breakout on 5m close
    bo_side_5m = 0
    bo_px_5m = None
    bo_idx_5m = None
    for idx, row in data_5m.iterrows():
        if row['close'] > or_high:
            bo_side_5m = 1; bo_px_5m = row['close']; bo_idx_5m = idx; break
        elif row['close'] < or_low:
            bo_side_5m = -1; bo_px_5m = row['close']; bo_idx_5m = idx; break

    if bo_side == 0 and bo_side_5m == 0:
        continue

    # Use 5m breakout if available, else 1m
    use_side = bo_side_5m if bo_side_5m != 0 else bo_side
    use_px = bo_px_5m if bo_side_5m != 0 else bo_px
    use_idx = bo_idx_5m if bo_side_5m != 0 else bo_idx

    post_bo_1m = data_1m.loc[bo_idx:] if bo_idx else data_1m
    post_bo_5m = data_5m.loc[use_idx:] if use_idx else data_5m

    if use_side == 1:
        mfe_1m = ((post_bo_1m['high'].max() - use_px) / use_px) * 100
        mae_1m = ((use_px - post_bo_1m['low'].min()) / use_px) * 100
        mfe_5m = ((post_bo_5m['high'].max() - use_px) / use_px) * 100
        mae_5m = ((use_px - post_bo_5m['low'].min()) / use_px) * 100
    else:
        mfe_1m = ((use_px - post_bo_1m['low'].min()) / use_px) * 100
        mae_1m = ((post_bo_1m['high'].max() - use_px) / use_px) * 100
        mfe_5m = ((use_px - post_bo_5m['low'].min()) / use_px) * 100
        mae_5m = ((post_bo_5m['high'].max() - use_px) / use_px) * 100

    session_high = data_5m['high'].max()
    session_low = data_5m['low'].min()
    close_at_cutoff = data_5m['close'].iloc[-1]

    # Session MFE from OR (all data bars)
    if use_side == 1:
        session_mfe = ((data_1m['high'].max() - or_high) / or_high) * 100
        session_mae = ((or_high - data_1m['low'].min()) / or_high) * 100
    else:
        session_mfe = ((or_low - data_1m['low'].min()) / or_low) * 100
        session_mae = ((data_1m['high'].max() - or_low) / or_low) * 100

    # Check if any 5m bar closed beyond opposite OR (R2 rule)
    crossed_opposite_close = False
    crossed_opposite_touch = False
    for idx, row in data_5m.iterrows():
        if use_side == 1:
            if row['close'] < or_low:
                crossed_opposite_close = True
            if row['low'] < or_low:
                crossed_opposite_touch = True
        else:
            if row['close'] > or_high:
                crossed_opposite_close = True
            if row['high'] > or_high:
                crossed_opposite_touch = True

    # Check if close at cutoff crossed opposite
    crossed_opposite_cutoff = (use_side == 1 and close_at_cutoff < or_low) or \
                              (use_side == -1 and close_at_cutoff > or_high)

    # Check if close at cutoff is on breakout side of OR
    close_on_bo_side_or = (use_side == 1 and close_at_cutoff > or_high) or \
                          (use_side == -1 and close_at_cutoff < or_low)

    # Check if close at cutoff is on breakout side of BO px
    close_on_bo_side_bopx = (use_side == 1 and close_at_cutoff > use_px) or \
                            (use_side == -1 and close_at_cutoff < use_px)

    # Track intrabar invalidation (P80 MAE hit)
    # We'll compute this later with the actual P80 value

    sessions.append({
        'date': date, 'side': use_side, 'or_high': or_high, 'or_low': or_low,
        'bo_px': use_px, 'bo_px_1m': bo_px, 'bo_px_5m': bo_px_5m,
        'mfe_1m': mfe_1m, 'mae_1m': mae_1m, 'mfe_5m': mfe_5m, 'mae_5m': mae_5m,
        'session_mfe': session_mfe, 'session_mae': session_mae,
        'session_high': session_high, 'session_low': session_low,
        'close_at_cutoff': close_at_cutoff,
        'crossed_opposite_close': crossed_opposite_close,
        'crossed_opposite_touch': crossed_opposite_touch,
        'crossed_opposite_cutoff': crossed_opposite_cutoff,
        'close_on_bo_side_or': close_on_bo_side_or,
        'close_on_bo_side_bopx': close_on_bo_side_bopx,
    })

df = pd.DataFrame(sessions)
print(f"Total sessions: {len(df)}")
print(f"  Bull: {(df['side']==1).sum()}, Bear: {(df['side']==-1).sum()}")
print()

# === Theory 1: MFE > 0 with different thresholds ===
print("=" * 70)
print("THEORY 1: MFE > threshold = FULL (testing different thresholds)")
print("=" * 70)
for thresh in [0, 0.001, 0.005, 0.01, 0.02, 0.05]:
    wins = (df['mfe_5m'] > thresh) & ~df['crossed_opposite_close']
    fails = ~wins
    w = wins.sum()
    f = fails.sum()
    print(f"  thresh={thresh:.3f}%: wins={w}, fails={f}  (target: 55/18)")
print()

# === Theory 2: Session MFE > threshold ===
print("=" * 70)
print("THEORY 2: Session MFE (from OR) > threshold = FULL")
print("=" * 70)
for thresh in [0, 0.001, 0.005, 0.01, 0.02, 0.05]:
    wins = (df['session_mfe'] > thresh) & ~df['crossed_opposite_close']
    fails = ~wins
    w = wins.sum()
    f = fails.sum()
    print(f"  thresh={thresh:.3f}%: wins={w}, fails={f}  (target: 55/18)")
print()

# === Theory 3: Different crossed_opposite rules ===
print("=" * 70)
print("THEORY 3: Different failure rules (MFE > 0 = win, various fail rules)")
print("=" * 70)
for fail_col, fail_name in [
    ('crossed_opposite_close', 'R2: any 5m close beyond opp OR'),
    ('crossed_opposite_touch', 'R3: any 5m touch beyond opp OR'),
    ('crossed_opposite_cutoff', 'R1: cutoff close beyond opp OR'),
]:
    wins = (df['mfe_5m'] > 0) & ~df[fail_col]
    fails = ~wins
    print(f"  {fail_name}: wins={wins.sum()}, fails={fails.sum()}  (target: 55/18)")
print()

# === Theory 4: Close at cutoff on BO side + various fail rules ===
print("=" * 70)
print("THEORY 4: Close at cutoff on BO side of BO px = FULL")
print("=" * 70)
for fail_col, fail_name in [
    ('crossed_opposite_close', 'R2: any 5m close beyond opp OR'),
    ('crossed_opposite_touch', 'R3: any 5m touch beyond opp OR'),
    ('crossed_opposite_cutoff', 'R1: cutoff close beyond opp OR'),
]:
    wins = df['close_on_bo_side_bopx'] & ~df[fail_col]
    fails = ~wins
    print(f"  {fail_name}: wins={wins.sum()}, fails={fails.sum()}  (target: 55/18)")
print()

# === Theory 5: Close at cutoff on BO side of OR = FULL ===
print("=" * 70)
print("THEORY 5: Close at cutoff on BO side of OR = FULL")
print("=" * 70)
for fail_col, fail_name in [
    ('crossed_opposite_close', 'R2: any 5m close beyond opp OR'),
    ('crossed_opposite_touch', 'R3: any 5m touch beyond opp OR'),
    ('crossed_opposite_cutoff', 'R1: cutoff close beyond opp OR'),
]:
    wins = df['close_on_bo_side_or'] & ~df[fail_col]
    fails = ~wins
    print(f"  {fail_name}: wins={wins.sum()}, fails={fails.sum()}  (target: 55/18)")
print()

# === Theory 6: MFE > 0 AND close on BO side = FULL ===
print("=" * 70)
print("THEORY 6: MFE > 0 AND close on BO side of OR = FULL")
print("=" * 70)
for fail_col, fail_name in [
    ('crossed_opposite_close', 'R2'),
    ('crossed_opposite_touch', 'R3'),
]:
    wins = (df['mfe_5m'] > 0) & df['close_on_bo_side_or'] & ~df[fail_col]
    fails = ~wins
    print(f"  {fail_name}: wins={wins.sum()}, fails={fails.sum()}  (target: 55/18)")
print()

# === Theory 7: Session MFE > 0 AND close on BO side = FULL ===
print("=" * 70)
print("THEORY 7: Session MFE > 0 AND close on BO side of OR = FULL")
print("=" * 70)
for fail_col, fail_name in [
    ('crossed_opposite_close', 'R2'),
    ('crossed_opposite_touch', 'R3'),
]:
    wins = (df['session_mfe'] > 0) & df['close_on_bo_side_or'] & ~df[fail_col]
    fails = ~wins
    print(f"  {fail_name}: wins={wins.sum()}, fails={fails.sum()}  (target: 55/18)")
print()

# === Theory 8: EV target hit = FULL, else Failed (no pending) ===
print("=" * 70)
print("THEORY 8: EV target (0.30%) hit = FULL, crossed opp = Failed, else Failed")
print("=" * 70)
for fail_col, fail_name in [
    ('crossed_opposite_close', 'R2'),
    ('crossed_opposite_touch', 'R3'),
]:
    target_hit = ((df['side']==1) & (df['session_high'] >= df['bo_px']*(1+EV_TARGET_PCT/100))) | \
                 ((df['side']==-1) & (df['session_low'] <= df['bo_px']*(1-EV_TARGET_PCT/100)))
    wins = target_hit & ~df[fail_col]
    fails = ~wins
    print(f"  {fail_name}: wins={wins.sum()}, fails={fails.sum()}  (target: 55/18)")
print()

# === Detailed session dump for the boundary cases ===
print("=" * 70)
print("BOUNDARY CASES: Sessions with MFE near 0 (potential classification flips)")
print("=" * 70)
near_zero = df[(df['mfe_5m'] >= -0.01) & (df['mfe_5m'] <= 0.05)][['date', 'side', 'bo_px', 'mfe_5m', 'mae_5m', 'session_mfe', 'close_at_cutoff', 'crossed_opposite_close', 'close_on_bo_side_or', 'close_on_bo_side_bopx']]
print(near_zero.to_string())
print()

# === Sessions where 1m and 5m breakout differ ===
print("=" * 70)
print("SESSIONS WHERE 1m vs 5m BREAKOUT DIFFER")
print("=" * 70)
diff = df[(df['bo_px_1m'].notna()) & (df['bo_px_5m'].notna()) & (df['bo_px_1m'] != df['bo_px_5m'])]
if len(diff) > 0:
    print(diff[['date', 'side', 'bo_px_1m', 'bo_px_5m', 'mfe_5m', 'close_at_cutoff']].to_string())
else:
    print("  No differences found")
print()

# === Sessions where crossed_opposite rules disagree ===
print("=" * 70)
print("SESSIONS WHERE R1/R2/R3 FAILURE RULES DISAGREE")
print("=" * 70)
disagree = df[(df['crossed_opposite_close'] != df['crossed_opposite_touch']) | 
              (df['crossed_opposite_close'] != df['crossed_opposite_cutoff'])]
print(disagree[['date', 'side', 'close_at_cutoff', 'or_high', 'or_low', 
                'crossed_opposite_close', 'crossed_opposite_touch', 'crossed_opposite_cutoff']].to_string())
print()

# === Full session dump sorted by MFE ===
print("=" * 70)
print("ALL SESSIONS SORTED BY MFE (5m) - lowest 20")
print("=" * 70)
sorted_df = df.sort_values('mfe_5m')
cols = ['date', 'side', 'or_high', 'or_low', 'bo_px', 'mfe_5m', 'mae_5m', 
        'session_mfe', 'close_at_cutoff', 'crossed_opposite_close', 'close_on_bo_side_or']
print(sorted_df[cols].head(20).to_string())