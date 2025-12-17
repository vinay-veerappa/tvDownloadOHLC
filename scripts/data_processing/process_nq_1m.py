"""Process NQ 1m CSV (Chicago timezone) and sync with other timeframes"""
import pandas as pd
from pathlib import Path

data_dir = Path("data")
tv_dir = Path("data/TV_OHLC")

# Load the new NQ 1m file (semicolon-delimited, no header)
csv_file = tv_dir / "nq-1m_bk.csv"
print("Loading NQ 1m CSV file...")

df = pd.read_csv(csv_file, sep=";", header=None, 
                 names=["date", "time", "open", "high", "low", "close", "volume"])

print(f"Total rows: {len(df):,}")

# Try multiple date formats
# Some rows may be MM/DD/YYYY, others may be DD/MM/YYYY
df["datetime"] = pd.to_datetime(df["date"] + " " + df["time"], format="mixed", dayfirst=False)

# Check for parse errors
parse_errors = df["datetime"].isna().sum()
print(f"Parse errors: {parse_errors}")

# Drop rows with parsing errors
df = df.dropna(subset=["datetime"])

# Convert time from Chicago (US/Central) to UTC
# Use 'NaT' for ambiguous times during DST transitions
print("Converting from Chicago time to UTC...")
try:
    df["datetime"] = df["datetime"].dt.tz_localize("America/Chicago", ambiguous="NaT", nonexistent="NaT")
    # Drop rows that couldn't be localized (DST transitions)
    before_count = len(df)
    df = df.dropna(subset=["datetime"])
    after_count = len(df)
    if before_count > after_count:
        print(f"  Dropped {before_count - after_count} rows with ambiguous DST times")
    df["datetime"] = df["datetime"].dt.tz_convert("UTC")
    df["datetime"] = df["datetime"].dt.tz_localize(None)  # Remove tz info for parquet compatibility
except Exception as e:
    print(f"Timezone conversion error: {e}")
    print("Proceeding without timezone conversion (assuming UTC)")
    df.index = df["datetime"]

df = df.set_index("datetime")
df = df[["open", "high", "low", "close", "volume"]]
df = df.sort_index()

print(f"NQ1 1m new (UTC): {df.index.min()} to {df.index.max()} ({len(df):,} bars)")
print()

# Merge with existing 1m
existing_1m = data_dir / "NQ1_1m.parquet"
if existing_1m.exists():
    old_df = pd.read_parquet(existing_1m)
    print(f"Existing NQ1_1m: {old_df.index.min()} to {old_df.index.max()} ({len(old_df):,} bars)")
    df = pd.concat([old_df, df])
    df = df[~df.index.duplicated(keep="last")]
    df = df.sort_index()

# Save 1m
df.to_parquet(existing_1m)
print(f"NQ1_1m saved: {df.index.min()} to {df.index.max()} ({len(df):,} bars)")

# Resample to 5m, 15m, 1h, 4h
print("\nResampling to fill gaps in higher timeframes...")

for tf, rule in [("5m", "5min"), ("15m", "15min"), ("1h", "1h"), ("4h", "4h")]:
    resampled = df.resample(rule, label="left", closed="left").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum"
    }).dropna()
    
    output_path = data_dir / f"NQ1_{tf}.parquet"
    
    # Merge with existing
    if output_path.exists():
        existing = pd.read_parquet(output_path)
        resampled = pd.concat([existing, resampled])
        resampled = resampled[~resampled.index.duplicated(keep="last")]
        resampled = resampled.sort_index()
    
    resampled.to_parquet(output_path)
    print(f"NQ1_{tf}: {resampled.index.min().date()} to {resampled.index.max().date()} ({len(resampled):,} bars)")

print("\nDone!")
