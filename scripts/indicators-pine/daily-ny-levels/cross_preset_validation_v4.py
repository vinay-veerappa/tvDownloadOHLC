"""
Cross-preset validation v4: Test EV-target-based classification.
Win = EV target (0.30%) hit by cutoff. Fail = EV target not hit.
Also test: Win = MFE > 0 AND not R2 fail. Fail = R2 OR MFE <= 0.
And: Win = MFE > EV target. Fail = MFE <= EV target (no R2/R3).
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

PRESETS = {
    '1100 BO':     {'or_start': 1100, 'or_end': 1115, 'cutoff': 1230, 'days': '23456',
                    'target_wins': 55, 'target_fails': 18, 'target_n': 73, 'crosses_midnight': False},
    'MO Break':    {'or_start': 930,  'or_end': 935,  'cutoff': 1200, 'days': '23456',
                    'target_wins': 32, 'target_fails': 42, 'target_n': 74, 'crosses_midnight': False},
    '1800 Break':  {'or_start': 1800, 'or_end': 1815, 'cutoff': 300,  'days': '12345',
                    'target_wins': 35, 'target_fails': 40, 'target_n': 75, 'crosses_midnight': True},
    'Magic Hour':  {'or_start': 300,  'or_end': 700,  'cutoff': 830,  'days': '23456',
                    'target_wins': 54, 'target_fails': 6,  'target_n': 60, 'crosses_midnight': False},
}

def days_to_python_dow(days_str):
    pine_to_python = {1: 6, 2: 0, 3: 1, 4: 2, 5: 3, 6: 4, 7: 5}
    return set(pine_to_python[int(d)] for d in days_str)

def build_sessions(preset_name, or_start, or_end, cutoff, days_str, crosses_midnight):
    valid_dows = days_to_python_dow(days_str)
    sessions = []
    for date, day_1m in df_1m.groupby('date'):
        if date.weekday() not in valid_dows:
            continue
        if crosses_midnight:
            next_date = date + pd.Timedelta(days=1)
            session_1m = pd.concat([
                df_1m[(df_1m['date'] == date) & (df_1m['et_hhmm'] >= or_start)],
                df_1m[(df_1m['date'] == next_date) & (df_1m['et_hhmm'] < cutoff)]
            ])
            session_5m = pd.concat([
                df_5m[(df_5m['date'] == date) & (df_5m['et_hhmm'] >= or_start)],
                df_5m[(df_5m['date'] == next_date) & (df_5m['et_hhmm'] < cutoff)]
            ])
        else:
            session_1m = df_1m[(df_1m['date'] == date) & (df_1m['et_hhmm'] >= or_start) & (df_1m['et_hhmm'] < cutoff)]
            session_5m = df_5m[(df_5m['date'] == date) & (df_5m['et_hhmm'] >= or_start) & (df_5m['et_hhmm'] < cutoff)]
        if session_1m.empty or session_5m.empty: continue
        or_bars = session_1m[(session_1m['et_hhmm'] >= or_start) & (session_1m['et_hhmm'] < or_end)]
        if or_bars.empty: continue
        or_high = or_bars['high'].max()
        or_low = or_bars['low'].min()
        data_1m = session_1m[session_1m['et_hhmm'] >= or_end]
        data_5m = session_5m[session_5m['et_hhmm'] >= or_end]
        if data_1m.empty or data_5m.empty: continue

        bo_side = 0; bo_px = None; bo_idx = None
        for idx, row in data_1m.iterrows():
            if row['close'] > or_high:
                bo_side = 1; bo_px = row['close']; bo_idx = idx; break
            elif row['close'] < or_low:
                bo_side = -1; bo_px = row['close']; bo_idx = idx; break
        if bo_side == 0: continue

        bo_5m_idx = None
        for idx in data_5m.index:
            if idx >= bo_idx: bo_5m_idx = idx; break
        if bo_5m_idx is None: bo_5m_idx = data_5m.index[0]
        post_bo_5m = data_5m.loc[bo_5m_idx:]

        if bo_side == 1:
            mfe = ((post_bo_5m['high'].max() - bo_px) / bo_px) * 100
            mae_bo = ((bo_px - post_bo_5m['low'].min()) / bo_px) * 100
        else:
            mfe = ((bo_px - post_bo_5m['low'].min()) / bo_px) * 100
            mae_bo = ((post_bo_5m['high'].max() - bo_px) / bo_px) * 100

        close_at_cutoff = data_5m['close'].iloc[-1]
        r1_fail = (bo_side == 1 and close_at_cutoff < or_low) or \
                  (bo_side == -1 and close_at_cutoff > or_high)
        r2_fail = False
        for idx, row in post_bo_5m.iterrows():
            if bo_side == 1 and row['close'] < or_low:
                r2_fail = True; break
            elif bo_side == -1 and row['close'] > or_high:
                r2_fail = True; break
        r3_fail = False
        for idx, row in post_bo_5m.iterrows():
            if bo_side == 1 and row['low'] < or_low:
                r3_fail = True; break
            elif bo_side == -1 and row['high'] > or_high:
                r3_fail = True; break

        # EV target hit
        target_px = bo_px * (1 + bo_side * 0.30 / 100)
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
            'bo_px': bo_px, 'mfe': mfe, 'mae_bo': mae_bo,
            'close_at_cutoff': close_at_cutoff, 'r1_fail': r1_fail,
            'r2_fail': r2_fail, 'r3_fail': r3_fail, 'ev_hit': ev_hit,
            'bar_data': bar_data,
        })
    return pd.DataFrame(sessions)

# Build sessions
all_sessions = {}
for name, cfg in PRESETS.items():
    df_p = build_sessions(name, cfg['or_start'], cfg['or_end'], cfg['cutoff'], cfg['days'], cfg['crosses_midnight'])
    all_sessions[name] = df_p
    print(f"  {name:15s}: N={len(df_p)} (tgt {cfg['target_n']})")

# === Test: Win = EV target hit, Fail = EV target not hit ===
print("\n" + "=" * 80)
print("THEORY: Win = EV target (0.30%) hit, Fail = not hit (no R1/R2/R3)")
print("=" * 80)
print(f"  {'Preset':<15} {'N':>4} {'Wins':>6} {'Fails':>6} {'Target':>12} {'Match':>8}")
print("  " + "-" * 60)
for name, cfg in PRESETS.items():
    df_p = all_sessions[name]
    w = df_p['ev_hit'].sum()
    f = (~df_p['ev_hit']).sum()
    target = f"{cfg['target_wins']}/{cfg['target_fails']}"
    match = "YES" if w == cfg['target_wins'] and f == cfg['target_fails'] else f"Δ={w-cfg['target_wins']}/{f-cfg['target_fails']}"
    print(f"  {name:<13} {len(df_p):>4} {w:>6} {f:>6} {target:>12} {match:>8}")
print()

# === Test: Win = MFE > 0 AND not R2, Fail = R2 OR MFE <= 0 ===
print("=" * 80)
print("THEORY: Win = MFE > 0 AND not R2, Fail = R2 OR MFE <= 0")
print("=" * 80)
print(f"  {'Preset':<15} {'N':>4} {'Wins':>6} {'Fails':>6} {'Target':>12} {'Match':>8}")
print("  " + "-" * 60)
for name, cfg in PRESETS.items():
    df_p = all_sessions[name]
    wins = (df_p['mfe'] > 0) & (~df_p['r2_fail'])
    w = wins.sum()
    f = (~wins).sum()
    target = f"{cfg['target_wins']}/{cfg['target_fails']}"
    match = "YES" if w == cfg['target_wins'] and f == cfg['target_fails'] else f"Δ={w-cfg['target_wins']}/{f-cfg['target_fails']}"
    print(f"  {name:<13} {len(df_p):>4} {w:>6} {f:>6} {target:>12} {match:>8}")
print()

# === Test: Win = MFE > EV target, Fail = MFE <= EV target ===
print("=" * 80)
print("THEORY: Win = MFE > 0.30%, Fail = MFE <= 0.30% (no R1/R2/R3)")
print("=" * 80)
print(f"  {'Preset':<15} {'N':>4} {'Wins':>6} {'Fails':>6} {'Target':>12} {'Match':>8}")
print("  " + "-" * 60)
for name, cfg in PRESETS.items():
    df_p = all_sessions[name]
    w = (df_p['mfe'] > 0.30).sum()
    f = (df_p['mfe'] <= 0.30).sum()
    target = f"{cfg['target_wins']}/{cfg['target_fails']}"
    match = "YES" if w == cfg['target_wins'] and f == cfg['target_fails'] else f"Δ={w-cfg['target_wins']}/{f-cfg['target_fails']}"
    print(f"  {name:<13} {len(df_p):>4} {w:>6} {f:>6} {target:>12} {match:>8}")
print()

# === Test: Win = MFE > 0 AND not R2 AND not R3, Fail = R2 OR R3 OR MFE <= 0 ===
print("=" * 80)
print("THEORY: Win = MFE > 0 AND not R2 AND not R3, Fail = R2 OR R3 OR MFE <= 0")
print("=" * 80)
print(f"  {'Preset':<15} {'N':>4} {'Wins':>6} {'Fails':>6} {'Target':>12} {'Match':>8}")
print("  " + "-" * 60)
for name, cfg in PRESETS.items():
    df_p = all_sessions[name]
    wins = (df_p['mfe'] > 0) & (~df_p['r2_fail']) & (~df_p['r3_fail'])
    w = wins.sum()
    f = (~wins).sum()
    target = f"{cfg['target_wins']}/{cfg['target_fails']}"
    match = "YES" if w == cfg['target_wins'] and f == cfg['target_fails'] else f"Δ={w-cfg['target_wins']}/{f-cfg['target_fails']}"
    print(f"  {name:<13} {len(df_p):>4} {w:>6} {f:>6} {target:>12} {match:>8}")
print()

# === Test: Win = EV hit AND not R2, Fail = R2 OR not EV hit ===
print("=" * 80)
print("THEORY: Win = EV hit AND not R2, Fail = R2 OR not EV hit")
print("=" * 80)
print(f"  {'Preset':<15} {'N':>4} {'Wins':>6} {'Fails':>6} {'Target':>12} {'Match':>8}")
print("  " + "-" * 60)
for name, cfg in PRESETS.items():
    df_p = all_sessions[name]
    wins = df_p['ev_hit'] & (~df_p['r2_fail'])
    w = wins.sum()
    f = (~wins).sum()
    target = f"{cfg['target_wins']}/{cfg['target_fails']}"
    match = "YES" if w == cfg['target_wins'] and f == cfg['target_fails'] else f"Δ={w-cfg['target_wins']}/{f-cfg['target_fails']}"
    print(f"  {name:<13} {len(df_p):>4} {w:>6} {f:>6} {target:>12} {match:>8}")
print()

# === Test: Win = EV hit AND not R3, Fail = R3 OR not EV hit ===
print("=" * 80)
print("THEORY: Win = EV hit AND not R3, Fail = R3 OR not EV hit")
print("=" * 80)
print(f"  {'Preset':<15} {'N':>4} {'Wins':>6} {'Fails':>6} {'Target':>12} {'Match':>8}")
print("  " + "-" * 60)
for name, cfg in PRESETS.items():
    df_p = all_sessions[name]
    wins = df_p['ev_hit'] & (~df_p['r3_fail'])
    w = wins.sum()
    f = (~wins).sum()
    target = f"{cfg['target_wins']}/{cfg['target_fails']}"
    match = "YES" if w == cfg['target_wins'] and f == cfg['target_fails'] else f"Δ={w-cfg['target_wins']}/{f-cfg['target_fails']}"
    print(f"  {name:<13} {len(df_p):>4} {w:>6} {f:>6} {target:>12} {match:>8}")
print()

# === Sweep: Win = MFE > threshold AND not R2, Fail = R2 OR MFE <= threshold ===
print("=" * 80)
print("SWEEP: Win = MFE > thresh AND not R2, Fail = R2 OR MFE <= thresh")
print("=" * 80)
for thresh in [0, 0.01, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50]:
    print(f"\n  thresh={thresh:.2f}%:")
    print(f"  {'Preset':<15} {'Wins':>6} {'Fails':>6} {'Target':>12} {'Match':>8}")
    print(f"  {'-'*55}")
    for name, cfg in PRESETS.items():
        df_p = all_sessions[name]
        wins = (df_p['mfe'] > thresh) & (~df_p['r2_fail'])
        w = wins.sum()
        f = (~wins).sum()
        target = f"{cfg['target_wins']}/{cfg['target_fails']}"
        match = "✅" if w == cfg['target_wins'] and f == cfg['target_fails'] else "❌"
        print(f"    {name:<13} {w:>6} {f:>6} {target:>12} {match:>8}")

# === Sweep: Win = MFE > threshold AND not R3, Fail = R3 OR MFE <= threshold ===
print("\n" + "=" * 80)
print("SWEEP: Win = MFE > thresh AND not R3, Fail = R3 OR MFE <= thresh")
print("=" * 80)
for thresh in [0, 0.01, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50]:
    print(f"\n  thresh={thresh:.2f}%:")
    print(f"  {'Preset':<15} {'Wins':>6} {'Fails':>6} {'Target':>12} {'Match':>8}")
    print(f"  {'-'*55}")
    for name, cfg in PRESETS.items():
        df_p = all_sessions[name]
        wins = (df_p['mfe'] > thresh) & (~df_p['r3_fail'])
        w = wins.sum()
        f = (~wins).sum()
        target = f"{cfg['target_wins']}/{cfg['target_fails']}"
        match = "✅" if w == cfg['target_wins'] and f == cfg['target_fails'] else "❌"
        print(f"    {name:<13} {w:>6} {f:>6} {target:>12} {match:>8}")