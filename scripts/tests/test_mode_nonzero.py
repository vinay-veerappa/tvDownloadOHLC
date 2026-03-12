import pandas as pd
import numpy as np

csv_path = r'C:\Users\vinay\Downloads\CME_MINI_NQ1!, 1W_9e077.csv'
df = pd.read_csv(csv_path)
df['time'] = pd.to_datetime(df['time'], utc=True)
df = df.sort_values('time').reset_index(drop=True)
df['ema5'] = df['close'].ewm(span=5, adjust=False).mean()

df['upPct'] = ((df['high'].shift(1) - df['ema5'].shift(2)) / df['ema5'].shift(2)) * 100
df['dnPct'] = ((df['ema5'].shift(2) - df['low'].shift(1)) / df['ema5'].shift(2)) * 100

u2 = df['upPct'].iloc[-52:].clip(lower=0)

def get_pine_mode(series, binSize=0.1):
    rounded = np.round(series / binSize) * binSize
    counts = rounded.value_counts()
    
    # Strip 0.0 out to see what the highest non-zero mode is!
    if 0.0 in counts:
        counts = counts.drop(0.0)
    
    modes = counts[counts == counts.max()].index
    print(f"Non-Zero Modes: {modes.tolist()} (count={counts.max()})")

get_pine_mode(u2, 0.1)
