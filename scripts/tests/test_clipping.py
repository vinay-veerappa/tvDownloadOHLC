import pandas as pd
import numpy as np

csv_path = r'C:\Users\vinay\Downloads\CME_MINI_NQ1!, 1W_9e077.csv'
df = pd.read_csv(csv_path)
df['time'] = pd.to_datetime(df['time'], utc=True)
df = df.sort_values('time').reset_index(drop=True)
df['ema5'] = df['close'].ewm(span=5, adjust=False).mean()

df['upPct'] = ((df['high'].shift(1) - df['ema5'].shift(2)) / df['ema5'].shift(2)) * 100
df['dnPct'] = ((df['ema5'].shift(2) - df['low'].shift(1)) / df['ema5'].shift(2)) * 100

u2 = df['upPct'].iloc[-52:].copy()
d2 = df['dnPct'].iloc[-52:].copy()

print(f"Original Mean Hi: {u2.mean():.2f}%")
print(f"Original Median: {u2.median():.2f}%")

u2_clipped = u2.clip(lower=0)
print(f"Clipped to 0 Mean Hi: {u2_clipped.mean():.2f}%")

u2_dropped = u2[u2 >= -1.0]
print(f"Dropped lowest outliers Mean Hi: {u2_dropped.mean():.2f}%")

# Let's test a couple variations
for clip_val in [0, -0.5, -1.0, 0.5]:
    u_c = u2.clip(lower=clip_val)
    print(f"Clipped {clip_val} Mean: {u_c.mean():.2f}%, Median: {u_c.median():.2f}%")

