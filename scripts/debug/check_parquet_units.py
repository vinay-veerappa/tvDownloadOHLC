import pandas as pd
import os

def check_units(path):
    print(f"Checking {path}...")
    df = pd.read_parquet(path)
    
    if 'time' not in df.columns:
        if 'timestamp' in df.columns:
            df['time'] = df['timestamp']
        else:
            print("No time/timestamp column")
            return

    df['time'] = pd.to_numeric(df['time'], errors='coerce')
    
    # Bucket by magnitude
    seconds = df[df['time'] < 1e11]
    ms = df[(df['time'] >= 1e11) & (df['time'] < 1e14)]
    us = df[df['time'] >= 1e14]
    
    print(f"  Total Rows: {len(df)}")
    print(f"  Seconds (< 1e11): {len(seconds)}")
    if not seconds.empty:
        print(f"    Range: {seconds['time'].min()} -> {seconds['time'].max()}")
        print(f"    Date: {pd.to_datetime(seconds['time'], unit='s').min()} -> {pd.to_datetime(seconds['time'], unit='s').max()}")

    print(f"  Millis (>= 1e11): {len(ms)}")
    if not ms.empty:
        print(f"    Range: {ms['time'].min()} -> {ms['time'].max()}")
        print(f"    Date: {pd.to_datetime(ms['time'], unit='ms').min()} -> {pd.to_datetime(ms['time'], unit='ms').max()}")

    print(f"  Micros (>= 1e14): {len(us)}")

check_units("data/live/live_storage_-NQ.parquet")
