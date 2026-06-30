"""
Cross-preset validation: Test the Gunship classification rule across ALL 4 presets.
Rule: R1 + TOUCH stop at P80 BO MAE (ALL sessions, split by side), applied to BO px.
Tooltip says "P80 MAE from breakout" — no wins/losses filter.

Presets and their Gunship targets (from §6.5-6.7):
  1100 BO:     55 FULL / 18 Failed (N=73)
  MO Break:    32 FULL / 42 Failed (N=74)
  1800 Break:  35 FULL / 40 Failed (N=75)
  Magic Hour:  54 FULL /  6 Failed (N=60)
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

def p_nearest(series, p):
    if len(series) == 0: return np.nan
    return np.percentile(series, p, method='nearest')

def p_linear(series, p):
    if len(series) == 0: return np.nan
    return np.percentile(series, p, method='linear')

PRESETS = {
    '1100 BO':     {'or_start': 1100, 'or_end': 1115, 'cutoff': 1230, 'target_wins': 55, 'target_fails': 18},
    'MO Break':    {'or_start': 930,  'or_end': 935,  'cutoff': 1600, 'target_wins': 32, 'target_fails': 42},
    '1800 Break':  {'or_start': 1800, 'or_end': 1805, 'cutoff': 2100, 'target_wins': 35, 'target_fails': 40},
    'Magic Hour':  {'or_start': 900,  'or_end': 930,  'cutoff': 1600, 'target_wins': 54, 'target_fails': 6},
}

def build_sessions(preset_name, or_start, or_end, cutoff):
    """Build sessions for a preset using 1m breakout detection, 5m post-bo tracking."""
    sessions = []
    for date, day_1m in df_1m.groupby('date'):
        rth_1m = day_1m[(day_1m['et_hhmm'] >= 900) & (day_1m['et_hhmm'] < 2200)]
        if rth_1m.empty: continue
        day_5m = df_5m[df_5m['date'] == date]
        rth_5m = day_5m[(day_5m['et_hhmm'] >= 900) & (day_5m['et_hhmm'] < 2200)]
        if rth_5m.empty: continue

        or_bars = rth_1m[(rth_1m['et_hhmm'] >= or_start) & (rth_1m['et_hhmm'] < or_end)]
        if or_bars.empty: continue
        or_high = or_bars['high'].max()
        or_low = or_bars['low'].min()

        data_1m = rth_1m[(rth_1m['et_hhmm'] >= or_end) & (rth_1m['et_hhmm'] < cutoff)]
        data_5m = rth_5m[(rth_5m['et_hhmm'] >= or_end) & (rth_5m['et_hhmm'] < cutoff)]
        if data_1m.empty or data_5m.empty: continue

        # 1m breakout detection
        bo_side = 0; bo_px = None; bo_idx = None
        for idx, row in data_1m.iterrows():
            if row['close'] > or_high:
                bo_side = 1; bo_px = row['close']; bo_idx = idx; break
            elif row['close'] < or_low:
                bo_side = -1; bo_px = row['close']; bo_idx = idx; break
        if bo_side == 0: continue

        # Find the 5m bar containing the 1m breakout
        bo_5m_idx = None
        for idx in data_5m.index:
            if idx >= bo_idx:
                bo_5m_idx = idx; break
        if bo_5m_idx is None: bo_5m_idx = data_5m.index[0]

        post_bo_5m = data_5m.loc[bo_5m_idx:]
        if bo_side == 1:
            mae_bo = ((bo_px - post_bo_5m['low'].min()) / bo_px) * 100
            mae_or = ((or_high - post_bo_5m['low'].min()) / or_high) * 100
        else:
            mae_bo = ((post_bo_5m['high'].max() - bo_px) / bo_px) * 100
            mae_or = ((post_bo_5m['high'].max() - or_low) / or_low) * 100

        close_at_cutoff = data_5m['close'].iloc[-1]
        r1_fail = (bo_side == 1 and close_at_cutoff < or_low) or \
                  (bo_side == -1 and close_at_cutoff > or_high)

        bar_data = []
        for idx, row in post_bo_5m.iterrows():
            bar_data.append({'high': row['high'], 'low': row['low'], 'close': row['close']})

        sessions.append({
            'date': date, 'side': bo_side, 'or_high': or_high, 'or_low': or_low,
            'bo_px': bo_px, 'mae_bo': mae_bo, 'mae_or': mae_or,
            'close_at_cutoff': close_at_cutoff, 'r1_fail': r1_fail,
            'bar_data': bar_data,
        })
    return pd.DataFrame(sessions)

def test_rule(df, pct, mae_col, sample_filter, anchor, stop_type, percentile_method='nearest'):
    """Test a classification rule and return (wins, fails)."""
    p_func = p_nearest if percentile_method == 'nearest' else p_linear
    
    bull_all = df[df['side'] == 1]
    bear_all = df[df['side'] == -1]
    
    if sample_filter == 'all':
        bull_sample = bull_all
        bear_sample = bear_all
    elif sample_filter == 'r1_wins':
        r1_wins = df[~df['r1_fail']]
        bull_sample = r1_wins[r1_wins['side'] == 1]
        bear_sample = r1_wins[r1_wins['side'] == -1]
    
    bull_p = p_func(bull_sample[mae_col], pct)
    bear_p = p_func(bear_sample[mae_col], pct)
    
    results = []
    for i, row in df.iterrows():
        p_mae = bull_p if row['side'] == 1 else bear_p
        if anchor == 'bo_px':
            invalid_px = row['bo_px'] * (1 - row['side'] * p_mae / 100)
        else:  # or_boundary
            ref = row['or_high'] if row['side'] == 1 else row['or_low']
            invalid_px = ref * (1 - row['side'] * p_mae / 100)
        
        stop_hit = False
        for bar in row['bar_data']:
            if stop_type == 'touch':
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
        results.append(not failed)
    
    w = sum(results)
    f = len(results) - w
    return w, f, bull_p, bear_p

# === Build sessions for all presets ===
print("=" * 80)
print("BUILDING SESSIONS FOR ALL PRESETS")
print("=" * 80)
all_sessions = {}
for name, cfg in PRESETS.items():
    df_preset = build_sessions(name, cfg['or_start'], cfg['or_end'], cfg['cutoff'])
    all_sessions[name] = df_preset
    r1_w = (~df_preset['r1_fail']).sum()
    r1_f = df_preset['r1_fail'].sum()
    print(f"  {name:15s}: {len(df_preset)} sessions, R1={r1_w}/{r1_f} (target: {cfg['target_wins']}/{cfg['target_fails']})")
print()

# === Test the tooltip-specified rule: P80 BO MAE, ALL sessions, TOUCH, BO px ===
print("=" * 80)
print("THEORY: P80 BO MAE (ALL sessions), TOUCH, applied to BO px — nearest-rank")
print("  (Tooltip says 'P80 MAE from breakout' — no wins/losses filter)")
print("=" * 80)
print(f"{'Preset':<15} {'N':>4} {'Bull P80':>10} {'Bear P80':>10} {'Wins':>6} {'Fails':>6} {'Target':>12} {'Match':>8}")
print("-" * 80)
for name, cfg in PRESETS.items():
    df_p = all_sessions[name]
    w, f, bull_p, bear_p = test_rule(df_p, 80, 'mae_bo', 'all', 'bo_px', 'touch', 'nearest')
    target = f"{cfg['target_wins']}/{cfg['target_fails']}"
    match = "YES" if w == cfg['target_wins'] and f == cfg['target_fails'] else f"Δ={w-cfg['target_wins']}/{f-cfg['target_fails']}"
    print(f"  {name:<13} {len(df_p):>4} {bull_p:>9.3f}% {bear_p:>9.3f}% {w:>6} {f:>6} {target:>12} {match:>8}")
print()

# === Sweep percentiles for P80 BO MAE, ALL, TOUCH, BO px ===
print("=" * 80)
print("SWEEP: P{X} BO MAE (ALL sessions), TOUCH, applied to BO px — nearest-rank")
print("=" * 80)
for pct in [75, 80, 85, 90, 92, 95, 97]:
    print(f"\n  P{pct}:")
    print(f"  {'Preset':<15} {'Wins':>6} {'Fails':>6} {'Target':>12} {'Match':>8}")
    print(f"  {'-'*55}")
    for name, cfg in PRESETS.items():
        df_p = all_sessions[name]
        w, f, _, _ = test_rule(df_p, pct, 'mae_bo', 'all', 'bo_px', 'touch', 'nearest')
        target = f"{cfg['target_wins']}/{cfg['target_fails']}"
        match = "YES" if w == cfg['target_wins'] and f == cfg['target_fails'] else f"Δ={w-cfg['target_wins']}/{f-cfg['target_fails']}"
        print(f"    {name:<13} {w:>6} {f:>6} {target:>12} {match:>8}")

# === Also test Session MAE from OR for comparison ===
print("\n" + "=" * 80)
print("SWEEP: P{X} Session MAE from OR (ALL sessions), TOUCH, applied to OR boundary — nearest-rank")
print("=" * 80)
for pct in [75, 80, 85, 90, 92, 95, 97]:
    print(f"\n  P{pct}:")
    print(f"  {'Preset':<15} {'Wins':>6} {'Fails':>6} {'Target':>12} {'Match':>8}")
    print(f"  {'-'*55}")
    for name, cfg in PRESETS.items():
        df_p = all_sessions[name]
        w, f, _, _ = test_rule(df_p, pct, 'mae_or', 'all', 'or_boundary', 'touch', 'nearest')
        target = f"{cfg['target_wins']}/{cfg['target_fails']}"
        match = "YES" if w == cfg['target_wins'] and f == cfg['target_fails'] else f"Δ={w-cfg['target_wins']}/{f-cfg['target_fails']}"
        print(f"    {name:<13} {w:>6} {f:>6} {target:>12} {match:>8}")

# === Test with CLOSE-based stop ===
print("\n" + "=" * 80)
print("SWEEP: P{X} BO MAE (ALL sessions), CLOSE, applied to BO px — nearest-rank")
print("=" * 80)
for pct in [75, 80, 85, 90, 92, 95, 97]:
    print(f"\n  P{pct}:")
    print(f"  {'Preset':<15} {'Wins':>6} {'Fails':>6} {'Target':>12} {'Match':>8}")
    print(f"  {'-'*55}")
    for name, cfg in PRESETS.items():
        df_p = all_sessions[name]
        w, f, _, _ = test_rule(df_p, pct, 'mae_bo', 'all', 'bo_px', 'close', 'nearest')
        target = f"{cfg['target_wins']}/{cfg['target_fails']}"
        match = "YES" if w == cfg['target_wins'] and f == cfg['target_fails'] else f"Δ={w-cfg['target_wins']}/{f-cfg['target_fails']}"
        print(f"    {name:<13} {w:>6} {f:>6} {target:>12} {match:>8}")

# === Test with R1 wins sample ===
print("\n" + "=" * 80)
print("SWEEP: P{X} BO MAE (R1 wins only), TOUCH, applied to BO px — nearest-rank")
print("=" * 80)
for pct in [75, 80, 85, 90, 92, 95, 97]:
    print(f"\n  P{pct}:")
    print(f"  {'Preset':<15} {'Wins':>6} {'Fails':>6} {'Target':>12} {'Match':>8}")
    print(f"  {'-'*55}")
    for name, cfg in PRESETS.items():
        df_p = all_sessions[name]
        w, f, _, _ = test_rule(df_p, pct, 'mae_bo', 'r1_wins', 'bo_px', 'touch', 'nearest')
        target = f"{cfg['target_wins']}/{cfg['target_fails']}"
        match = "YES" if w == cfg['target_wins'] and f == cfg['target_fails'] else f"Δ={w-cfg['target_wins']}/{f-cfg['target_fails']}"
        print(f"    {name:<13} {w:>6} {f:>6} {target:>12} {match:>8}")

# === Test Session MAE from OR, applied to BO px ===
print("\n" + "=" * 80)
print("SWEEP: P{X} Session MAE from OR (ALL), TOUCH, applied to BO px — nearest-rank")
print("=" * 80)
for pct in [75, 80, 85, 90, 92, 95, 97]:
    print(f"\n  P{pct}:")
    print(f"  {'Preset':<15} {'Wins':>6} {'Fails':>6} {'Target':>12} {'Match':>8}")
    print(f"  {'-'*55}")
    for name, cfg in PRESETS.items():
        df_p = all_sessions[name]
        w, f, _, _ = test_rule(df_p, pct, 'mae_or', 'all', 'bo_px', 'touch', 'nearest')
        target = f"{cfg['target_wins']}/{cfg['target_fails']}"
        match = "YES" if w == cfg['target_wins'] and f == cfg['target_fails'] else f"Δ={w-cfg['target_wins']}/{f-cfg['target_fails']}"
        print(f"    {name:<13} {w:>6} {f:>6} {target:>12} {match:>8}")