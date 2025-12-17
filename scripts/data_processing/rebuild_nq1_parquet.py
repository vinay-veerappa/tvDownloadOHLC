"""
Load the converted NQ1 CSV (with Unix timestamps) and rebuild all parquet files.
This will fix any corruption from previous updates.
"""
import pandas as pd
from pathlib import Path

data_dir = Path("data")
csv_path = Path("data/TV_OHLC/nq-1m_converted.csv")

print("Loading converted NQ1 CSV (Unix timestamps)...")
df = pd.read_csv(csv_path)
print(f"Loaded {len(df):,} rows")

# Convert Unix time to datetime index
df["datetime"] = pd.to_datetime(df["time"], unit="s")
df = df.set_index("datetime")
df = df[["open", "high", "low", "close", "volume"]]
df = df.sort_index()

# Remove any duplicates
before = len(df)
df = df[~df.index.duplicated(keep="last")]
after = len(df)
if before != after:
    print(f"Removed {before - after} duplicate rows")

print(f"Date range: {df.index.min()} to {df.index.max()}")
print()

# Save NQ1_1m.parquet
output_1m = data_dir / "NQ1_1m.parquet"
df.to_parquet(output_1m)
print(f"NQ1_1m: {len(df):,} bars saved")

# Resample to higher timeframes
timeframes = [
    ("5m", "5min"),
    ("15m", "15min"),
    ("1h", "1h"),
    ("4h", "4h"),
]

for tf_name, rule in timeframes:
    resampled = df.resample(rule, label="left", closed="left").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum"
    }).dropna()
    
    output_path = data_dir / f"NQ1_{tf_name}.parquet"
    resampled.to_parquet(output_path)
    print(f"NQ1_{tf_name}: {len(resampled):,} bars saved ({resampled.index.min().date()} to {resampled.index.max().date()})")

print()
print("All NQ1 parquet files rebuilt successfully!")
