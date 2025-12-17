"""Compare Unix timestamp CSV with current NQ1 data to diagnose timezone issue"""
import pandas as pd
from pathlib import Path

# Check the CSV with Unix timestamps
csv_file = Path("data/TV_OHLC/CME_MINI_NQ1!, 1_e0c08.csv")
df_unix = pd.read_csv(csv_file)

print("CSV with Unix timestamps:")
print(f"  Rows: {len(df_unix):,}")
print(f"  Columns: {df_unix.columns.tolist()}")
print()

# First and last rows
print("First 3 rows:")
print(df_unix.head(3))
print()

print("Last 3 rows:")
print(df_unix.tail(3))
print()

# Convert timestamps
first_time = df_unix["time"].iloc[0]
last_time = df_unix["time"].iloc[-1]

print(f"First Unix timestamp: {first_time} = {pd.to_datetime(first_time, unit='s')}")
print(f"Last Unix timestamp: {last_time} = {pd.to_datetime(last_time, unit='s')}")
print()

# Compare with current NQ1_1m parquet
nq_1m = pd.read_parquet("data/NQ1_1m.parquet")
print("Current NQ1_1m.parquet:")
print(f"  Range: {nq_1m.index.min()} to {nq_1m.index.max()}")
print(f"  Rows: {len(nq_1m):,}")
