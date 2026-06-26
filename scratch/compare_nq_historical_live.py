import os
import pandas as pd
from datetime import datetime, timezone

hist_path = os.path.join("data", "NQ1_1m.parquet")
live_path = os.path.join("data", "live", "live_storage_-NQ.parquet")

print("=== HISTORICAL PARQUET (data/NQ1_1m.parquet) ===")
if os.path.exists(hist_path):
    df_hist = pd.read_parquet(hist_path)
    print(f"Total rows: {len(df_hist)}")
    print(f"Columns: {list(df_hist.columns)}")
    print(f"Index name/type: {df_hist.index.name} / {type(df_hist.index)}")
    
    # Check if time column exists or if it's the index
    if 'time' in df_hist.columns:
        times = df_hist['time']
    else:
        df_hist = df_hist.reset_index()
        # Find time column
        time_cols = [c for c in df_hist.columns if c in ['time', 'datetime', 'timestamp']]
        if time_cols:
            times = df_hist[time_cols[0]]
        else:
            times = df_hist.index
            
    print(f"Sample raw times: {times.tail(5).tolist()}")
    # Convert sample times to datetime
    sample_dts = []
    for t in times.tail(5):
        unit = 'ms' if t > 10**11 else 's'
        sample_dts.append(pd.to_datetime(t, unit=unit, utc=True))
    print(f"Sample Datetimes (UTC): {sample_dts}")
else:
    print("Historical parquet file not found.")

print("\n=== LIVE PARQUET (data/live/live_storage_-NQ.parquet) ===")
if os.path.exists(live_path):
    df_live = pd.read_parquet(live_path)
    print(f"Total rows: {len(df_live)}")
    print(f"Columns: {list(df_live.columns)}")
    print(f"Sample raw times: {df_live['time'].tail(5).tolist()}")
    
    sample_dts = []
    for t in df_live['time'].tail(5):
        unit = 'ms' if t > 10**11 else 's'
        sample_dts.append(pd.to_datetime(t, unit=unit, utc=True))
    print(f"Sample Datetimes (UTC): {sample_dts}")
else:
    print("Live parquet file not found.")
