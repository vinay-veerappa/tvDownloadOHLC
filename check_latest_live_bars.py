import os
import pandas as pd
from datetime import datetime

live_es_path = "data/live/live_storage_-ES.parquet"

if os.path.exists(live_es_path):
    df_live = pd.read_parquet(live_es_path)
    df_live['datetime'] = pd.to_datetime(df_live['time'], unit='ms')
    
    # Filter for today (2026-06-23) after 13:55 UTC
    mask = (df_live['datetime'] >= '2026-06-23 13:55:00')
    df_slice = df_live[mask]
    
    print("=== Latest Live Storage 1m Bars ===")
    for idx, row in df_slice.iterrows():
        # Convert UTC to EDT (UTC-4)
        edt_time = row['datetime'] - pd.Timedelta(hours=4)
        print(f"UTC: {row['datetime']} | EDT: {edt_time} | Open: {row['open']}, High: {row['high']}, Low: {row['low']}, Close: {row['close']}, Vol: {row['volume']}")
else:
    print("live_storage_-ES.parquet not found!")
