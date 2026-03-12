import pandas as pd
import numpy as np

w_path = r'C:\Users\vinay\Downloads\CME_MINI_NQ1!, 1W_9e077.csv'
df = pd.read_csv(w_path)
df['time'] = pd.to_datetime(df['time'], utc=True)
df = df.sort_values('time').reset_index(drop=True)
df['ema5'] = df['close'].ewm(span=5, adjust=False).mean()

df['upPct'] = ((df['high'].shift(1) - df['ema5'].shift(2)) / df['ema5'].shift(2)) * 100
df['upPct'] = df['upPct'].clip(lower=0)

# Try different lookbacks
for length in range(12, 100, 2):
    u = df['upPct'].iloc[-length:]
    msg = f"Lookback {length}: Mean={u.mean():.2f}%, Median={u.median():.2f}%"
    if round(u.mean(), 1) == 3.2 or round(u.median(), 1) == 3.2:
        print(f"** MATCH ** -> {msg}")
    
