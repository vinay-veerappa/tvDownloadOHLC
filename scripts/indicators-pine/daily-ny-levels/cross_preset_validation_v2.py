"""
Cross-preset validation v2: Correct OR windows and cutoffs from RangeSessionLib.pine.

Presets:
  1100 BO:     OR=1100-1115, cutoff=1230, days=23456 (Mon-Fri)
  MO Break:    OR=0930-0935, cutoff=1200, days=23456
  1800 Break:  OR=1800-1815, cutoff=0300 (NEXT DAY), days=12345 (Sun-Thu)
  Magic Hour:  OR=0300-0700, cutoff=0830, days=23456

Gunship targets:
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
df_1m['et_dow'] = df_1m['et_time'].dt.dayofweek  # 0=Monday, 6=Sunday
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

# Day codes: "12345" = Sun(0)-Thu(4), "23456" = Mon(1)-Fri(5)
# Python dayofweek: 0=Monday, 6=Sunday
# Pine day codes: 1=Sunday, 2=Monday, 3=Tuesday, 4=Wednesday, 5=Thursday, 6=Friday, 7=Saturday
# So "12345" = Pine days 1-5 = Sun,Mon,Tue,Wed,Thu = Python 6,0,1,2,3
# "23456" = Pine days 2-6 = Mon,Tue,Wed,Thu,Fri = Python 0,1,2,3,4

PRESETS = {
    '1100 BO':     {'or_start': 1100, 'or_end': 1115, 'cutoff': 1230, 'days': '23456',
                    'target_wins': 55, 'target_fails': 18, 'target_n': 73},
    'MO Break':    {'or_start': 930,  'or_end': 935,  'cutoff': 1200, 'days': '23456',
                    'target_wins': 32, 'target_fails': 42, 'target_n': 74},
    '1800 Break':  {'or_start': 1800, 'or_end': 1815, 'cutoff': 300,  'days': '12345',
                    'target_wins': 35, 'target_fails': 40, 'target_n': 75},
    'Magic Hour':  {'or_start': 300,  'or_end': 700,  'cutoff': 830,  'days': '23456',
                    'target_wins': 54, 'target_fails': 6,  'target_n': 60},
}

def days_to_python_dow(days_str):
    """Convert Pine day codes to Python dayofweek set."""
    # Pine: 1=Sun, 2=Mon, 3=Tue, 4=Wed, 5=Thu, 6=Fri, 7=Sat
    # Python: 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun
    pine_to_python = {1: 6, 2: 0, 3: 1, 4: 2, 5: 3, 6: 4, 7: 5}
    return set(pine_to_python[int(d)] for d in days_str)

def build_sessions(preset_name, or_start, or_end, cutoff, days_str):
    """Build sessions for a preset using 1m breakout detection, 5m post-bo tracking."""
    valid_dows = days_to_python_dow(days_str)
    sessions = []
    
    # For 1800 Break, the session spans midnight (1800 ET -> 0300 ET next day)
    # The OR day is the day where 1800 falls, and cutoff is next day 0300
    # We need to handle this by grouping by the "session start date"
    crosses_midnight = cutoff < or_start
    
    for date, day_1m in df_1m.groupby('date'):
        # Check if this date's day-of-week is valid for the preset
        # For 1800 Break, the session starts at 1800 ET, so the OR day is the session date
        # For other presets, the session is within the same day
        if not crosses_midnight:
            # Same-day session: check if this date's DOW is valid
            day_dow = date.weekday()
            if day_dow not in valid_dows:
                continue
        
        if crosses_midnight:
            # 1800 Break: OR starts at 1800 ET, cutoff at 0300 ET next day
            # The "session date" is the date of the 1800 bar
            # Filter 1m data: from 1800 ET on this date to 0300 ET on next date
            next_date = date + pd.Timedelta(days=1)
            session_1m = df_1m[(df_1m['date'] == date) & (df_1m['et_hhmm'] >= or_start)] if or_start >= 1000 else \
                         df_1m[(df_1m['date'] == date) & (df_1m['et_hhmm'] >= or_start)]
            # Add next day's data up to cutoff
            next_day_1m = df_1m[df_1m['date'] == next_date]
            session_1m = pd.concat([session_1m, next_day_1m[next_day_1m['et_hhmm'] < cutoff]])
            
            session_5m = df_5m[(df_5m['date'] == date) & (df_5m['et_hhmm'] >= or_start)]
            next_day_5m = df_5m[df_5m['date'] == next_date]
            session_5m = pd.concat([session_5m, next_day_5m[next_day_5m['et_hhmm'] < cutoff]])
        else:
            # Same-day session
            session_1m = day_1m[(day_1m['et_hhmm'] >= or_start) & (day_1m['et_hhmm'] < cutoff)]
            day_5m = df_5m[df_5m['date'] == date]
            session_5m = day_5m[(day_5m['et_hhmm'] >= or_start) & (day_5m['et_hhmm'] < cutoff)]
        
        if session_1m.empty or session_5m.empty:
            continue
        
        # OR building
        or_bars = session_1m[(session_1m['et_hhmm'] >= or_start) & (session_1m['et_hhmm'] < or_end)]
        if or_bars.empty:
            continue
        or_high = or_bars['high'].max()
        or_low = or_bars['low'].min()
        
        # Data window
        data_1m = session_1m[session_1m['et_hhmm'] >= or_end]
        data_5m = session_5m[session_5m['et_hhmm'] >= or_end]
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
        
        # Find the 5m bar containing the 1m breakout
        bo_5m_idx = None
        for idx in data_5m.index:
            if idx >= bo_idx:
                bo_5m_idx = idx; break
        if bo_5m_idx is None:
            bo_5m_idx = data_5m.index[0]
        
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

def test_rule(df, pct, mae_col, sample_filter, anchor, stop_type, pmethod='nearest'):
    p_func = p_nearest if pmethod == 'nearest' else lambda s, p: np.percentile(s, p, method='linear')
    bull_all = df[df['side'] == 1]
    bear_all = df[df['side'] == -1]
    if sample_filter == 'all':
        bull_sample, bear_sample = bull_all, bear_all
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
        failed = row['r1_fail'] or stop_hit
        results.append(not failed)
    return sum(results), len(results) - sum(results), bull_p, bear_p

# === Build sessions for all presets ===
print("=" * 80)
print("BUILDING SESSIONS FOR ALL PRESETS (CORRECT OR WINDOWS)")
print("=" * 80)
all_sessions = {}
for name, cfg in PRESETS.items():
    df_preset = build_sessions(name, cfg['or_start'], cfg['or_end'], cfg['cutoff'], cfg['days'])
    all_sessions[name] = df_preset
    r1_w = (~df_preset['r1_fail']).sum()
    r1_f = df_preset['r1_fail'].sum()
    n = len(df_preset)
    n_match = "✅" if n == cfg['target_n'] else f"❌ (target {cfg['target_n']})"
    print(f"  {name:15s}: N={n} {n_match}, R1={r1_w}/{r1_f} (target: {cfg['target_wins']}/{cfg['target_fails']})")
print()

# === Test the tooltip-specified rule: P80 BO MAE, ALL sessions, TOUCH, BO px ===
print("=" * 80)
print("RULE: P80 BO MAE (ALL sessions), TOUCH, applied to BO px — nearest-rank")
print("  (Tooltip: 'P80 MAE from breakout' — no wins/losses filter)")
print("=" * 80)
print(f"  {'Preset':<15} {'N':>4} {'Bull P80':>10} {'Bear P80':>10} {'Wins':>6} {'Fails':>6} {'Target':>12} {'Match':>8}")
print("  " + "-" * 75)
for name, cfg in PRESETS.items():
    df_p = all_sessions[name]
    w, f, bull_p, bear_p = test_rule(df_p, 80, 'mae_bo', 'all', 'bo_px', 'touch', 'nearest')
    target = f"{cfg['target_wins']}/{cfg['target_fails']}"
    match = "YES" if w == cfg['target_wins'] and f == cfg['target_fails'] else f"Δ={w-cfg['target_wins']}/{f-cfg['target_fails']}"
    print(f"  {name:<13} {len(df_p):>4} {bull_p:>9.3f}% {bear_p:>9.3f}% {w:>6} {f:>6} {target:>12} {match:>8}")
print()

# === Sweep all configurations ===
configs = [
    ('BO MAE, ALL, TOUCH, BO px', 'mae_bo', 'all', 'bo_px', 'touch'),
    ('BO MAE, ALL, CLOSE, BO px', 'mae_bo', 'all', 'bo_px', 'close'),
    ('BO MAE, R1wins, TOUCH, BO px', 'mae_bo', 'r1_wins', 'bo_px', 'touch'),
    ('Sess MAE OR, ALL, TOUCH, OR bdy', 'mae_or', 'all', 'or_boundary', 'touch'),
    ('Sess MAE OR, ALL, CLOSE, OR bdy', 'mae_or', 'all', 'or_boundary', 'close'),
    ('Sess MAE OR, ALL, TOUCH, BO px', 'mae_or', 'all', 'bo_px', 'touch'),
    ('BO MAE, ALL, TOUCH, OR bdy', 'mae_bo', 'all', 'or_boundary', 'touch'),
]

for config_name, mae_col, sample, anchor, stop_type in configs:
    print("=" * 80)
    print(f"SWEEP: {config_name} — nearest-rank")
    print("=" * 80)
    print(f"  {'Pct':>4} ", end="")
    for name in PRESETS:
        print(f"{'  ' + name:>18}", end="")
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
            w, f, _, _ = test_rule(df_p, pct, mae_col, sample, anchor, stop_type, 'nearest')
            match = "✅" if w == cfg['target_wins'] and f == cfg['target_fails'] else "❌"
            print(f"  {w:>3}/{f:<3} {match:>2}       ", end="")
        print()
    print()