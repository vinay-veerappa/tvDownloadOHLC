import pandas as pd

w_path = r'C:\Users\vinay\Downloads\CME_MINI_NQ1!, 1W_9e077.csv'
df = pd.read_csv(w_path)
df['time'] = pd.to_datetime(df['time'], utc=True)
df = df.sort_values('time').reset_index(drop=True)

df['ema5'] = df['close'].ewm(span=5, adjust=False).mean()
up = ((df['high'].shift(1) - df['ema5'].shift(2)) / df['ema5'].shift(2)) * 100

print("Last 5 upPct values:")
print(up.tail(5).tolist())

