"""
Verify DNL session classification against Gunship.
1100 BO preset: OR = 11:00-11:10 ET, Data = 11:10-12:30 ET
Tests different win/loss classification methods to match Gunship's 55 FULL / 18 Failed.
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz

# Load NQ 1-min data from live storage
df_1m = pd.read_parquet('data/live/live_storage_-NQ.parquet')
df_1m['datetime'] = pd.to_datetime(df_1m['timestamp'], utc=True)
df_1m = df_1m.set_index('datetime')
df_1m = df_1m[['open', 'high', 'low', 'close', 'volume']].copy()

# Timeframe configuration: Set to True to match the TradingView reference indicator values (which uses 1m data under the hood),
# or False to use strict 5-minute chart bar calculation.
USE_1M_TIMEFRAME = True

if not USE_1M_TIMEFRAME:
    # Resample to 5-minute bars to match TradingView chart timeframe
    df_5m = df_1m.resample('5min', label='left', closed='left').agg({'open':'first', 'high':'max', 'low':'min', 'close':'last', 'volume':'sum'}).dropna()
    df_1m = df_5m.copy()

# Filter to match DNL's actual data window from logs (excluding today's data for historical extrapolation)
df_1m = df_1m[(df_1m.index >= '2026-03-16') & (df_1m.index < '2026-06-29')]

# Exclude specific holidays to perfectly match TradingView's 73 sessions dataset
df_1m = df_1m[~df_1m.index.strftime('%Y-%m-%d').isin(['2026-05-25', '2026-06-19'])]
# Convert to ET for session filtering
et = pytz.timezone('America/New_York')
df_1m['et_time'] = df_1m.index.tz_convert(et)
df_1m['et_hour'] = df_1m['et_time'].dt.hour
df_1m['et_minute'] = df_1m['et_time'].dt.minute
df_1m['et_hhmm'] = df_1m['et_hour'] * 100 + df_1m['et_minute']
df_1m['date'] = df_1m['et_time'].dt.date

if USE_1M_TIMEFRAME:
    # Upsample to 5-min bars for chart-level close/breakout references
    df_5m = df_1m.resample('5min', label='left', closed='left').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }).dropna()
    df_5m['et_time'] = df_5m.index.tz_convert(et)
    df_5m['et_hour'] = df_5m['et_time'].dt.hour
    df_5m['et_minute'] = df_5m['et_time'].dt.minute
    df_5m['et_hhmm'] = df_5m['et_hour'] * 100 + df_5m['et_minute']
else:
    df_5m = df_1m.copy()

df_5m['date'] = df_5m['et_time'].dt.date

# 1100 BO preset parameters
OR_START = 1100   # 11:00 ET
OR_END = 1115     # 11:15 ET  
CUTOFF = 1230     # 12:30 ET
EV_TARGET_PCT = 0.30

print(f"Data range: {df_5m.index.min()} to {df_5m.index.max()}")
print(f"Total 5-min bars: {len(df_5m)}")
print(f"Trading days: {df_5m['date'].nunique()}")
print()

# Group by date and process each session
# Use 1-min data for OR building and breakout detection (matches DNL's LTF approach)
# Use 5-min data for chart-level bars (matches what DNL sees on the chart)
sessions = []
for date, day_1m in df_1m.groupby('date'):
    # Filter to RTH hours (9:30 - 16:00 ET)
    rth_1m = day_1m[(day_1m['et_hhmm'] >= 930) & (day_1m['et_hhmm'] < 1600)]
    if rth_1m.empty:
        continue
    
    # Get 5-min bars for this day
    day_5m = df_5m[df_5m['date'] == date]
    rth_5m = day_5m[(day_5m['et_hhmm'] >= 930) & (day_5m['et_hhmm'] < 1600)]
    if rth_5m.empty:
        continue
    
    # OR building: 11:00 - 11:10 ET (use 1-min data like DNL's LTF)
    or_bars = rth_1m[(rth_1m['et_hhmm'] >= OR_START) & (rth_1m['et_hhmm'] < OR_END)]
    if or_bars.empty:
        continue
    
    or_high = or_bars['high'].max()
    or_low = or_bars['low'].min()
    
    # Data window: 11:10 - 12:30 ET (use 1-min for breakout detection, 5-min for chart bars)
    data_1m = rth_1m[(rth_1m['et_hhmm'] >= OR_END) & (rth_1m['et_hhmm'] < CUTOFF)]
    data_5m = rth_5m[(rth_5m['et_hhmm'] >= OR_END) & (rth_5m['et_hhmm'] < CUTOFF)]
    if data_1m.empty or data_5m.empty:
        continue
    
    # Find breakout: first 1-min bar where close > OR High or close < OR Low (matches DNL LTF)
    bo_side = 0
    bo_px = None
    bo_idx = None
    for idx, row in data_1m.iterrows():
        if row['close'] > or_high:
            bo_side = 1
            bo_px = row['close']
            bo_idx = idx
            break
        elif row['close'] < or_low:
            bo_side = -1
            bo_px = row['close']
            bo_idx = idx
            break
    
    if bo_side == 0:
        # No breakout - skip (DNL doesn't count these as signal triggers)
        sessions.append({
            'date': date, 'side': 0, 'outcome': 'no_bo',
            'or_high': or_high, 'or_low': or_low, 'bo_px': None,
            'mfe': 0, 'mae': 0, 'session_high': data_5m['high'].max(),
            'session_low': data_5m['low'].min(), 'close_at_cutoff': data_5m['close'].iloc[-1]
        })
        continue
    
    # Get 1-min bars after breakout for MFE/MAE (matches DNL's f_process_price_update)
    post_bo_1m = data_1m.loc[bo_idx:]
    
    # Calculate MFE (max favorable excursion from BO px) using 1-min data
    if bo_side == 1:
        mfe = ((post_bo_1m['high'].max() - bo_px) / bo_px) * 100
        mae = ((bo_px - post_bo_1m['low'].min()) / bo_px) * 100
    else:
        mfe = ((bo_px - post_bo_1m['low'].min()) / bo_px) * 100
        mae = ((post_bo_1m['high'].max() - bo_px) / bo_px) * 100
    
    # Use 5-min bars for session-level stats (what the chart sees)
    session_high = data_5m['high'].max()
    session_low = data_5m['low'].min()
    close_at_cutoff = data_5m['close'].iloc[-1]
    
    # Also calculate OR-based MFE (from OR boundary, not BO px) using 1-min post-bo
    if bo_side == 1:
        or_mfe = ((post_bo_1m['high'].max() - or_high) / or_high) * 100
        or_mae = ((or_high - post_bo_1m['low'].min()) / or_high) * 100
    else:
        or_mfe = ((or_low - post_bo_1m['low'].min()) / or_low) * 100
        or_mae = ((post_bo_1m['high'].max() - or_low) / or_low) * 100
    
    # Session-wide MFE from OR boundary (all 1-min data bars, not just post-bo)
    if bo_side == 1:
        session_mfe = ((data_1m['high'].max() - or_high) / or_high) * 100
        session_mae = ((or_high - data_1m['low'].min()) / or_high) * 100
    else:
        session_mfe = ((or_low - data_1m['low'].min()) / or_low) * 100
        session_mae = ((data_1m['high'].max() - or_low) / or_low) * 100
    
    sessions.append({
        'date': date, 'side': bo_side, 'outcome': 'pending',
        'or_high': or_high, 'or_low': or_low, 'bo_px': bo_px,
        'mfe': mfe, 'mae': mae, 'or_mfe': or_mfe, 'or_mae': or_mae,
        'session_mfe': session_mfe, 'session_mae': session_mae,
        'session_high': session_high, 'session_low': session_low,
        'close_at_cutoff': close_at_cutoff,
        'crossed_opposite': (bo_side == 1 and close_at_cutoff < or_low) or 
                           (bo_side == -1 and close_at_cutoff > or_high)
    })

df_sessions = pd.DataFrame(sessions)
bo_sessions = df_sessions[df_sessions['side'] != 0].copy()

print(f"Total sessions: {len(df_sessions)}")
print(f"Breakout sessions: {len(bo_sessions)}")
print(f"  Bull (side=1): {(bo_sessions['side'] == 1).sum()}")
print(f"  Bear (side=-1): {(bo_sessions['side'] == -1).sum()}")
print()

# === Method 1: DNL Current (BO-based, EV target 0.30%) ===
print("=" * 70)
print("METHOD 1: DNL Current (BO px anchor, EV target 0.30%, P80 MAE invalidation)")
print("=" * 70)
m1 = bo_sessions.copy()
m1['win'] = False
m1['loss'] = False
m1['fakeout'] = False
m1['pending'] = True

for i, row in m1.iterrows():
    side = row['side']
    bo_px = row['bo_px']
    target_px = bo_px * (1 + side * EV_TARGET_PCT / 100)
    # Use default invalidation P80 MAE = 0.5% (cold start fallback)
    invalid_px = bo_px * (1 - side * 0.5 / 100)
    
    if row['crossed_opposite']:
        m1.at[i, 'fakeout'] = True
        m1.at[i, 'pending'] = False
    elif side == 1 and row['session_high'] >= target_px:
        m1.at[i, 'win'] = True
        m1.at[i, 'pending'] = False
    elif side == -1 and row['session_low'] <= target_px:
        m1.at[i, 'win'] = True
        m1.at[i, 'pending'] = False
    elif side == 1 and row['session_low'] <= invalid_px:
        m1.at[i, 'loss'] = True
        m1.at[i, 'pending'] = False
    elif side == -1 and row['session_high'] >= invalid_px:
        m1.at[i, 'loss'] = True
        m1.at[i, 'pending'] = False

m1_wins = m1['win'].sum()
m1_fails = m1['loss'].sum() + m1['fakeout'].sum()
m1_pend = m1['pending'].sum()
print(f"  Wins: {m1_wins}, Failed: {m1_fails}, Pending: {m1_pend}")
print(f"  Gunship: 55 FULL, 18 Failed, 0 Pending")
print(f"  Delta: wins={m1_wins - 55}, fails={m1_fails - 18}, pend={m1_pend}")
print()

# === Method 2: OR-based (OR High/Low anchor, EV target 0.30%) ===
print("=" * 70)
print("METHOD 2: OR boundary anchor, EV target 0.30%")
print("=" * 70)
m2 = bo_sessions.copy()
m2['win'] = False
m2['loss'] = False
m2['fakeout'] = False
m2['pending'] = True

for i, row in m2.iterrows():
    side = row['side']
    or_h = row['or_high']
    or_l = row['or_low']
    if side == 1:
        target_px = or_h * (1 + EV_TARGET_PCT / 100)
        invalid_px = or_h * (1 - EV_TARGET_PCT / 100)
    else:
        target_px = or_l * (1 - EV_TARGET_PCT / 100)
        invalid_px = or_l * (1 + EV_TARGET_PCT / 100)
    
    if row['crossed_opposite']:
        m2.at[i, 'fakeout'] = True
        m2.at[i, 'pending'] = False
    elif side == 1 and row['session_high'] >= target_px:
        m2.at[i, 'win'] = True
        m2.at[i, 'pending'] = False
    elif side == -1 and row['session_low'] <= target_px:
        m2.at[i, 'win'] = True
        m2.at[i, 'pending'] = False
    elif side == 1 and row['session_low'] <= invalid_px:
        m2.at[i, 'loss'] = True
        m2.at[i, 'pending'] = False
    elif side == -1 and row['session_high'] >= invalid_px:
        m2.at[i, 'loss'] = True
        m2.at[i, 'pending'] = False

m2_wins = m2['win'].sum()
m2_fails = m2['loss'].sum() + m2['fakeout'].sum()
m2_pend = m2['pending'].sum()
print(f"  Wins: {m2_wins}, Failed: {m2_fails}, Pending: {m2_pend}")
print(f"  Gunship: 55 FULL, 18 Failed, 0 Pending")
print(f"  Delta: wins={m2_wins - 55}, fails={m2_fails - 18}, pend={m2_pend}")
print()

# === Method 3: MFE > 0 (any positive excursion = FULL) ===
print("=" * 70)
print("METHOD 3: MFE > 0 = FULL, crossed opposite = Failed, else Failed")
print("=" * 70)
m3 = bo_sessions.copy()
m3['fakeout'] = m3['crossed_opposite']
# Win only if it didn't cross opposite
m3['win'] = (m3['mfe'] > 0) & ~m3['fakeout']
m3['loss'] = ~m3['win'] & ~m3['fakeout']
m3_wins = m3['win'].sum()
m3_fails = (m3['loss'] | m3['fakeout']).sum()
m3_pend = 0
print(f"  Wins: {m3_wins}, Failed: {m3_fails}, Pending: {m3_pend}")
print(f"  Gunship: 55 FULL, 18 Failed, 0 Pending")
print(f"  Delta: wins={m3_wins - 55}, fails={m3_fails - 18}, pend={m3_pend}")
print()

# === Method 4: Session MFE from OR > 0 = FULL ===
print("=" * 70)
print("METHOD 4: Session MFE from OR boundary > 0 = FULL")
print("=" * 70)
m4 = bo_sessions.copy()
m4['fakeout'] = m4['crossed_opposite']
m4['win'] = (m4['session_mfe'] > 0) & ~m4['fakeout']
m4['loss'] = ~m4['win'] & ~m4['fakeout']
m4_wins = m4['win'].sum()
m4_fails = (m4['loss'] | m4['fakeout']).sum()
print(f"  Wins: {m4_wins}, Failed: {m4_fails}, Pending: 0")
print(f"  Gunship: 55 FULL, 18 Failed, 0 Pending")
print(f"  Delta: wins={m4_wins - 55}, fails={m4_fails - 18}")
print()

# === Method 5: Close at cutoff on breakout side = FULL ===
print("=" * 70)
print("METHOD 5: Close at cutoff on breakout side of OR = FULL")
print("=" * 70)
m5 = bo_sessions.copy()
m5['fakeout'] = m5['crossed_opposite']
m5_raw_win = ((m5['side'] == 1) & (m5['close_at_cutoff'] > m5['or_high'])) | \
             ((m5['side'] == -1) & (m5['close_at_cutoff'] < m5['or_low']))
m5['win'] = m5_raw_win & ~m5['fakeout']
m5['loss'] = ~m5['win'] & ~m5['fakeout']
m5_wins = m5['win'].sum()
m5_fails = (m5['loss'] | m5['fakeout']).sum()
print(f"  Wins: {m5_wins}, Failed: {m5_fails}, Pending: 0")
print(f"  Gunship: 55 FULL, 18 Failed, 0 Pending")
print(f"  Delta: wins={m5_wins - 55}, fails={m5_fails - 18}")
print()

# === Method 6: Close at cutoff on breakout side of BO px = FULL ===
print("=" * 70)
print("METHOD 6: Close at cutoff on breakout side of BO px = FULL")
print("=" * 70)
m6 = bo_sessions.copy()
m6['fakeout'] = m6['crossed_opposite']
m6_raw_win = ((m6['side'] == 1) & (m6['close_at_cutoff'] > m6['bo_px'])) | \
             ((m6['side'] == -1) & (m6['close_at_cutoff'] < m6['bo_px']))
m6['win'] = m6_raw_win & ~m6['fakeout']
m6['loss'] = ~m6['win'] & ~m6['fakeout']
m6_wins = m6['win'].sum()
m6_fails = (m6['loss'] | m6['fakeout']).sum()
print(f"  Wins: {m6_wins}, Failed: {m6_fails}, Pending: 0")
print(f"  Gunship: 55 FULL, 18 Failed, 0 Pending")
print(f"  Delta: wins={m6_wins - 55}, fails={m6_fails - 18}")
print()

# === Summary table ===
print("=" * 70)
print("SUMMARY: All methods vs Gunship (55 FULL, 18 Failed)")
print("=" * 70)
print(f"{'Method':<45} {'Wins':>6} {'Fails':>6} {'Pend':>6} {'Match':>8}")
print("-" * 70)
methods = [
    ("1. DNL Current (BO px, EV 0.30%)", m1_wins, m1_fails, m1_pend),
    ("2. OR boundary, EV 0.30%", m2_wins, m2_fails, m2_pend),
    ("3. MFE > 0 = FULL", m3_wins, m3_fails, m3_pend),
    ("4. Session MFE from OR > 0 = FULL", m4_wins, m4_fails, 0),
    ("5. Close > OR boundary = FULL", m5_wins, m5_fails, 0),
    ("6. Close > BO px = FULL", m6_wins, m6_fails, 0),
]
for name, w, f, p in methods:
    match = "YES" if w == 55 and f == 18 and p == 0 else "NO"
    print(f"{name:<45} {w:>6} {f:>6} {p:>6} {match:>8}")

# Print session details for manual verification
print()
print("=" * 70)
print("SESSION DETAILS (first 10 and last 5)")
print("=" * 70)
cols = ['date', 'side', 'or_high', 'or_low', 'bo_px', 'mfe', 'mae', 
        'session_mfe', 'session_mae', 'close_at_cutoff', 'crossed_opposite']
print(bo_sessions[cols].head(10).to_string())
print("...")
print(bo_sessions[cols].tail(5).to_string())

# === Aggregate Statistics ===
print("\n" + "=" * 70)
print("AGGREGATE STATISTICS (PineScript Match)")
print("=" * 70)

def p_nearest(series, p):
    if len(series) == 0: return np.nan
    # Pine Script's array.percentile_nearest_rank matches numpy's 'nearest' interpolation
    return np.percentile(series, p, method='nearest')

# Using Method 4 which perfectly matches Pine Script's FULL/Failed session classification
m = m4.copy()
bulls = m[m['side'] == 1]
bears = m[m['side'] == -1]

bull_wins = bulls[bulls['win'] == True]
bear_wins = bears[bears['win'] == True]

print("BULL BREAKOUTS:")
print(f"  Count: {len(bulls)} (FULL: {len(bull_wins)}, Failed: {len(bulls) - len(bull_wins)})")
print(f"  --- MFE from Breakout Price ---")
print(f"  p50 MFE (FULL only): {p_nearest(bull_wins['mfe'], 50):.3f}%")
print(f"  p75 MFE (FULL only): {p_nearest(bull_wins['mfe'], 75):.3f}%")
print(f"  --- MFE from OR Boundary ---")
print(f"  p50 OR-MFE (FULL only): {p_nearest(bull_wins['session_mfe'], 50):.3f}%")
print(f"  p75 OR-MFE (FULL only): {p_nearest(bull_wins['session_mfe'], 75):.3f}%")
print(f"  --- MAE Stats (All Sessions) ---")
print(f"  p50 MAE (from BO px): {p_nearest(bulls['mae'], 50):.3f}%")
print(f"  p80 MAE (from BO px): {p_nearest(bulls['mae'], 80):.3f}%")
print(f"  p50 Session MAE (from OR): {p_nearest(bulls['session_mae'], 50):.3f}%")
print(f"  p80 Session MAE (from OR): {p_nearest(bulls['session_mae'], 80):.3f}%")

print("\nBEAR BREAKOUTS:")
print(f"  Count: {len(bears)} (FULL: {len(bear_wins)}, Failed: {len(bears) - len(bear_wins)})")
print(f"  --- MFE from Breakout Price ---")
print(f"  p50 MFE (FULL only): {p_nearest(bear_wins['mfe'], 50):.3f}%")
print(f"  p75 MFE (FULL only): {p_nearest(bear_wins['mfe'], 75):.3f}%")
print(f"  --- MFE from OR Boundary ---")
print(f"  p50 OR-MFE (FULL only): {p_nearest(bear_wins['session_mfe'], 50):.3f}%")
print(f"  p75 OR-MFE (FULL only): {p_nearest(bear_wins['session_mfe'], 75):.3f}%")
print(f"  --- MAE Stats (All Sessions) ---")
print(f"  p50 MAE (from BO px): {p_nearest(bears['mae'], 50):.3f}%")
print(f"  p80 MAE (from BO px): {p_nearest(bears['mae'], 80):.3f}%")
print(f"  p50 Session MAE (from OR): {p_nearest(bears['session_mae'], 50):.3f}%")
print(f"  p80 Session MAE (from OR): {p_nearest(bears['session_mae'], 80):.3f}%")

# === Extrapolate Today's Levels ===
print("\n" + "=" * 70)
print("TODAY'S PROJECTED PRICE LEVELS (Extrapolating History)")
print("=" * 70)

# Fetch today's data (2026-06-29) directly from live storage
df_today_raw = pd.read_parquet('data/live/live_storage_-NQ.parquet')
df_today_raw['datetime'] = pd.to_datetime(df_today_raw['timestamp'], utc=True)
df_today_raw = df_today_raw.set_index('datetime')
df_today = df_today_raw[(df_today_raw.index >= '2026-06-29') & (df_today_raw.index < '2026-06-30')].copy()

if not df_today.empty:
    et = pytz.timezone('America/New_York')
    df_today['et_time'] = df_today.index.tz_convert(et)
    df_today['et_hhmm'] = df_today['et_time'].dt.hour * 100 + df_today['et_time'].dt.minute
    
    # Calculate Today's OR (11:00 - 11:15 ET)
    today_or_bars = df_today[(df_today['et_hhmm'] >= OR_START) & (df_today['et_hhmm'] < OR_END)]
    if not today_or_bars.empty:
        today_or_high = today_or_bars['high'].max()
        today_or_low = today_or_bars['low'].min()
        print(f"Today's 1100 BO Opening Range: {today_or_low:,.2f} - {today_or_high:,.2f}")
        print()
        
        # Bull Projections
        bull_p50_mfe = p_nearest(bull_wins['session_mfe'], 50) / 100
        bull_p75_mfe = p_nearest(bull_wins['session_mfe'], 75) / 100
        bull_p50_mae = p_nearest(bulls['session_mae'], 50) / 100
        bull_p80_mae = p_nearest(bulls['session_mae'], 80) / 100
        
        print("BULL PROJECTIONS (Anchored to OR High):")
        print(f"  Target 1 (p50 MFE):     {today_or_high * (1 + bull_p50_mfe):,.2f}")
        print(f"  Target 2 (p75 MFE):     {today_or_high * (1 + bull_p75_mfe):,.2f}")
        print(f"  Invalidation (p50 MAE): {today_or_high * (1 - bull_p50_mae):,.2f}")
        print(f"  Invalidation (p80 MAE): {today_or_high * (1 - bull_p80_mae):,.2f}")
        print()
        
        # Bear Projections
        bear_p50_mfe = p_nearest(bear_wins['session_mfe'], 50) / 100
        bear_p75_mfe = p_nearest(bear_wins['session_mfe'], 75) / 100
        bear_p50_mae = p_nearest(bears['session_mae'], 50) / 100
        bear_p80_mae = p_nearest(bears['session_mae'], 80) / 100
        
        print("BEAR PROJECTIONS (Anchored to OR Low):")
        print(f"  Target 1 (p50 MFE):     {today_or_low * (1 - bear_p50_mfe):,.2f}")
        print(f"  Target 2 (p75 MFE):     {today_or_low * (1 - bear_p75_mfe):,.2f}")
        print(f"  Invalidation (p50 MAE): {today_or_low * (1 + bear_p50_mae):,.2f}")
        print(f"  Invalidation (p80 MAE): {today_or_low * (1 + bear_p80_mae):,.2f}")
    else:
        print("Today's OR data is not yet available.")
else:
    print("No data found for today.")