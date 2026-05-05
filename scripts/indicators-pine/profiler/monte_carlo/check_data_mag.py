
import pandas as pd
from pathlib import Path

path = Path("data/NQ1_1m.parquet")
df = pd.read_parquet(path)
print(f"Data Head:\n{df.head()}")
print(f"Index TZ: {df.index.tz}")

# Check magnitude of moves
print(f"\nPrice Sample: {df['close'].iloc[0]} to {df['close'].iloc[-1]}")
daily_ranges = df['high'].resample('D').max() - df['low'].resample('D').min()
print(f"Mean Daily Range (Points): {daily_ranges.mean():.2f}")

# Check 18:00 to 04:00 move for one day
sample_date = df.index[len(df)//2].date()
start = pd.Timestamp(f"{sample_date} 18:00").tz_localize(df.index.tz)
end = start + pd.Timedelta(hours=10)
try:
    subset = df.loc[start:end]
    open_p = subset.iloc[0]['open']
    last_p = subset.iloc[-1]['close']
    pct = (last_p - open_p) / open_p * 100
    print(f"\nSample Move ({start} to {end}): {pct:.4f}%")
except Exception as e:
    print(f"Sample failed: {e}")
