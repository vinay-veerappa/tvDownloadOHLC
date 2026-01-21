import pandas as pd
import os
import sys

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
LIVE_DIR = os.path.join(DATA_DIR, "live")

def fix_parquet(ticker_safe):
    path = os.path.join(LIVE_DIR, f"live_storage_{ticker_safe}.parquet")
    if not os.path.exists(path):
        print(f"File not found: {path}")
        return

    print(f"Fixing {path}...")
    df = pd.read_parquet(path)
    
    if 'time' not in df.columns and 'timestamp' in df.columns:
        df['time'] = df['timestamp']
    
    # Force numeric
    df['time'] = pd.to_numeric(df['time'], errors='coerce')
    df = df.dropna(subset=['time'])

    # Convert Seconds to Milliseconds
    # Rule: < 1e11 (year 5138) ==> Seconds
    mask_sec = df['time'] < 1e11
    
    count_sec = mask_sec.sum()
    if count_sec > 0:
        print(f"  Converting {count_sec} rows from Seconds to Milliseconds...")
        df.loc[mask_sec, 'time'] = (df.loc[mask_sec, 'time'] * 1000).astype('int64')
        
    # Ensure all are int64
    df['time'] = df['time'].astype('int64')
    
    # Sort
    df = df.sort_values('time')
    
    # Save back
    df.to_parquet(path, index=False)
    print(f"✅ Fixed {path}. Range: {pd.to_datetime(df['time'].min(), unit='ms')} -> {pd.to_datetime(df['time'].max(), unit='ms')}")

if __name__ == "__main__":
    fix_parquet("-NQ")
    fix_parquet("-ES")
