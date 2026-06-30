"""
Reversal Zone verification: The zone spans P25 (top) to P50 (bottom).
For bull: both boundaries are BELOW bo_px (MAE direction = opposite of breakout)
For bear: both boundaries are ABOVE bo_px

The Gunship label "REVERSAL TARGET ZONE" shows one price — we need to check
if it's the P25 (top) or P50 (bottom) boundary, or the midpoint.

Also re-run with R3 + P80 stop-loss classification to see if it improves matches.
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

def p_nearest(series, p):
    if len(series) == 0: return np.nan
    return np.percentile(series, p, method='nearest')

def days_to_python_dow(days_str):
    pine_to_python = {1: 6, 2: 0, 3: 1, 4: 2, 5: 3, 6: 4, 7: 5}
    return set(pine_to_python[int(d)] for d in days_str)

PRESETS = {
    '1100 BO':     {'or_start': 1100, 'or_end': 1115, 'cutoff': 1230, 'days': '23456',
                    'crosses_midnight': False, 'start_date': '2026-03-13'},
    'MO Break':    {'or_start': 930,  'or_end': 935,  'cutoff': 1200, 'days': '23456',
                    'crosses_midnight': False, 'start_date': '2026-03-12'},
    '1800 Break':  {'or_start': 1800, 'or_end': 1815, 'cutoff': 300,  'days': '12345',
                    'crosses_midnight': True, 'start_date': '2026-03-12'},
    'Q1 Break':    {'or_start': 600,  'or_end': 830,  'cutoff': 1200, 'days': '23456',
                    'crosses_midnight': False, 'start_date': '2026-03-12'},
}

# Gunship captured: Reversal Zone label price + Max Reversal price
# From the MCP captures, the "REVERSAL TARGET ZONE" label shows ONE price.
# We need to determine if this is P25 (top) or P50 (bottom).
# For bull: P25 > P50 (P25 is closer to bo_px, P50 is further below)
# For bear: P25 < P50 (P25 is closer to bo_px, P50 is further above)

GUNSHIP = {
    '1100 BO': {
        'bo_px': 29773.50, 'side': 1,
        'rev_zone_label': 29611.69,  # The price shown on the label
        'max_rev': 29346.84,
    },
    'MO Break': {
        'bo_px': 29785.00, 'side': 1,
        'rev_zone_label': 29611.69,
        'max_rev': 29346.84,
    },
    '1800 Break': {
        'bo_px': 29558.75, 'side': 1,
        'rev_zone_label': 29442.70,
        'max_rev': 29231.37,
    },
    'Q1 Break': {
        'bo_px': 29643.25, 'side': -1,
        'rev_zone_label': 29833.64,
        'max_rev': 30013.53,
    },
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
        
        if bo_side == 1:
            mfe = ((post_bo_5m['high'].max() - bo_px) / bo_px) * 100
            mae_bo = ((bo_px - post_bo_5m['low'].min()) / bo_px) * 100
        else:
            mfe = ((bo_px - post_bo_5m['low'].min()) / bo_px) * 100
            mae_bo = ((post_bo_5m['high'].max() - bo_px) / bo_px) * 100
        
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
        
        sessions.append({
            'date': date, 'side': bo_side, 'or_high': or_high, 'or_low': or_low,
            'bo_px': bo_px, 'mfe': mfe, 'mae_bo': mae_bo,
            'r2_fail': r2_fail, 'r3_fail': r3_fail,
        })
    return pd.DataFrame(sessions)

all_sessions = {}
for name, cfg in PRESETS.items():
    all_sessions[name] = build_sessions(cfg)

# For each preset, compute rolling P25 and P50 of fake MAE
# and check which one matches the Gunship's Reversal Zone label price
for preset_name, gunship in GUNSHIP.items():
    df_p = all_sessions[preset_name]
    side = gunship['side']
    bo_px = gunship['bo_px']
    rev_label = gunship['rev_zone_label']
    max_rev = gunship['max_rev']
    
    same_side = df_p[df_p['side'] == side].reset_index(drop=True)
    
    print("=" * 90)
    print(f"{preset_name} (side={'bull' if side==1 else 'bear'}, BO px={bo_px})")
    print(f"  Reversal Zone label: {rev_label:.2f}")
    print(f"  Max Reversal: {max_rev:.2f}")
    print(f"  Same-side sessions: {len(same_side)}")
    print("=" * 90)
    
    # Rolling history
    hist_mae_fakes = []
    hist_mae_all = []
    hist_mae_fails = []
    
    for i, row in same_side.iterrows():
        is_last = (i == len(same_side) - 1)
        
        if is_last:
            # Compute P25 and P50 from rolling fake MAE history
            print(f"\n  Rolling fake MAE history: {len(hist_mae_fakes)} sessions")
            print(f"  Rolling ALL MAE history: {len(hist_mae_all)} sessions")
            print(f"  Rolling fail MAE history: {len(hist_mae_fails)} sessions")
            
            # Reversal Zone: P25 (top) and P50 (bottom) of fake MAE
            # For bull: P25 price > P50 price (both below bo_px)
            # For bear: P25 price < P50 price (both above bo_px)
            # The label could be either boundary
            
            print(f"\n  Reversal Zone boundaries (MAE of fakes, BO px anchor):")
            for pct in [25, 50, 75, 90]:
                if len(hist_mae_fakes) > 0:
                    p = p_nearest(hist_mae_fakes, pct)
                else:
                    p = 0.30  # fallback
                price = bo_px * (1 - side * p / 100)
                delta = price - rev_label
                match = "✅" if abs(delta) < 2.0 else "❌"
                print(f"    P{pct} fake MAE: {p:.3f}% → {price:.2f} (Δ={delta:+.2f}) {match}")
            
            print(f"\n  Reversal Zone boundaries (MAE of ALL, BO px anchor):")
            for pct in [25, 50, 75, 90]:
                if len(hist_mae_all) > 0:
                    p = p_nearest(hist_mae_all, pct)
                else:
                    p = 0.30
                price = bo_px * (1 - side * p / 100)
                delta = price - rev_label
                match = "✅" if abs(delta) < 2.0 else "❌"
                print(f"    P{pct} ALL MAE: {p:.3f}% → {price:.2f} (Δ={delta:+.2f}) {match}")
            
            print(f"\n  Reversal Zone boundaries (MAE of fails, BO px anchor):")
            for pct in [25, 50, 75, 90]:
                if len(hist_mae_fails) > 0:
                    p = p_nearest(hist_mae_fails, pct)
                else:
                    p = 0.30
                price = bo_px * (1 - side * p / 100)
                delta = price - rev_label
                match = "✅" if abs(delta) < 2.0 else "❌"
                print(f"    P{pct} fail MAE: {p:.3f}% → {price:.2f} (Δ={delta:+.2f}) {match}")
            
            # Max Reversal: P90 MAE of fakes
            print(f"\n  Max Reversal (P90 MAE, BO px anchor):")
            for label, hist in [('Fakes', hist_mae_fakes), ('ALL', hist_mae_all), ('Fails', hist_mae_fails)]:
                if len(hist) > 0:
                    p90 = p_nearest(hist, 90)
                else:
                    p90 = 0.50
                price = bo_px * (1 - side * p90 / 100)
                delta = price - max_rev
                match = "✅" if abs(delta) < 2.0 else "❌"
                print(f"    P90 {label:>5} MAE: {p90:.3f}% → {price:.2f} (Δ={delta:+.2f}) {match}")
            
            # Also show the zone range (P25 top, P50 bottom)
            if len(hist_mae_fakes) > 0:
                p25 = p_nearest(hist_mae_fakes, 25)
                p50 = p_nearest(hist_mae_fakes, 50)
                price25 = bo_px * (1 - side * p25 / 100)
                price50 = bo_px * (1 - side * p50 / 100)
                print(f"\n  Zone range (fakes): P25={price25:.2f} to P50={price50:.2f}")
                print(f"  Gunship label: {rev_label:.2f}")
                if side == 1:
                    # Bull: P25 is top (closer to bo_px), P50 is bottom
                    print(f"  → Label is {'P25 (top)' if abs(rev_label - price25) < abs(rev_label - price50) else 'P50 (bottom)'}")
                else:
                    # Bear: P25 is bottom (closer to bo_px), P50 is top
                    print(f"  → Label is {'P25 (bottom)' if abs(rev_label - price25) < abs(rev_label - price50) else 'P50 (top)'}")
            
            # Also check with ALL sample
            if len(hist_mae_all) > 0:
                p25 = p_nearest(hist_mae_all, 25)
                p50 = p_nearest(hist_mae_all, 50)
                price25 = bo_px * (1 - side * p25 / 100)
                price50 = bo_px * (1 - side * p50 / 100)
                print(f"\n  Zone range (ALL): P25={price25:.2f} to P50={price50:.2f}")
                print(f"  Gunship label: {rev_label:.2f}")
        
        # Commit to history
        hist_mae_all.append(row['mae_bo'])
        if row['r3_fail']:
            hist_mae_fails.append(row['mae_bo'])
        if row['r2_fail']:
            hist_mae_fakes.append(row['mae_bo'])
    
    print()