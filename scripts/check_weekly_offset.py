"""Check weekly data for timestamp offset issue"""
import pandas as pd
from pathlib import Path

# Load ES1 weekly CSV
weekly_csv = pd.read_csv("data/TV_OHLC/CME_MINI_ES1!, 1W.csv")

print("=== ES1 Weekly CSV - Last 5 rows ===")
for i in range(-5, 0):
    row = weekly_csv.iloc[i]
    ts = pd.to_datetime(row["time"], unit="s")
    print(f"{ts}: O={row['open']}, H={row['high']}, L={row['low']}, C={row['close']}")

print()

# Load ES1 daily parquet to aggregate for comparison
es_1d = pd.read_parquet("data/ES1_1D.parquet")

print("=== Aggregating daily to weekly for comparison ===")
# Get last few weeks
last_weeks = es_1d.tail(30).resample("W", label="left", closed="left").agg({
    "open": "first",
    "high": "max",
    "low": "min",
    "close": "last"
}).dropna()

print(last_weeks.tail(5))

print()

# Also check 1m for the current week
es_1m = pd.read_parquet("data/ES1_1m.parquet")
print("=== 1m aggregated by week ===")
weekly_from_1m = es_1m.resample("W", label="left", closed="left").agg({
    "open": "first",
    "high": "max",
    "low": "min", 
    "close": "last"
}).dropna()
print(weekly_from_1m.tail(5))
