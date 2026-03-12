import pandas as pd

df = pd.read_parquet(r'data/NQ1_1W.parquet')
df.index = df.index.tz_convert('US/Eastern')
df = df.dropna()

print("Parquet Weekly OHLC - Last 5 weeks:")
print(df[['open', 'high', 'low', 'close']].tail(5))
