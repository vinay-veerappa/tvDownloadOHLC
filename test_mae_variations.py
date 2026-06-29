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

# Convert to 1m timeframe (including today's data)
df_hist = df[(df.index >= '2026-03-16') & (df.index < '2026-06-30')]
# Keep 1-minute timeframe instead of resampling
# df_hist = df_hist.resample('5min', label='left', closed='left').agg({'open':'first', 'high':'max', 'low':'min', 'close':'last', 'volume':'sum'}).dropna()

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
for date, day_5m in df_hist.groupby('date'):
    rth_5m = day_5m[(day_5m['et_hhmm'] >= 930) & (day_5m['et_hhmm'] < 1600)]
    if rth_5m.empty: continue
    
    or_bars = rth_5m[(rth_5m['et_hhmm'] >= OR_START) & (rth_5m['et_hhmm'] < OR_END)]
    if or_bars.empty: continue
    
    or_high = or_bars['high'].max()
    or_low = or_bars['low'].min()
    
    data_5m = rth_5m[(rth_5m['et_hhmm'] >= OR_END) & (rth_5m['et_hhmm'] < CUTOFF)]
    if data_5m.empty: continue
    
    bo_side = 0
    bo_px = None
    bo_idx = None
    for idx, row in data_5m.iterrows():
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
    
    post_bo = data_5m.loc[bo_idx:]
    if bo_side == 1:
        mfe = ((post_bo['high'].max() - bo_px) / bo_px) * 100
        mae = ((bo_px - post_bo['low'].min()) / bo_px) * 100
        session_mfe = ((data_5m['high'].max() - or_high) / or_high) * 100
        session_mae = ((or_high - data_5m['low'].min()) / or_high) * 100
        swapped_mae = ((or_low - data_5m['low'].min()) / or_low) * 100
    else:
        mfe = ((bo_px - post_bo['low'].min()) / bo_px) * 100
        mae = ((post_bo['high'].max() - bo_px) / bo_px) * 100
        session_mfe = ((or_low - data_5m['low'].min()) / or_low) * 100
        session_mae = ((data_5m['high'].max() - or_low) / or_low) * 100
        swapped_mae = ((data_5m['high'].max() - or_high) / or_high) * 100
        
    close_at_cutoff = data_5m['close'].iloc[-1]
    crossed = (bo_side == 1 and close_at_cutoff < or_low) or (bo_side == -1 and close_at_cutoff > or_high)
    
    sessions.append({
        'side': bo_side, 'mfe': mfe, 'mae': mae, 
        'session_mfe': session_mfe, 'session_mae': session_mae, 
        'swapped_mae': swapped_mae, 'crossed': crossed
    })

bo = pd.DataFrame(sessions)
bo['win'] = (bo['session_mfe'] > 0) & ~bo['crossed']

bulls = bo[bo['side'] == 1]
bears = bo[bo['side'] == -1]

bull_wins = bulls[bulls['win']]
bear_wins = bears[bears['win']]

print("=== 5-MIN TIMEFRAME MAE PERCENTILES ===")

def print_metrics(name, df_subset):
    print(f"\n--- {name} (N={len(df_subset)}) ---")
    print(f"  P50 MAE (from BO): {p_nearest(df_subset['mae'], 50):.4f}%")
    print(f"  P80 MAE (from BO): {p_nearest(df_subset['mae'], 80):.4f}%")
    print(f"  P50 Session MAE (from OR): {p_nearest(df_subset['session_mae'], 50):.4f}%")
    print(f"  P80 Session MAE (from OR): {p_nearest(df_subset['session_mae'], 80):.4f}%")
    print(f"  P50 Swapped MAE: {p_nearest(df_subset['swapped_mae'], 50):.4f}%")
    print(f"  P80 Swapped MAE: {p_nearest(df_subset['swapped_mae'], 80):.4f}%")

print_metrics("BULL BREAKOUTS (All)", bulls)
print_metrics("BULL BREAKOUTS (Wins Only)", bull_wins)
print_metrics("BEAR BREAKOUTS (All)", bears)
print_metrics("BEAR BREAKOUTS (Wins Only)", bear_wins)
