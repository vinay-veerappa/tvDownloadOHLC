import pandas as pd
import numpy as np
import pytz

def p_nearest(series, p):
    if len(series) == 0: return np.nan
    return np.percentile(series, p, method='nearest')

# Load NQ 1-min data from live storage
df = pd.read_parquet('data/live/live_storage_-NQ.parquet')
df['datetime'] = pd.to_datetime(df['timestamp'], utc=True)
df = df.set_index('datetime')
df_hist = df[(df.index >= '2026-03-16') & (df.index < '2026-06-30')]

# Skip holidays
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
        session_mae = ((or_high - data_1m['low'].min()) / or_high) * 100
        swapped_mae = ((or_low - data_1m['low'].min()) / or_low) * 100
    else:
        mfe = ((bo_px - post_bo['low'].min()) / bo_px) * 100
        mae = ((post_bo['high'].max() - bo_px) / bo_px) * 100
        session_mfe = ((or_low - data_1m['low'].min()) / or_low) * 100
        session_mae = ((data_1m['high'].max() - or_low) / or_low) * 100
        swapped_mae = ((data_1m['high'].max() - or_high) / or_high) * 100
        
    close_at_cutoff = data_1m['close'].iloc[-1]
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

print("=== REVERSE ENGINEERING BEAR MAE = 0.183% ===")
for p in range(1, 101):
    val_bo = p_nearest(bear_wins['mae'], p)
    val_or = p_nearest(bear_wins['session_mae'], p)
    val_all_bo = p_nearest(bears['mae'], p)
    val_all_or = p_nearest(bears['session_mae'], p)
    
    if abs(val_bo - 0.183) < 0.005:
        print(f"Match Bear Win BO MAE P{p}: {val_bo:.4f}%")
    if abs(val_or - 0.183) < 0.005:
        print(f"Match Bear Win OR MAE P{p}: {val_or:.4f}%")
    if abs(val_all_bo - 0.183) < 0.005:
        print(f"Match Bear All BO MAE P{p}: {val_all_bo:.4f}%")
    if abs(val_all_or - 0.183) < 0.005:
        print(f"Match Bear All OR MAE P{p}: {val_all_or:.4f}%")

print("\n=== REVERSE ENGINEERING BULL MAE = 0.123% ===")
for p in range(1, 101):
    val_bo = p_nearest(bull_wins['mae'], p)
    val_or = p_nearest(bull_wins['session_mae'], p)
    val_all_bo = p_nearest(bulls['mae'], p)
    val_all_or = p_nearest(bulls['session_mae'], p)
    
    if abs(val_bo - 0.123) < 0.005:
        print(f"Match Bull Win BO MAE P{p}: {val_bo:.4f}%")
    if abs(val_or - 0.123) < 0.005:
        print(f"Match Bull Win OR MAE P{p}: {val_or:.4f}%")
    if abs(val_all_bo - 0.123) < 0.005:
        print(f"Match Bull All BO MAE P{p}: {val_all_bo:.4f}%")
    if abs(val_all_or - 0.123) < 0.005:
        print(f"Match Bull All OR MAE P{p}: {val_all_or:.4f}%")
