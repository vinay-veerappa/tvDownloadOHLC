import pandas as pd
import os

path = "data/live/live_storage_-NQ.parquet"
print(f"Reading {path}...")
df = pd.read_parquet(path)
print(f"Row count: {len(df)}")

df['time'] = pd.to_numeric(df['time'], errors='coerce')
df = df.sort_values('time')

print("\n--- Head (First 5 Rows) ---")
print(df.head(5))

print("\n--- Tail (Last 5 Rows) ---")
print(df.tail(5))

print("\n--- NaN Check ---")
print(df.isna().sum())

# Check specifically the Jan 14-21 range
print("\n--- Jan 14-21 Gap Check ---")
start_ms = 1736812800000 # Jan 14
end_ms = 1737417600000 # Jan 21
gap_data = df[(df['time'] >= start_ms) & (df['time'] <= end_ms)]

if gap_data.empty:
    print("❌ NO DATA between Jan 14 and Jan 21")
else:
    print(f"✅ Found {len(gap_data)} rows in gap window.")
    print(gap_data.head())
    print("...")
    print(gap_data.tail())
