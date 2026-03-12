import pandas as pd
import numpy as np

csv_path = r'C:\Users\vinay\Downloads\CME_MINI_NQ1!, 1W_9e077.csv'
df = pd.read_csv(csv_path)
df['time'] = pd.to_datetime(df['time'], utc=True)
df = df.sort_values('time').reset_index(drop=True)
df['ema5'] = df['close'].ewm(span=5, adjust=False).mean()

# Verified [2] formulation
df['upPct'] = ((df['high'].shift(1) - df['ema5'].shift(2)) / df['ema5'].shift(2)) * 100
df['dnPct'] = ((df['ema5'].shift(2) - df['low'].shift(1)) / df['ema5'].shift(2)) * 100

u2 = df['upPct'].iloc[-52:]
d2 = df['dnPct'].iloc[-52:]

print(f"Standard Mean Hi: {u2.mean():.2f}%")
print(f"Positive-Only Mean Hi: {u2[u2 > 0].mean():.2f}%")

# What if the mode of 0.3% is the mode of the DAILY distances, but over the last 52 weeks?
df_d = pd.read_csv(r'C:\Users\vinay\Downloads\CME_MINI_NQ1!, 1D_96a65.csv')
df_d['time'] = pd.to_datetime(df_d['time'], utc=True)
df_d = df_d.sort_values('time').reset_index(drop=True)

daily_emas = pd.Series(index=df_d.index, dtype=float)

# Fast O(N^2) for small N
for i in range(len(df_d)):
    d_time = df_d['time'].iloc[i]
    # Find the latest weekly EMA calculation that was available BEFORE this day
    # Technically we want the weekly EMA of the week that ENDED before this day
    past_weeks = df[df['time'] < d_time - pd.Timedelta(days=2)]
    if len(past_weeks) > 1:
        daily_emas.iloc[i] = past_weeks['ema5'].iloc[-1]

df_d['prevWeeklyEma'] = daily_emas
up_d = ((df_d['high'] - df_d['prevWeeklyEma']) / df_d['prevWeeklyEma']) * 100

u_d_52 = up_d.iloc[-260:]  # Roughly 52 weeks
modes_d = np.round(u_d_52, 1).value_counts()
print(f"\nDaily Modes (last 52 weeks):")
print(modes_d.head(5))
