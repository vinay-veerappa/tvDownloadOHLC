"""Analyze Chicago timezone CSV file format and find overlap with Unix timestamp CSV"""
import pandas as pd
from pathlib import Path

# Load the semicolon-delimited Chicago timezone file
csv_chicago = Path("data/TV_OHLC/nq-1m_bk.csv")
df_chicago = pd.read_csv(csv_chicago, sep=";", header=None,
                         names=["date", "time", "open", "high", "low", "close", "volume"])

print("=== Chicago timezone file info ===")
print(f"Total rows: {len(df_chicago):,}")
print(f"First row: {df_chicago.iloc[0]['date']} {df_chicago.iloc[0]['time']}")
print(f"Last row: {df_chicago.iloc[-1]['date']} {df_chicago.iloc[-1]['time']}")
print()

# Show first 10 rows
print("=== First 10 rows ===")
print(df_chicago.head(10).to_string())
print()

# Show last 10 rows
print("=== Last 10 rows ===")
print(df_chicago.tail(10).to_string())
print()

# Load the Unix timestamp file (UTC) for comparison
csv_unix = Path("data/TV_OHLC/CME_MINI_NQ1!, 1_e0c08.csv")
df_unix = pd.read_csv(csv_unix)
df_unix.columns = [c.lower() for c in df_unix.columns]
df_unix["datetime"] = pd.to_datetime(df_unix["time"], unit="s")

print("=== Unix timestamp file info (UTC) ===")
print(f"Total rows: {len(df_unix):,}")
print(f"First: {df_unix['datetime'].min()}")
print(f"Last: {df_unix['datetime'].max()}")
print()

# Try to find matching OHLC values
# Let's look for a specific OHLC pattern in the Unix file
sample = df_unix.iloc[100:105]
print("=== Sample from Unix file (rows 100-104) ===")
for idx, row in sample.iterrows():
    print(f"  {row['datetime']}: O={row['open']:.2f} H={row['high']:.2f} L={row['low']:.2f} C={row['close']:.2f}")
print()

# Search for similar OHLC in Chicago file
target_open = sample.iloc[0]["open"]
target_high = sample.iloc[0]["high"]
target_low = sample.iloc[0]["low"]
target_close = sample.iloc[0]["close"]

print(f"=== Searching for O={target_open}, H={target_high}, L={target_low}, C={target_close} ===")
matches = df_chicago[
    (abs(df_chicago["open"] - target_open) < 0.01) &
    (abs(df_chicago["high"] - target_high) < 0.01) &
    (abs(df_chicago["low"] - target_low) < 0.01) &
    (abs(df_chicago["close"] - target_close) < 0.01)
]

if len(matches) > 0:
    print(f"Found {len(matches)} matches:")
    for idx, row in matches.iterrows():
        print(f"  Row {idx}: {row['date']} {row['time']} - O={row['open']} H={row['high']} L={row['low']} C={row['close']}")
else:
    print("No exact matches found. Trying with larger tolerance...")
    matches = df_chicago[
        (abs(df_chicago["open"] - target_open) < 1.0) &
        (abs(df_chicago["high"] - target_high) < 1.0) &
        (abs(df_chicago["low"] - target_low) < 1.0) &
        (abs(df_chicago["close"] - target_close) < 1.0)
    ]
    print(f"Found {len(matches)} approximate matches")
    if len(matches) > 0:
        print(matches.head(10).to_string())
