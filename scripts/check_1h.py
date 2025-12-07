import pandas as pd
from pathlib import Path

# Check new 1H CSV
csv = Path("data/TV_OHLC/CME_MINI_NQ1!, 60_3aff7.csv")
df = pd.read_csv(csv)
df["datetime"] = pd.to_datetime(df["time"], unit="s")
print(f"New 1H CSV: {df['datetime'].min()} to {df['datetime'].max()}, {len(df):,} bars")
print()
print("First 5 rows:")
print(df.head())
print()
print("Last 5 rows:")
print(df.tail())
