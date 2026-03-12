import pandas as pd
import numpy as np

# Load TV exported CSV
csv_path = r'C:\Users\vinay\Downloads\CME_MINI_NQ1!, 1W_9e077.csv'
df = pd.read_csv(csv_path)

# Convert time and sort just in case
df['time'] = pd.to_datetime(df['time'], utc=True)
df = df.sort_values('time').reset_index(drop=True)

# Standard EMA(5)
# In Pine, ta.ema(c, length) uses an alpha of 2 / (length + 1)
df['ema5'] = df['close'].ewm(span=5, adjust=False).mean()

# Our Pine Script [2] offset logic:
# prevWeekHigh = high[1]  (high of the week that just completed)
# prevWeeklyEma = ema[2]  (ema of the week BEFORE the week that just completed)
df['upPct_2'] = ((df['high'].shift(1) - df['ema5'].shift(2)) / df['ema5'].shift(2)) * 100
df['dnPct_2'] = ((df['ema5'].shift(2) - df['low'].shift(1)) / df['ema5'].shift(2)) * 100

# Testing [1] offset logic just to compare:
df['upPct_1'] = ((df['high'].shift(1) - df['ema5'].shift(1)) / df['ema5'].shift(1)) * 100

# The indicator analyzes the *completed* weeks. 
# We look back 52 weeks from the most recent completed week.
# df.iloc[-1] is the current forming week.
u2 = df['upPct_2'].iloc[-52:]
d2 = df['dnPct_2'].iloc[-52:]

print("USING [2] OFFSET (prevWeeklyEma):")
print(f"Mean Hi: {u2.mean():.2f}%")
print(f"Mean Lo: {d2.mean():.2f}%")
print(f"Median Hi: {u2.median():.2f}%")
print(f"Median Lo: {d2.median():.2f}%")

# Mode nearest mean logic
def get_mode(series, bin_size=0.1):
    rounded = np.round(series / bin_size) * bin_size
    counts = rounded.value_counts()
    modes = counts[counts == counts.max()].index
    print(f"Modes array {bin_size} bin: {modes.tolist()} (count={counts.max()})")
    return modes

get_mode(u2, 0.1)

u1 = df['upPct_1'].iloc[-52:]
print("\nUSING [1] OFFSET (weeklyEma):")
print(f"Mean Hi: {u1.mean():.2f}%")
print(f"Median Hi: {u1.median():.2f}%")
get_mode(u1, 0.1)
