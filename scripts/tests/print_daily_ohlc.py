import pandas as pd

df = pd.read_parquet(r'data/NQ1_1d.parquet')

# Make sure we have the index as datetime
if not pd.api.types.is_datetime64tz_dtype(df.index):
    df.index = pd.to_datetime(df.index, utc=True).tz_convert('US/Eastern')
else:
    df.index = df.index.tz_convert('US/Eastern')

df = df.dropna()

print("Parquet Daily OHLC - March 2026:")
recent_days = df.loc['2026-03-02':]

for date, row in recent_days.iterrows():
    print(f"{date.strftime('%Y-%m-%d %A')}: O={row['open']:.2f}, H={row['high']:.2f}, L={row['low']:.2f}, C={row['close']:.2f}")

