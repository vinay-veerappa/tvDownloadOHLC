import os
import pandas as pd
from datetime import datetime, timezone
import json

path_live = os.path.join("data", "live", "live_storage_-NQ.parquet")
print(f"Checking parquet file: {path_live}")

if os.path.exists(path_live):
    df_live = pd.read_parquet(path_live)
    print(f"Total rows in live storage: {len(df_live)}")
    
    if 'time' in df_live.columns:
        first_time = df_live['time'].iloc[0]
        unit = 'ms' if first_time > 10**11 else 's'
        df_live['datetime_utc'] = pd.to_datetime(df_live['time'], unit=unit, utc=True)
        
        # Sort by time
        df_live = df_live.sort_values('time')
        
        # Print the last 15 candles
        print("\nLast 15 candles in parquet:")
        last_15 = df_live.tail(15)
        for idx, row in last_15.iterrows():
            # Convert time to timestamp and print it
            print(f"Time (raw): {row['time']}, UTC: {row['datetime_utc']}, O: {row['open']}, H: {row['high']}, L: {row['low']}, C: {row['close']}, V: {row['volume']}")
else:
    print(f"Parquet file {path_live} not found.")

# Let's also check if there is a live json file
path_json = os.path.join("data", "live", "live_chart_-NQ.json")
if os.path.exists(path_json):
    print(f"\nChecking JSON file: {path_json}")
    with open(path_json, 'r') as f:
        data = json.load(f)
    candles = data.get('candles', [])
    print(f"Total candles in JSON: {len(candles)}")
    if candles:
        print("\nLast 10 candles in JSON:")
        for c in candles[-10:]:
            raw_time = c.get('time', 0)
            dt_utc = datetime.fromtimestamp(raw_time / 1000, tz=timezone.utc)
            print(f"Time: {raw_time}, UTC: {dt_utc}, O: {c.get('open')}, H: {c.get('high')}, L: {c.get('low')}, C: {c.get('close')}")
else:
    print(f"JSON file {path_json} not found.")
