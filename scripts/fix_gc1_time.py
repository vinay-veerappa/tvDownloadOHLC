import pandas as pd
import data_utils
from pathlib import Path

path = Path("data/GC1_1m.parquet")
print(f"Reading {path}...")
df = pd.read_parquet(path)
print(f"Loaded {len(df)} rows.")

if not isinstance(df.index, pd.DatetimeIndex):
    print("Converting index to DatetimeIndex...")
    df.index = pd.to_datetime(df.index)

print("Regenerating 'time' column...")
# Force recalculate
df['time'] = df.index.astype(int) // 10**9

print("Checking for NaNs in 'time'...")
nans = df['time'].isna().sum()
print(f"NaNs: {nans}")

if nans > 0:
    print("Filling NaNs...")
    df['time'] = df['time'].fillna(0).astype(int)

print("Saving...")
data_utils.safe_save_parquet(df, str(path))
print("Done.")
