import pandas as pd

w_path = r'C:\Users\vinay\Downloads\CME_MINI_NQ1!, 1W_9e077.csv'
df = pd.read_csv(w_path)
df['time'] = pd.to_datetime(df['time'], utc=True)
df = df.sort_values('time').reset_index(drop=True)

df['ema5'] = df['close'].ewm(span=5, adjust=False).mean()

# [2] offset logic: prevWeekHigh vs prevWeeklyEma (which is ema5.shift(2))
up_pct = ((df['high'].shift(1) - df['ema5'].shift(2)) / df['ema5'].shift(2)) * 100
up_pct_clipped = up_pct.clip(lower=0)

u = up_pct_clipped.iloc[-52:]
print(f"Clipped [2] Mean Hi: {u.mean():.2f}%")
print(f"Clipped [2] Median Hi: {u.median():.2f}%")

dn_pct = ((df['ema5'].shift(2) - df['low'].shift(1)) / df['ema5'].shift(2)) * 100
dn_pct_clipped = dn_pct.clip(lower=0)

d = dn_pct_clipped.iloc[-52:]
print(f"Clipped [2] Mean Lo: {d.mean():.2f}%")
print(f"Clipped [2] Median Lo: {d.median():.2f}%")
