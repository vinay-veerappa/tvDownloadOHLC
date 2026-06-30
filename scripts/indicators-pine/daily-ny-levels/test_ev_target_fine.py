"""
Fine-tune EV target matching: test close-based, wick-based, and OR-boundary anchors.
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

df_1m = df_1m[df_1m['date'] <= pd.Timestamp('2026-06-26').date()]
HOLIDAYS = {pd.Timestamp('2026-04-03').date(), pd.Timestamp('2026-05-25').date(), pd.Timestamp('2026-06-19').date()}
df_1m = df_1m[~df_1m['date'].isin(HOLIDAYS)]
df_1m = df_1m[df_1m['date'] >= pd.Timestamp('2026-03-12').date()]

df_5m = df_1m.resample('5min', label='left', closed='left').agg(
    {'open':'first', 'high':'max', 'low':'min', 'close':'last', 'volume':'sum'}).dropna()
df_5m['et_time'] = df_5m.index.tz_convert(et)
df_5m['et_hhmm'] = df_5m['et_time'].dt.hour * 100 + df_5m['et_time'].dt.minute
df_5m['et_dow'] = df_5m['et_time'].dt.dayofweek
df_5m['date'] = df_5m['et_time'].dt.date

def days_to_python_dow(days_str):
    pine_to_python = {1: 6, 2: 0, 3: 1, 4: 2, 5: 3, 6: 4, 7: 5}
    return set(pine_to_python[int(d)] for d in days_str)

PRESETS = {
    '1100 BO':     {'or_start': 1100, 'or_end': 1115, 'cutoff': 1230, 'days': '23456',
                    'crosses_midnight': False, 'start_date': '2026-03-13',
                    'target_full': 55, 'target_failed': 18},
    'MO Break':    {'or_start': 930,  'or_end': 935,  'cutoff': 1200, 'days': '23456',
                    'crosses_midnight': False, 'start_date': '2026-03-12',
                    'target_full': 32, 'target_failed': 42},
    '1800 Break':  {'or_start': 1800, 'or_end': 1815, 'cutoff': 300,  'days': '12345',
                    'crosses_midnight': True, 'start_date': '2026-03-12',
                    'target_full': 35, 'target_failed': 40},
    'Q1 Break':    {'or_start': 600,  'or_end': 830,  'cutoff': 1200, 'days': '23456',
                    'crosses_midnight': False, 'start_date': '2026-03-12',
                    'target_full': 44, 'target_failed': 29},
}

def build_sessions(cfg):
    valid_dows = days_to_python_dow(cfg['days'])
    start_date = pd.Timestamp(cfg['start_date']).date()
    sessions = []
    for date in sorted(df_1m['date'].unique()):
        if date < start_date: continue
        if date in HOLIDAYS: continue
        if date.weekday() not in valid_dows: continue
        if cfg['crosses_midnight']:
            next_date = date + pd.Timedelta(days=1)
            session_1m = pd.concat([
                df_1m[(df_1m['date'] == date) & (df_1m['et_hhmm'] >= cfg['or_start'])],
                df_1m[(df_1m['date'] == next_date) & (df_1m['et_hhmm'] < cfg['cutoff'])]])
            session_5m = pd.concat([
                df_5m[(df_5m['date'] == date) & (df_5m['et_hhmm'] >= cfg['or_start'])],
                df_5m[(df_5m['date'] == next_date) & (df_5m['et_hhmm'] < cfg['cutoff'])]])
        else:
            session_1m = df_1m[(df_1m['date'] == date) & (df_1m['et_hhmm'] >= cfg['or_start']) & (df_1m['et_hhmm'] < cfg['cutoff'])]
            session_5m = df_5m[(df_5m['date'] == date) & (df_5m['et_hhmm'] >= cfg['or_start']) & (df_5m['et_hhmm'] < cfg['cutoff'])]
        if session_1m.empty or session_5m.empty: continue
        or_bars = session_1m[(session_1m['et_hhmm'] >= cfg['or_start']) & (session_1m['et_hhmm'] < cfg['or_end'])]
        if or_bars.empty: continue
        or_high = or_bars['high'].max()
        or_low = or_bars['low'].min()
        data_1m = session_1m[session_1m['et_hhmm'] >= cfg['or_end']]
        data_5m = session_5m[session_5m['et_hhmm'] >= cfg['or_end']]
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
        
        bar_data = []
        for idx, row in post_bo_5m.iterrows():
            bar_data.append({'high': row['high'], 'low': row['low'], 'close': row['close']})
        
        sessions.append({
            'date': date, 'side': bo_side, 'or_high': or_high, 'or_low': or_low,
            'bo_px': bo_px, 'bar_data': bar_data,
        })
    return pd.DataFrame(sessions)

all_sessions = {}
for name, cfg in PRESETS.items():
    all_sessions[name] = build_sessions(cfg)

def count_ev_matches(df, cfg, ev_targets, mode='wick_bo_px'):
    """mode: wick_bo_px, close_bo_px, wick_or_boundary, close_or_boundary"""
    matches = []
    for ev in ev_targets:
        wins = 0
        for _, row in df.iterrows():
            if mode == 'wick_bo_px':
                base = row['bo_px']
                target_px = base * (1 + row['side'] * ev / 100)
                hit = any(
                    (row['side'] == 1 and bar['high'] >= target_px) or
                    (row['side'] == -1 and bar['low'] <= target_px)
                    for bar in row['bar_data']
                )
            elif mode == 'close_bo_px':
                base = row['bo_px']
                target_px = base * (1 + row['side'] * ev / 100)
                hit = any(
                    (row['side'] == 1 and bar['close'] >= target_px) or
                    (row['side'] == -1 and bar['close'] <= target_px)
                    for bar in row['bar_data']
                )
            elif mode == 'wick_or_boundary':
                base = row['or_high'] if row['side'] == 1 else row['or_low']
                target_px = base * (1 + row['side'] * ev / 100)
                hit = any(
                    (row['side'] == 1 and bar['high'] >= target_px) or
                    (row['side'] == -1 and bar['low'] <= target_px)
                    for bar in row['bar_data']
                )
            elif mode == 'close_or_boundary':
                base = row['or_high'] if row['side'] == 1 else row['or_low']
                target_px = base * (1 + row['side'] * ev / 100)
                hit = any(
                    (row['side'] == 1 and bar['close'] >= target_px) or
                    (row['side'] == -1 and bar['close'] <= target_px)
                    for bar in row['bar_data']
                )
            if hit:
                wins += 1
        fails = len(df) - wins
        if wins == cfg['target_full'] and fails == cfg['target_failed']:
            matches.append((ev, wins, fails))
    return matches

ev_targets = np.arange(0.01, 2.01, 0.01)
modes = ['wick_bo_px', 'close_bo_px', 'wick_or_boundary', 'close_or_boundary']

print("=" * 100)
print("EV TARGET FINE SEARCH (EV target only, no stop/fakeout)")
print("=" * 100)

for mode in modes:
    print(f"\n### Mode: {mode} ###")
    for name, cfg in PRESETS.items():
        df = all_sessions[name]
        matches = count_ev_matches(df, cfg, ev_targets, mode)
        if matches:
            print(f"  {name}: exact matches at EV = {[f'{m[0]:.2f}%' for m in matches]}")
        else:
            # Find closest
            best_diff = float('inf')
            best = None
            for ev in ev_targets:
                wins = 0
                for _, row in df.iterrows():
                    if mode == 'wick_bo_px':
                        target_px = row['bo_px'] * (1 + row['side'] * ev / 100)
                        hit = any((row['side'] == 1 and bar['high'] >= target_px) or (row['side'] == -1 and bar['low'] <= target_px) for bar in row['bar_data'])
                    elif mode == 'close_bo_px':
                        target_px = row['bo_px'] * (1 + row['side'] * ev / 100)
                        hit = any((row['side'] == 1 and bar['close'] >= target_px) or (row['side'] == -1 and bar['close'] <= target_px) for bar in row['bar_data'])
                    elif mode == 'wick_or_boundary':
                        base = row['or_high'] if row['side'] == 1 else row['or_low']
                        target_px = base * (1 + row['side'] * ev / 100)
                        hit = any((row['side'] == 1 and bar['high'] >= target_px) or (row['side'] == -1 and bar['low'] <= target_px) for bar in row['bar_data'])
                    elif mode == 'close_or_boundary':
                        base = row['or_high'] if row['side'] == 1 else row['or_low']
                        target_px = base * (1 + row['side'] * ev / 100)
                        hit = any((row['side'] == 1 and bar['close'] >= target_px) or (row['side'] == -1 and bar['close'] <= target_px) for bar in row['bar_data'])
                    if hit:
                        wins += 1
                fails = len(df) - wins
                diff = abs(wins - cfg['target_full']) + abs(fails - cfg['target_failed'])
                if diff < best_diff:
                    best_diff = diff
                    best = (ev, wins, fails)
            print(f"  {name}: closest EV={best[0]:.2f}% -> {best[1]}/{best[2]} vs {cfg['target_full']}/{cfg['target_failed']} (diff={best_diff})")
