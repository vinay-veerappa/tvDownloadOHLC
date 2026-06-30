"""
Cross-preset validation with CORRECT date range:
  Start: March 12-13, 2026 (determined by 5000-bar replay window)
  End: June 26, 2026 (last complete session before June 29)
  Exclude: Good Friday (Apr 3), Memorial Day (May 25), Juneteenth (Jun 19)

This should produce EXACT session counts matching the Gunship.
"""
import pandas as pd
import numpy as np
import pytz

df_1m = pd.read_parquet('data/live/live_storage_-NQ.parquet')
df_1m['datetime'] = pd.to_datetime(df_1m['timestamp'], utc=True)
df_1m = df_1m.set_index('datetime')
df_1m = df_1m[['open', 'high', 'low', 'close', 'volume']].copy()

et = pytz.timezone('America/New_York')
df_1m['et_time'] = df_1m.index.tz_convert(et)
df_1m['et_hhmm'] = df_1m['et_time'].dt.hour * 100 + df_1m['et_time'].dt.minute
df_1m['et_dow'] = df_1m['et_time'].dt.dayofweek
df_1m['date'] = df_1m['et_time'].dt.date

# Exclude June 29 and beyond
df_1m = df_1m[df_1m['date'] <= pd.Timestamp('2026-06-26').date()]

# Exclude all 3 holidays
HOLIDAYS = {pd.Timestamp('2026-04-03').date(),  # Good Friday
            pd.Timestamp('2026-05-25').date(),  # Memorial Day
            pd.Timestamp('2026-06-19').date()}  # Juneteenth

df_1m = df_1m[~df_1m['date'].isin(HOLIDAYS)]

# Filter to start from March 12, 2026 (determined by 5000-bar replay window)
# The 73rd-75th session from June 26 backwards falls on March 12-13
df_1m = df_1m[df_1m['date'] >= pd.Timestamp('2026-03-12').date()]

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
    'Q1 Break':    {'or_start': 600,  'or_end': 830,  'cutoff': 1200, 'days': '23456',
                    'target_wins': 44, 'target_fails': 29, 'target_n': 73, 'crosses_midnight': False},
}

def days_to_python_dow(days_str):
    pine_to_python = {1: 6, 2: 0, 3: 1, 4: 2, 5: 3, 6: 4, 7: 5}
    return set(pine_to_python[int(d)] for d in days_str)

def build_sessions(cfg):
    valid_dows = days_to_python_dow(cfg['days'])
    sessions = []
    for date in sorted(df_1m['date'].unique()):
        if date in HOLIDAYS:
            continue
        if date.weekday() not in valid_dows:
            continue
        if cfg['crosses_midnight']:
            next_date = date + pd.Timedelta(days=1)
            session_1m = pd.concat([
                df_1m[(df_1m['date'] == date) & (df_1m['et_hhmm'] >= cfg['or_start'])],
                df_1m[(df_1m['date'] == next_date) & (df_1m['et_hhmm'] < cfg['cutoff'])]
            ])
            session_5m = pd.concat([
                df_5m[(df_5m['date'] == date) & (df_5m['et_hhmm'] >= cfg['or_start'])],
                df_5m[(df_5m['date'] == next_date) & (df_5m['et_hhmm'] < cfg['cutoff'])]
            ])
        else:
            session_1m = df_1m[(df_1m['date'] == date) & (df_1m['et_hhmm'] >= cfg['or_start']) & (df_1m['et_hhmm'] < cfg['cutoff'])]
            session_5m = df_5m[(df_5m['date'] == date) & (df_5m['et_hhmm'] >= cfg['or_start']) & (df_5m['et_hhmm'] < cfg['cutoff'])]
        if session_1m.empty or session_5m.empty:
            continue
        or_bars = session_1m[(session_1m['et_hhmm'] >= cfg['or_start']) & (session_1m['et_hhmm'] < cfg['or_end'])]
        if or_bars.empty:
            continue
        or_high = or_bars['high'].max()
        or_low = or_bars['low'].min()
        data_1m = session_1m[session_1m['et_hhmm'] >= cfg['or_end']]
        data_5m = session_5m[session_5m['et_hhmm'] >= cfg['or_end']]
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
        
        bar_data = []
        for idx, row in post_bo_5m.iterrows():
            bar_data.append({'high': row['high'], 'low': row['low'], 'close': row['close']})
        
        sessions.append({
            'date': date, 'side': bo_side, 'or_high': or_high, 'or_low': or_low,
            'bo_px': bo_px, 'mfe': mfe, 'mae_bo': mae_bo, 'mae_or': mae_or,
            'close_at_cutoff': close_at_cutoff, 'r1_fail': r1_fail,
            'r2_fail': r2_fail, 'r3_fail': r3_fail, 'bar_data': bar_data,
        })
    return pd.DataFrame(sessions)

# Build sessions for all presets
print("=" * 80)
print("SESSION COUNTS (CORRECT DATE RANGE: Mar 12-13 → Jun 26, excl 3 holidays)")
print("=" * 80)
all_sessions = {}
for name, cfg in PRESETS.items():
    df_p = build_sessions(cfg)
    all_sessions[name] = df_p
    n = len(df_p)
    n_match = "✅" if n == cfg['target_n'] else f"❌ (target {cfg['target_n']})"
    r1_w = (~df_p['r1_fail']).sum()
    r1_f = df_p['r1_fail'].sum()
    r2_w = (~df_p['r2_fail']).sum()
    r2_f = df_p['r2_fail'].sum()
    r3_w = (~df_p['r3_fail']).sum()
    r3_f = df_p['r3_fail'].sum()
    print(f"  {name:15s}: N={n} {n_match}, R1={r1_w}/{r1_f}, R2={r2_w}/{r2_f}, R3={r3_w}/{r3_f} (tgt {cfg['target_wins']}/{cfg['target_fails']})")
print()

# === Test all rule combinations ===
configs = [
    ('R1 + P{X} BO MAE (ALL, TOUCH, BO px)', 'r1_fail', 'mae_bo', 'all', 'bo_px', 'touch'),
    ('R2 + P{X} BO MAE (ALL, TOUCH, BO px)', 'r2_fail', 'mae_bo', 'all', 'bo_px', 'touch'),
    ('R3 + P{X} BO MAE (ALL, TOUCH, BO px)', 'r3_fail', 'mae_bo', 'all', 'bo_px', 'touch'),
    ('R1 + P{X} Sess MAE OR (ALL, TOUCH, OR bdy)', 'r1_fail', 'mae_or', 'all', 'or_boundary', 'touch'),
    ('R2 + P{X} Sess MAE OR (ALL, TOUCH, OR bdy)', 'r2_fail', 'mae_or', 'all', 'or_boundary', 'touch'),
    ('R3 + P{X} Sess MAE OR (ALL, TOUCH, OR bdy)', 'r3_fail', 'mae_or', 'all', 'or_boundary', 'touch'),
    ('R1 + P{X} BO MAE (ALL, CLOSE, BO px)', 'r1_fail', 'mae_bo', 'all', 'bo_px', 'close'),
    ('R2 + P{X} BO MAE (ALL, CLOSE, BO px)', 'r2_fail', 'mae_bo', 'all', 'bo_px', 'close'),
    ('R3 + P{X} BO MAE (ALL, CLOSE, BO px)', 'r3_fail', 'mae_bo', 'all', 'bo_px', 'close'),
]

for config_name, fail_col, mae_col, sample, anchor, stop_type in configs:
    print("=" * 80)
    print(f"SWEEP: {config_name}")
    print("=" * 80)
    print(f"  {'Pct':>4} ", end="")
    for name in PRESETS:
        print(f"  {'  ' + name:>18}", end="")
    print()
    print(f"  {'':>4} ", end="")
    for name, cfg in PRESETS.items():
        target = f"{cfg['target_wins']}/{cfg['target_fails']}"
        print(f"  {'W/F (tgt ' + target + ')':>16}", end="")
    print()
    print("  " + "-" * 80)
    
    for pct in [75, 80, 85, 90, 92, 95, 97]:
        print(f"  P{pct:>2} ", end="")
        for name, cfg in PRESETS.items():
            df_p = all_sessions[name]
            bull_all = df_p[df_p['side'] == 1]
            bear_all = df_p[df_p['side'] == -1]
            bull_p = p_nearest(bull_all[mae_col], pct)
            bear_p = p_nearest(bear_all[mae_col], pct)
            results = []
            for i, row in df_p.iterrows():
                p_mae = bull_p if row['side'] == 1 else bear_p
                if anchor == 'bo_px':
                    invalid_px = row['bo_px'] * (1 - row['side'] * p_mae / 100)
                else:
                    ref = row['or_high'] if row['side'] == 1 else row['or_low']
                    invalid_px = ref * (1 - row['side'] * p_mae / 100)
                stop_hit = False
                for bar in row['bar_data']:
                    if stop_type == 'touch':
                        if row['side'] == 1 and bar['low'] <= invalid_px:
                            stop_hit = True; break
                        elif row['side'] == -1 and bar['high'] >= invalid_px:
                            stop_hit = True; break
                    else:
                        if row['side'] == 1 and bar['close'] <= invalid_px:
                            stop_hit = True; break
                        elif row['side'] == -1 and bar['close'] >= invalid_px:
                            stop_hit = True; break
                failed = row[fail_col] or stop_hit
                results.append(not failed)
            w = sum(results)
            f = len(results) - w
            match = "✅" if w == cfg['target_wins'] and f == cfg['target_fails'] else "❌"
            print(f"  {w:>3}/{f:<3} {match:>2}       ", end="")
        print()
    print()

# Also test MFE > 0 AND not R2/R3
print("=" * 80)
print("MFE > 0 AND not R2 = Win")
print("=" * 80)
print(f"  {'Preset':<15} {'Wins':>6} {'Fails':>6} {'Target':>12} {'Match':>8}")
print("  " + "-" * 55)
for name, cfg in PRESETS.items():
    df_p = all_sessions[name]
    wins = (df_p['mfe'] > 0) & (~df_p['r2_fail'])
    w = wins.sum()
    f = (~wins).sum()
    target = f"{cfg['target_wins']}/{cfg['target_fails']}"
    match = "✅" if w == cfg['target_wins'] and f == cfg['target_fails'] else "❌"
    print(f"  {name:<13} {w:>6} {f:>6} {target:>12} {match:>8}")

print("\n" + "=" * 80)
print("MFE > 0 AND not R3 = Win")
print("=" * 80)
print(f"  {'Preset':<15} {'Wins':>6} {'Fails':>6} {'Target':>12} {'Match':>8}")
print("  " + "-" * 55)
for name, cfg in PRESETS.items():
    df_p = all_sessions[name]
    wins = (df_p['mfe'] > 0) & (~df_p['r3_fail'])
    w = wins.sum()
    f = (~wins).sum()
    target = f"{cfg['target_wins']}/{cfg['target_fails']}"
    match = "✅" if w == cfg['target_wins'] and f == cfg['target_fails'] else "❌"
    print(f"  {name:<13} {w:>6} {f:>6} {target:>12} {match:>8}")