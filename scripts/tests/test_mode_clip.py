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
d2 = df['dnPct'].iloc[-52:].clip(lower=0)

# Exact mode logic from our Pine
def get_pine_mode(series, binSize=0.1):
    rounded = np.round(series / binSize) * binSize
    counts = rounded.value_counts()
    modes = counts[counts == counts.max()].index
    print(f"Modes: {modes.tolist()} (count={counts.max()})")
    return modes

get_pine_mode(u2, 0.1)

# What if negative values weren't clipped to 0, but EXCLUDED ENTIRELY from the tracking array?
# So the N of the tracking array shrinks below 52?
# No, we tested positive-only and Mean was 2.96%.

# What about dnPct? 
# In reference_values.md: Mean Lo is 2.05%, Median Lo is 2.15%, Mode is 1.8%
print(f"Clipped Mean Lo: {d2.mean():.2f}%")
print(f"Clipped Median Lo: {d2.median():.2f}%")

d2_ex = df['dnPct'].iloc[-52:]
print(f"Standard Mean Lo: {d2_ex.mean():.2f}%")
print(f"Standard Median Lo: {d2_ex.median():.2f}%")
get_pine_mode(d2_ex, 0.1)
