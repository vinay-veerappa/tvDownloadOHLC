"""
Level verification v2: Fix direction bugs, skip Red zone levels.
Focus on: PB Entry, BO Cashflow, BO Inval, Pivot, BO Confirm, Reversal Zone, Max Reversal.

Bugs fixed:
1. Reversal Zone: was computing bo_px * (1 + side * mae%) [wrong direction]
   → Fixed to bo_px * (1 - side * mae%) [same direction as invalidation]
2. Max Reversal: same direction fix
3. Reversal Zone: also test OR boundary anchor (not just BO px)

Also test: the Gunship tooltip says "p25-p50 MAE of fakes" for Reversal Zone.
For bull, the reversal zone is BELOW the BO px (price went up, then reversed down).
So the MAE here is the ADVERSE excursion from the breakout, measured in the 
opposite direction of the breakout. This is the same as the BO MAE.
The price = bo_px * (1 - side * mae_pct / 100) — same formula as invalidation.
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
                    'target_n': 73, 'crosses_midnight': False, 'start_date': '2026-03-13'},
    'MO Break':    {'or_start': 930,  'or_end': 935,  'cutoff': 1200, 'days': '23456',
                    'target_n': 74, 'crosses_midnight': False, 'start_date': '2026-03-12'},
    '1800 Break':  {'or_start': 1800, 'or_end': 1815, 'cutoff': 300,  'days': '12345',
                    'target_n': 75, 'crosses_midnight': True, 'start_date': '2026-03-12'},
    'Q1 Break':    {'or_start': 600,  'or_end': 830,  'cutoff': 1200, 'days': '23456',
                    'target_n': 73, 'crosses_midnight': False, 'start_date': '2026-03-12'},
}

# Gunship captured levels
GUNSHIP = {
    '1100 BO': {
        'bo_px': 29773.50, 'side': 1,
        'PB Entry':       29742.25,
        'BO Cashflow':    29785.50,
        'BO Inval':       29711.25,
        'Pivot':          29835.50,
        'BO Confirm':     29888.50,
        'Reversal Zone':  29611.69,
        'Max Reversal':   29346.84,
    },
    'MO Break': {
        'bo_px': 29785.00, 'side': 1,
        'PB Entry':       29767.84,
        'BO Cashflow':    29882.68,
        'BO Inval':       29698.40,
        'Pivot':          29835.50,
        'BO Confirm':     29888.50,
        'Reversal Zone':  29611.69,
        'Max Reversal':   29346.84,
    },
    '1800 Break': {
        'bo_px': 29558.75, 'side': 1,
        'PB Entry':       29549.17,
        'BO Cashflow':    29637.80,
        'BO Inval':       29522.76,
        'Pivot':          29614.61,
        'BO Confirm':     29677.51,
        'Reversal Zone':  29442.70,
        'Max Reversal':   29231.37,
    },
    'Q1 Break': {
        'bo_px': 29643.25, 'side': -1,
        'PB Entry':       29690.67,
        'BO Cashflow':    29567.70,
        'BO Inval':       29796.00,
        'Pivot':          29559.16,
        'BO Confirm':     29530.73,
        'Reversal Zone':  29833.64,
        'Max Reversal':   30013.53,
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
        
        sessions.append({
            'date': date, 'side': bo_side, 'or_high': or_high, 'or_low': or_low,
            'bo_px': bo_px, 'mfe': mfe, 'mae_bo': mae_bo, 'mae_or': mae_or,
            'close_at_cutoff': close_at_cutoff,
            'r1_fail': r1_fail, 'r2_fail': r2_fail, 'r3_fail': r3_fail,
        })
    return pd.DataFrame(sessions)

# Build sessions
all_sessions = {}
for name, cfg in PRESETS.items():
    all_sessions[name] = build_sessions(cfg)
    print(f"  {name:15s}: N={len(all_sessions[name])} (target {cfg['target_n']})")
print()

# Verify each level
for preset_name, gunship in GUNSHIP.items():
    df_p = all_sessions[preset_name]
    bo_px = gunship['bo_px']
    side = gunship['side']
    
    bull = df_p[df_p['side'] == 1]
    bear = df_p[df_p['side'] == -1]
    same_side = df_p[df_p['side'] == side]
    
    # Classification: win = not R3 fail, fail = R3 fail, fake = R2 fail
    same_win = same_side[~same_side['r3_fail']]
    same_fail = same_side[same_side['r3_fail']]
    same_fake = same_side[same_side['r2_fail']]
    
    print("=" * 90)
    print(f"{preset_name} (BO px={bo_px}, side={'bull' if side==1 else 'bear'})")
    print(f"  Same-side: {len(same_side)} ({len(same_win)} wins, {len(same_fail)} fails, {len(same_fake)} fakes)")
    print("=" * 90)
    
    def fmt_price(pct, anchor_px, direction):
        """Compute price. direction=1 for MFE (same as breakout), direction=-1 for MAE (opposite)"""
        return anchor_px * (1 + side * direction * pct / 100)
    
    # === PB Entry (P25 MAE from breakout) ===
    # Tooltip: "PB entry — p25 MAE from breakout price"
    # MAE = adverse excursion = OPPOSITE direction from breakout
    # For bull: PB Entry = bo_px * (1 - p25_mae/100) → BELOW bo_px
    # For bear: PB Entry = bo_px * (1 + p25_mae/100) → ABOVE bo_px
    g = gunship['PB Entry']
    print(f"\n  PB Entry (Gunship: {g:.2f}, tooltip: p25 MAE from breakout):")
    for label, sample in [('ALL', same_side), ('Wins', same_win), ('Fails', same_fail)]:
        if len(sample) == 0: continue
        p = p_nearest(sample['mae_bo'], 25)
        price = bo_px * (1 - side * p / 100)  # MAE direction = opposite of breakout
        delta = price - g
        match = "✅" if abs(delta) < 2.0 else "❌"
        print(f"    P25 MAE ({label:>5}): {p:.3f}% → {price:.2f} (Δ={delta:+.2f}) {match}")
    
    # === BO Cashflow (P20 MFE from breakout) ===
    # Tooltip: "BO Cashflow — p20 MFE from breakout"
    # MFE = favorable excursion = SAME direction as breakout
    # For bull: Cashflow = bo_px * (1 + p20_mfe/100) → ABOVE bo_px
    # For bear: Cashflow = bo_px * (1 - p20_mfe/100) → BELOW bo_px
    g = gunship['BO Cashflow']
    print(f"\n  BO Cashflow (Gunship: {g:.2f}, tooltip: p20 MFE from breakout):")
    for label, sample in [('ALL', same_side), ('Wins', same_win), ('Fails', same_fail)]:
        if len(sample) == 0: continue
        p = p_nearest(sample['mfe'], 20)
        price = bo_px * (1 + side * p / 100)  # MFE direction = same as breakout
        delta = price - g
        match = "✅" if abs(delta) < 2.0 else "❌"
        print(f"    P20 MFE ({label:>5}): {p:.3f}% → {price:.2f} (Δ={delta:+.2f}) {match}")
    
    # === BO Inval (P80 MAE from breakout) ===
    # Tooltip: "p80 MAE from breakout"
    # Same direction as PB Entry (MAE = opposite of breakout)
    g = gunship['BO Inval']
    print(f"\n  BO Inval (Gunship: {g:.2f}, tooltip: p80 MAE from breakout):")
    for label, sample in [('ALL', same_side), ('Wins', same_win), ('Fails', same_fail)]:
        if len(sample) == 0: continue
        p = p_nearest(sample['mae_bo'], 80)
        price = bo_px * (1 - side * p / 100)
        delta = price - g
        match = "✅" if abs(delta) < 2.0 else "❌"
        print(f"    P80 MAE ({label:>5}): {p:.3f}% → {price:.2f} (Δ={delta:+.2f}) {match}")
    
    # === Pivot (P50 MFE of fakes) ===
    # Tooltip: "Pivot — p50 MFE of fakes"
    # MFE = favorable direction = SAME as breakout
    # Fakes = sessions that crossed opposite OR (R2 fail)
    g = gunship['Pivot']
    print(f"\n  Pivot (Gunship: {g:.2f}, tooltip: p50 MFE of fakes):")
    for label, sample in [('Fakes', same_fake), ('ALL', same_side), ('Wins', same_win)]:
        if len(sample) == 0: continue
        p = p_nearest(sample['mfe'], 50)
        price = bo_px * (1 + side * p / 100)
        delta = price - g
        match = "✅" if abs(delta) < 2.0 else "❌"
        print(f"    P50 MFE ({label:>5}): {p:.3f}% → {price:.2f} (Δ={delta:+.2f}) {match}")
    
    # === BO Confirm (P75 MFE of fakes) ===
    # Tooltip: "BO Confirm — p75 MFE of fakes"
    g = gunship['BO Confirm']
    print(f"\n  BO Confirm (Gunship: {g:.2f}, tooltip: p75 MFE of fakes):")
    for label, sample in [('Fakes', same_fake), ('ALL', same_side), ('Wins', same_win)]:
        if len(sample) == 0: continue
        p = p_nearest(sample['mfe'], 75)
        price = bo_px * (1 + side * p / 100)
        delta = price - g
        match = "✅" if abs(delta) < 2.0 else "❌"
        print(f"    P75 MFE ({label:>5}): {p:.3f}% → {price:.2f} (Δ={delta:+.2f}) {match}")
    
    # === Reversal Zone (p25-p50 MAE of fakes) ===
    # Tooltip: "Reversal Zone — p25-p50 MAE of fakes"
    # MAE = adverse direction = OPPOSITE of breakout (same as BO Inval)
    # For bull: Reversal Zone = bo_px * (1 - mae/100) → BELOW bo_px
    # For bear: Reversal Zone = bo_px * (1 + mae/100) → ABOVE bo_px
    g = gunship['Reversal Zone']
    print(f"\n  Reversal Zone (Gunship: {g:.2f}, tooltip: p25-p50 MAE of fakes):")
    # The Gunship shows a single price for the zone. Test P25 and P50.
    for pct in [25, 50, 75]:
        for label, sample in [('Fakes', same_fake), ('ALL', same_side), ('Fails', same_fail)]:
            if len(sample) == 0: continue
            p = p_nearest(sample['mae_bo'], pct)
            price = bo_px * (1 - side * p / 100)  # MAE direction = opposite of breakout
            delta = price - g
            match = "✅" if abs(delta) < 2.0 else "❌"
            print(f"    P{pct} MAE_BO ({label:>5}): {p:.3f}% → {price:.2f} (Δ={delta:+.2f}) {match}")
    
    # Also test with Session MAE from OR boundary
    print(f"    --- Session MAE from OR boundary ---")
    for pct in [25, 50, 75]:
        for label, sample in [('Fakes', same_fake), ('ALL', same_side)]:
            if len(sample) == 0: continue
            p = p_nearest(sample['mae_or'], pct)
            # Anchor at OR boundary (same side as breakout)
            ref = df_p[df_p['side'] == side]['or_high'].iloc[0] if side == 1 else df_p[df_p['side'] == side]['or_low'].iloc[0]
            # Actually we need the CURRENT session's OR, not the first session's
            # Skip OR boundary for now — we don't have today's OR in the historical data
            price = bo_px * (1 - side * p / 100)  # Using BO px as proxy
            delta = price - g
            match = "✅" if abs(delta) < 2.0 else "❌"
            print(f"    P{pct} MAE_OR ({label:>5}): {p:.3f}% → {price:.2f} (Δ={delta:+.2f}) {match} [BO px anchor]")
    
    # === Max Reversal (P90 MAE of fakes) ===
    # Tooltip: "Max Rev — p90 MAE of fakes"
    # Same direction as Reversal Zone (MAE = opposite of breakout)
    g = gunship['Max Reversal']
    print(f"\n  Max Reversal (Gunship: {g:.2f}, tooltip: p90 MAE of fakes):")
    for label, sample in [('Fakes', same_fake), ('ALL', same_side), ('Fails', same_fail)]:
        if len(sample) == 0: continue
        p = p_nearest(sample['mae_bo'], 90)
        price = bo_px * (1 - side * p / 100)  # MAE direction = opposite of breakout
        delta = price - g
        match = "✅" if abs(delta) < 2.0 else "❌"
        print(f"    P90 MAE ({label:>5}): {p:.3f}% → {price:.2f} (Δ={delta:+.2f}) {match}")
    
    print()