"""
Unified level verification: Test all 12 Gunship levels across all 4 presets.
For each level, test 3 sample populations (ALL, wins, fails) and 2 anchors (BO px, OR boundary).
Compare Python-computed prices against Gunship drawn prices.

Date range: Mar 12-13 → Jun 26, 2026 (excluding Good Friday, Memorial Day, Juneteenth)
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

# Correct date range
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
                    'target_n': 73, 'crosses_midnight': False, 'start_date': '2026-03-13'},
    'MO Break':    {'or_start': 930,  'or_end': 935,  'cutoff': 1200, 'days': '23456',
                    'target_n': 74, 'crosses_midnight': False, 'start_date': '2026-03-12'},
    '1800 Break':  {'or_start': 1800, 'or_end': 1815, 'cutoff': 300,  'days': '12345',
                    'target_n': 75, 'crosses_midnight': True, 'start_date': '2026-03-12'},
    'Q1 Break':    {'or_start': 600,  'or_end': 830,  'cutoff': 1200, 'days': '23456',
                    'target_n': 73, 'crosses_midnight': False, 'start_date': '2026-03-12'},
}

# Gunship captured levels per preset (from MCP label capture)
# Format: {level_name: (price, tooltip_formula, derived_pct_from_bo)}
GUNSHIP_LEVELS = {
    '1100 BO': {
        'bo_px': 29773.50, 'side': 1,  # bull
        'PB Entry':       (29742.25, 'p25 MAE', 0.105),
        'BO Cashflow':    (29785.50, 'p20 MFE', 0.155),
        'MED MFE':        (29839.00, 'p50 Red', 0.350),
        'MAX MFE':        (29852.30, 'p75 Red', None),  # from §6.5.2
        'BO Inval':       (29711.25, 'p80 MAE', 0.209),
        'Pivot':          (29835.50, 'p50 fake MFE', 0.170),
        'BO Confirm':     (29888.50, 'p75 fake MFE', 0.347),
        'Reversal Zone':  (29611.69, 'p25-p50 fake MAE', None),
        'Max Reversal':   (29346.84, 'p90 fake MAE', 1.471),
        'Midpoint':       (29662.50, 'midpoint', 9.400),
    },
    'MO Break': {
        'bo_px': 29785.00, 'side': 1,  # bull
        'PB Entry':       (29767.84, 'p25 MAE', 0.058),
        'BO Cashflow':    (29882.68, 'p20 MFE', 0.328),
        'MED MFE':        (29928.19, 'p50 Red', None),
        'MAX MFE':        (30052.30, 'p75 Red', None),
        'BO Inval':       (29698.40, 'p80 MAE', None),
        'Pivot':          (29835.50, 'p50 fake MFE', 0.170),
        'BO Confirm':     (29888.50, 'p75 fake MFE', 0.347),
        'Reversal Zone':  (29611.69, 'p25-p50 fake MAE', None),
        'Max Reversal':   (29346.84, 'p90 fake MAE', 1.471),
        'Midpoint':       (29662.50, 'midpoint', 9.400),
    },
    '1800 Break': {
        'bo_px': 29558.75, 'side': 1,  # bull
        'PB Entry':       (29549.17, 'p25 MAE', 0.032),
        'BO Cashflow':    (29637.80, 'p20 MFE', 0.267),
        'MED MFE':        (29626.85, 'p50 Red', None),
        'MAX MFE':        (29763.67, 'p75 Red', None),
        'BO Inval':       (29522.76, 'p80 MAE', None),
        'Pivot':          (29614.61, 'p50 fake MFE', 0.189),
        'BO Confirm':     (29677.51, 'p75 fake MFE', 0.402),
        'Reversal Zone':  (29442.70, 'p25-p50 fake MAE', None),
        'Max Reversal':   (29231.37, 'p90 fake MAE', 1.108),
        'Midpoint':       (29416.38, 'midpoint', 22.900),
    },
    'Q1 Break': {
        'bo_px': 29643.25, 'side': -1,  # bear
        'PB Entry':       (29690.67, 'p25 MAE', 0.160),
        'BO Cashflow':    (29567.70, 'p20 MFE', 0.255),
        'MED MFE':        (29495.59, 'p50 Red', 0.498),
        'MAX MFE':        (29469.52, 'p75 Red', 0.586),
        'BO Inval':       (29796.00, 'p80 MAE', 0.515),
        'Pivot':          (29559.16, 'p50 fake MFE', 0.284),
        'BO Confirm':     (29530.73, 'p75 fake MFE', 0.380),
        'Reversal Zone':  (29833.64, 'p25-p50 fake MAE', None),
        'Max Reversal':   (30013.53, 'p90 fake MAE', 1.249),
        'AVG_low':        (29509.59, 'avg', None),
        'AVG_high':       (29896.99, 'avg', None),
    },
}

def build_sessions(cfg):
    valid_dows = days_to_python_dow(cfg['days'])
    start_date = pd.Timestamp(cfg['start_date']).date()
    sessions = []
    for date in sorted(df_1m['date'].unique()):
        if date < start_date:
            continue
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
        r1_fail = (bo_side == 1 and close_at_cutoff < or_low) or (bo_side == -1 and close_at_cutoff > or_high)
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
        
        # Classify: use R3 + P80 BO MAE (ALL, TOUCH, BO px) as best current rule
        # For level computation, we need to know which sessions are "wins" and "fails"
        # and which are "fakeouts" (R2 fail) and "Red" (fails)
        
        sessions.append({
            'date': date, 'side': bo_side, 'or_high': or_high, 'or_low': or_low,
            'bo_px': bo_px, 'mfe': mfe, 'mae_bo': mae_bo, 'mae_or': mae_or,
            'close_at_cutoff': close_at_cutoff,
            'r1_fail': r1_fail, 'r2_fail': r2_fail, 'r3_fail': r3_fail,
        })
    return pd.DataFrame(sessions)

# Build sessions for all presets
print("=" * 80)
print("BUILDING SESSIONS")
print("=" * 80)
all_sessions = {}
for name, cfg in PRESETS.items():
    df_p = build_sessions(cfg)
    all_sessions[name] = df_p
    print(f"  {name:15s}: N={len(df_p)} (target {cfg['target_n']})")
print()

# For each preset, compute levels and compare to Gunship
for preset_name, cfg in PRESETS.items():
    df_p = all_sessions[preset_name]
    gunship = GUNSHIP_LEVELS.get(preset_name, {})
    if not gunship:
        continue
    
    bo_px = gunship['bo_px']
    side = gunship['side']
    
    print("=" * 80)
    print(f"LEVEL VERIFICATION: {preset_name} (BO px={bo_px}, side={'bull' if side==1 else 'bear'})")
    print("=" * 80)
    
    bull = df_p[df_p['side'] == 1]
    bear = df_p[df_p['side'] == -1]
    same_side = df_p[df_p['side'] == side]
    opp_side = df_p[df_p['side'] == -side]
    
    # Classify sessions for "Red" (fails) and "fakes" (R2 fail)
    # Using R3 + P80 as current best classification rule
    bull_p80 = p_nearest(bull['mae_bo'], 80) if len(bull) > 0 else 0.5
    bear_p80 = p_nearest(bear['mae_bo'], 80) if len(bear) > 0 else 0.5
    
    # Simple classification: fail = R2 fail (fakeout) or R3 fail (touch opp OR)
    # "Red" = failed sessions = R3 fail
    red_sessions = df_p[df_p['r3_fail']]  # failed sessions
    win_sessions = df_p[~df_p['r3_fail']]  # winning sessions
    fake_sessions = df_p[df_p['r2_fail']]  # fakeout sessions (R2)
    
    same_side_red = same_side[same_side['r3_fail']]
    same_side_win = same_side[~same_side['r3_fail']]
    same_side_fake = same_side[same_side['r2_fail']]
    
    print(f"  Sessions: {len(df_p)} total, {len(bull)} bull, {len(bear)} bear")
    print(f"  Same side: {len(same_side)} ({len(same_side_win)} wins, {len(same_side_red)} red/fails, {len(same_side_fake)} fakes)")
    print()
    
    # For each level, compute Python values and compare
    def compute_level(pct, mae_col, sample_df, anchor, side):
        """Compute a level price from a percentile of a metric."""
        if len(sample_df) == 0:
            return np.nan, np.nan
        p_val = p_nearest(sample_df[mae_col], pct)
        if anchor == 'bo_px':
            price = bo_px * (1 - side * p_val / 100) if 'mae' in mae_col else bo_px * (1 + side * p_val / 100)
        else:  # or_boundary
            ref = gunship.get('or_high', 0) if side == 1 else gunship.get('or_low', 0)
            price = ref * (1 - side * p_val / 100) if 'mae' in mae_col else ref * (1 + side * p_val / 100)
        return p_val, price
    
    levels_to_test = [
        # (name, pct, metric_col, sample_label, sample_df, anchor)
        ('PB Entry (P25 MAE)', 25, 'mae_bo', 'ALL same-side', same_side, 'bo_px'),
        ('PB Entry (P25 MAE)', 25, 'mae_bo', 'Wins same-side', same_side_win, 'bo_px'),
        ('PB Entry (P25 MAE)', 25, 'mae_bo', 'Red same-side', same_side_red, 'bo_px'),
        ('BO Cashflow (P20 MFE)', 20, 'mfe', 'ALL same-side', same_side, 'bo_px'),
        ('BO Cashflow (P20 MFE)', 20, 'mfe', 'Wins same-side', same_side_win, 'bo_px'),
        ('BO Cashflow (P20 MFE)', 20, 'mfe', 'Red same-side', same_side_red, 'bo_px'),
        ('BO Inval (P80 MAE)', 80, 'mae_bo', 'ALL same-side', same_side, 'bo_px'),
        ('BO Inval (P80 MAE)', 80, 'mae_bo', 'Wins same-side', same_side_win, 'bo_px'),
        ('BO Inval (P80 MAE)', 80, 'mae_bo', 'Red same-side', same_side_red, 'bo_px'),
        ('MED MFE (P50 Red MFE)', 50, 'mfe', 'Red same-side', same_side_red, 'bo_px'),
        ('MED MFE (P50 ALL MFE)', 50, 'mfe', 'ALL same-side', same_side, 'bo_px'),
        ('MED MFE (P50 Wins MFE)', 50, 'mfe', 'Wins same-side', same_side_win, 'bo_px'),
        ('MAX MFE (P75 Red MFE)', 75, 'mfe', 'Red same-side', same_side_red, 'bo_px'),
        ('MAX MFE (P75 ALL MFE)', 75, 'mfe', 'ALL same-side', same_side, 'bo_px'),
        ('MAX MFE (P75 Wins MFE)', 75, 'mfe', 'Wins same-side', same_side_win, 'bo_px'),
        ('Pivot (P50 fake MFE)', 50, 'mfe', 'Fakes same-side', same_side_fake, 'bo_px'),
        ('BO Confirm (P75 fake MFE)', 75, 'mfe', 'Fakes same-side', same_side_fake, 'bo_px'),
        ('Max Rev (P90 fake MAE)', 90, 'mae_bo', 'Fakes same-side', same_side_fake, 'bo_px'),
        ('Max Rev (P90 fake MAE OR)', 90, 'mae_or', 'Fakes same-side', same_side_fake, 'or_boundary'),
    ]
    
    # Get Gunship prices for comparison
    gunship_prices = {}
    for key in ['PB Entry', 'BO Cashflow', 'BO Inval', 'MED MFE', 'MAX MFE', 'Pivot', 'BO Confirm', 'Max Reversal']:
        if key in gunship:
            gunship_prices[key] = gunship[key][0]
    
    print(f"  {'Level':<30} {'Sample':<20} {'Pct%':>6} {'Python Price':>14} {'Gunship Price':>14} {'Δ':>8} {'Match':>6}")
    print("  " + "-" * 100)
    
    for level_name, pct, metric, sample_label, sample_df, anchor in levels_to_test:
        if len(sample_df) == 0:
            continue
        p_val = p_nearest(sample_df[metric], pct)
        
        # Compute price
        if anchor == 'bo_px':
            if 'mae' in metric:
                price = bo_px * (1 - side * p_val / 100)
            else:
                price = bo_px * (1 + side * p_val / 100)
        else:
            # Need OR boundary — we don't have it in gunship dict, skip for now
            continue
        
        # Find matching Gunship price
        gunship_key = None
        if 'PB Entry' in level_name: gunship_key = 'PB Entry'
        elif 'Cashflow' in level_name: gunship_key = 'BO Cashflow'
        elif 'Inval' in level_name: gunship_key = 'BO Inval'
        elif 'MED' in level_name: gunship_key = 'MED MFE'
        elif 'MAX' in level_name: gunship_key = 'MAX MFE'
        elif 'Pivot' in level_name: gunship_key = 'Pivot'
        elif 'Confirm' in level_name: gunship_key = 'BO Confirm'
        elif 'Max Rev' in level_name: gunship_key = 'Max Reversal'
        
        g_price = gunship_prices.get(gunship_key)
        if g_price is not None:
            delta = price - g_price
            match = "✅" if abs(delta) < 2.0 else "❌"
            print(f"  {level_name:<30} {sample_label:<20} {p_val:>5.3f}% {price:>14.2f} {g_price:>14.2f} {delta:>+8.2f} {match:>6}")
        else:
            print(f"  {level_name:<30} {sample_label:<20} {p_val:>5.3f}% {price:>14.2f} {'---':>14} {'':>8} {'':>6}")
    
    # Also test Reversal Zone
    if 'Reversal Zone' in gunship:
        g_rev = gunship['Reversal Zone'][0]
        print(f"\n  Reversal Zone (Gunship: {g_rev:.2f}):")
        for pct in [25, 50, 75, 90]:
            for metric in ['mae_bo', 'mae_or']:
                for sample_label, sample_df in [('Fakes', same_side_fake), ('Red', same_side_red)]:
                    if len(sample_df) == 0:
                        continue
                    p_val = p_nearest(sample_df[metric], pct)
                    # For bear, reversal is ABOVE bo_px (opposite direction)
                    if metric == 'mae_bo':
                        price = bo_px * (1 + side * p_val / 100)  # opposite direction
                    else:
                        continue  # skip OR for now
                    delta = price - g_rev
                    match = "✅" if abs(delta) < 2.0 else "❌"
                    print(f"    P{pct} {metric} {sample_label}: {p_val:.3f}% → {price:.2f} (Δ={delta:+.2f}) {match}")
    
    print()