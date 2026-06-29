import pandas as pd
import numpy as np
import pytz

def p_nearest(series, p):
    if len(series) == 0: return np.nan
    return np.percentile(series, p, method='nearest')

# Load data and build sessions manually for clarity
df = pd.read_parquet('data/live/live_storage_-NQ.parquet')
df['datetime'] = pd.to_datetime(df['timestamp'], utc=True)
df = df.set_index('datetime')

# Timeframe configuration: Set to True to match the TradingView reference indicator values (which uses 1m data under the hood),
# or False to use strict 5-minute chart bar calculation.
USE_1M_TIMEFRAME = True

# Filter exactly as the main script
df_hist = df[(df.index >= '2026-03-16') & (df.index < '2026-06-29')]

if not USE_1M_TIMEFRAME:
    # Convert to 5m timeframe
    df_hist = df_hist.resample('5min', label='left', closed='left').agg({'open':'first', 'high':'max', 'low':'min', 'close':'last', 'volume':'sum'}).dropna()

# Drop holidays to match TradingView 73 sessions exactly
df_hist = df_hist[~df_hist.index.strftime('%Y-%m-%d').isin(['2026-05-25', '2026-06-19'])]

et = pytz.timezone('America/New_York')
df_hist = df_hist.copy()
df_hist['et_time'] = df_hist.index.tz_convert(et)
df_hist['et_hhmm'] = df_hist['et_time'].dt.hour * 100 + df_hist['et_time'].dt.minute
df_hist['date'] = df_hist['et_time'].dt.date

OR_START = 1100
OR_END = 1115
CUTOFF = 1230

sessions = []
for date, day_1m in df_hist.groupby('date'):
    rth_1m = day_1m[(day_1m['et_hhmm'] >= 930) & (day_1m['et_hhmm'] < 1600)]
    if rth_1m.empty: continue
    
    or_bars = rth_1m[(rth_1m['et_hhmm'] >= OR_START) & (rth_1m['et_hhmm'] < OR_END)]
    if or_bars.empty: continue
    
    or_high = or_bars['high'].max()
    or_low = or_bars['low'].min()
    
    data_1m = rth_1m[(rth_1m['et_hhmm'] >= OR_END) & (rth_1m['et_hhmm'] < CUTOFF)]
    if data_1m.empty: continue
    
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
            
    if bo_side == 0: continue
    
    post_bo = data_1m.loc[bo_idx:]
    if bo_side == 1:
        mfe = ((post_bo['high'].max() - bo_px) / bo_px) * 100
        mae = ((bo_px - post_bo['low'].min()) / bo_px) * 100
        session_mfe = ((data_1m['high'].max() - or_high) / or_high) * 100
        # Swapped PineScript parameter bug: or_low is passed where or_high is expected
        session_mae = ((or_low - data_1m['low'].min()) / or_low) * 100
    else:
        mfe = ((bo_px - post_bo['low'].min()) / bo_px) * 100
        mae = ((post_bo['high'].max() - bo_px) / bo_px) * 100
        session_mfe = ((or_low - data_1m['low'].min()) / or_low) * 100
        # Swapped PineScript parameter bug: or_high is passed where or_low is expected
        session_mae = ((data_1m['high'].max() - or_high) / or_high) * 100
        
    close_at_cutoff = data_1m['close'].iloc[-1]
    crossed = (bo_side == 1 and close_at_cutoff < or_low) or (bo_side == -1 and close_at_cutoff > or_high)
    
    sessions.append({
        'side': bo_side, 'mfe': mfe, 'mae': mae, 'session_mfe': session_mfe, 'session_mae': session_mae, 'crossed': crossed
    })

bo = pd.DataFrame(sessions)
bo['win'] = (bo['session_mfe'] > 0) & ~bo['crossed']
bo['fake'] = bo['crossed']

bulls = bo[bo['side'] == 1]
bull_wins = bulls[bulls['win']]
bull_fakes = bulls[bulls['fake']]

# Percentiles
p80_mae_wins = p_nearest(bull_wins['mae'], 80)
p80_mae_losses = p_nearest(bulls[~bulls['win']]['mae'], 80)
p25_mae = p_nearest(bulls['mae'], 25)
p20_bo = p_nearest(bulls['mfe'], 20)
p50_fake_bo = p_nearest(bull_fakes['mfe'], 50)
p75_fake_bo = p_nearest(bull_fakes['mfe'], 75)
p50_fake_or = p_nearest(bull_fakes['session_mfe'], 50)
p75_fake_or = p_nearest(bull_fakes['session_mfe'], 75)
rev_p25 = p_nearest(bull_fakes['session_mae'], 25)
rev_p50 = p_nearest(bull_fakes['session_mae'], 50)
p50_mae_all = p_nearest(bulls['mae'], 50)
p50_mfe_wins = p_nearest(bull_wins['mfe'], 50)
p50_mfe_or = p_nearest(bull_wins['session_mfe'], 50)
avg_mfe_wins = bull_wins['mfe'].mean()

# Today's levels
or_high = 29735.00
bo_px = 29739.50
tv_bo_px = 29773.50

print("=========================================================")
print("TODAY'S LEVELS USING PINESCRIPT METHODOLOGY (Bull Breakout)")
print("=========================================================")
print(f"OR High: {or_high}")
print(f"BO Px (1m close): {bo_px}")
print(f"BO Px (TradingView inferred 5m close): {tv_bo_px}")
print("\n--- USING 1m BO Px (29739.50) ---")
print(f"Invalidation (Wins P80 = {p80_mae_wins:.3f}%): {bo_px * (1 - p80_mae_wins/100):.2f}")
print(f"Pullback Activation (P25 MAE = {p25_mae:.3f}%): {bo_px * (1 - p25_mae/100):.2f}")
print(f"BO Cashflow (P20 MFE = {p20_bo:.3f}%): {bo_px * (1 + p20_bo/100):.2f}")
print(f"Pivot Level (P50 Fake MFE): {bo_px * (1 + p50_fake_bo/100):.2f}")
print(f"BO Confirmation (P75 Fake MFE = {p75_fake_bo:.3f}%): {bo_px * (1 + p75_fake_bo/100):.2f}")
print(f"Reversal Zone Top (P25 Fake OR-MAE = {rev_p25:.3f}%): {or_high * (1 - rev_p25/100):.2f}")
print(f"Reversal Zone Bot (P50 Fake OR-MAE = {rev_p50:.3f}%): {or_high * (1 - rev_p50/100):.2f}")

print("\n--- USING TradingView 5m BO Px (29773.50) ---")
print(f"Invalidation (Wins P80 = {p80_mae_wins:.3f}%): {tv_bo_px * (1 - p80_mae_wins/100):.2f}")
print(f"Pullback Activation (P25 MAE = {p25_mae:.3f}%): {tv_bo_px * (1 - p25_mae/100):.2f}")
print(f"BO Cashflow (P20 MFE = {p20_bo:.3f}%): {tv_bo_px * (1 + p20_bo/100):.2f}")
print(f"Pivot Level (P50 Fake MFE): {tv_bo_px * (1 + p50_fake_bo/100):.2f}")
print(f"BO Confirmation (P75 Fake MFE = {p75_fake_bo:.3f}%): {tv_bo_px * (1 + p75_fake_bo/100):.2f}")

print("\n--- ALTERNATE (Using OR High Anchor instead of BO Px) ---")
print(f"BO Confirmation (P75 Fake OR-MFE = {p75_fake_or:.3f}%): {or_high * (1 + p75_fake_or/100):.2f}")
print(f"Pivot Level (P50 Fake OR-MFE = {p50_fake_or:.3f}%): {or_high * (1 + p50_fake_or/100):.2f}")
print(f"Median MFE Target (P50 MFE): {or_high * (1 + p50_mfe_or/100):.2f}")
