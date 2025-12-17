"""
Convert NQ1 Chicago timezone CSV to intermediate CSV with Unix timestamps.
Then verify conversion with 50 random sample rows.
"""
import pandas as pd
from pathlib import Path
import pytz

# Load the Chicago timezone CSV
csv_chicago = Path("data/TV_OHLC/nq-1m_bk.csv")
print("Loading Chicago timezone CSV...")
df = pd.read_csv(csv_chicago, sep=";", header=None,
                 names=["date", "time", "open", "high", "low", "close", "volume"])

print(f"Loaded {len(df):,} rows")
print(f"Date format: DD/MM/YYYY (e.g., {df.iloc[0]['date']})")
print()

# Parse date with DD/MM/YYYY format and combine with time
print("Parsing dates (DD/MM/YYYY format)...")
df["datetime_str"] = df["date"] + " " + df["time"]
df["datetime"] = pd.to_datetime(df["datetime_str"], format="%d/%m/%Y %H:%M", errors="coerce")

# Check for parse errors
parse_errors = df["datetime"].isna().sum()
print(f"Parse errors: {parse_errors}")

if parse_errors > 0:
    print("Sample of parse errors:")
    print(df[df["datetime"].isna()].head())

# Convert Chicago time to UTC
# Chicago = America/Chicago (CST = UTC-6, CDT = UTC-5)
print()
print("Converting Chicago timezone to UTC...")
chicago_tz = pytz.timezone("America/Chicago")

# Localize to Chicago timezone (handle DST)
df["datetime"] = df["datetime"].dt.tz_localize(chicago_tz, ambiguous="NaT", nonexistent="NaT")

# Drop rows with ambiguous/nonexistent times (DST transitions)
ambiguous_count = df["datetime"].isna().sum()
print(f"Ambiguous/nonexistent times dropped: {ambiguous_count}")
df = df.dropna(subset=["datetime"])

# Convert to UTC
df["datetime"] = df["datetime"].dt.tz_convert("UTC")

# Convert to Unix timestamp
df["unix_time"] = df["datetime"].apply(lambda x: int(x.timestamp()))

# Remove timezone info for cleaner output
df["datetime"] = df["datetime"].dt.tz_localize(None)

print(f"Conversion complete: {len(df):,} rows")
print(f"Date range: {df['datetime'].min()} to {df['datetime'].max()}")
print()

# Save intermediate CSV with Unix timestamps
output_path = Path("data/TV_OHLC/nq-1m_converted.csv")
output_df = df[["unix_time", "open", "high", "low", "close", "volume"]].copy()
output_df.columns = ["time", "open", "high", "low", "close", "volume"]
output_df.to_csv(output_path, index=False)
print(f"Saved intermediate CSV to: {output_path}")
print()

# Verify against Unix timestamp file
print("=== Verifying conversion with 50 sample rows ===")
csv_unix = Path("data/TV_OHLC/CME_MINI_NQ1!, 1_e0c08.csv")
df_unix = pd.read_csv(csv_unix)
df_unix.columns = [c.lower() for c in df_unix.columns]
df_unix["datetime"] = pd.to_datetime(df_unix["time"], unit="s")

# Sample 50 rows from Unix file
sample_indices = list(range(0, 500, 10))  # Every 10th row from 0-500
matches = 0
misses = 0

for i in sample_indices[:50]:
    if i >= len(df_unix):
        break
    
    row = df_unix.iloc[i]
    o, h, l, c = row["open"], row["high"], row["low"], row["close"]
    
    # Find in converted data
    converted_matches = df[
        (abs(df["open"] - o) < 0.01) &
        (abs(df["high"] - h) < 0.01) &
        (abs(df["low"] - l) < 0.01) &
        (abs(df["close"] - c) < 0.01)
    ]
    
    if len(converted_matches) >= 1:
        matches += 1
    else:
        misses += 1
        print(f"MISS at row {i}: UTC={row['datetime']} O={o:.2f}")

print()
print(f"Results: {matches} matches, {misses} misses out of {min(50, len(sample_indices))} samples")
print(f"Match rate: {matches/(matches+misses)*100:.1f}%")
