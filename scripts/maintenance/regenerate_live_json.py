import os
import sys
import json
import pandas as pd
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
LIVE_DIR = os.path.join(DATA_DIR, "live")

def regenerate_json(ticker_safe):
    parquet_path = os.path.join(LIVE_DIR, f"live_storage_{ticker_safe}.parquet")
    json_path = os.path.join(LIVE_DIR, f"live_chart_{ticker_safe}.json")
    
    if not os.path.exists(parquet_path):
        print(f"Skipping {ticker_safe}: Parquet not found.")
        return

    print(f"Reading {parquet_path}...")
    try:
        df = pd.read_parquet(parquet_path)
    except Exception as e:
        print(f"Error reading parquet: {e}")
        return

    print(f"Initial row count: {len(df)}")
    if df.empty:
        print("Dataset empty.")
        return

    # 2. Standardize Columns
    if 'time' not in df.columns and 'timestamp' in df.columns:
        df['time'] = df['timestamp']
        
    df = df.dropna(subset=['time'])
    print(f"After dropping null time: {len(df)}")
    
    # Convert to numeric
    df['time'] = pd.to_numeric(df['time'], errors='coerce')
    df = df.dropna(subset=['time'])
    print(f"After numeric conversion: {len(df)}")
    
    # Check max value
    max_t = df['time'].max()
    min_t = df['time'].min()
    print(f"Time Range (raw): {min_t} -> {max_t}")
    
    if max_t < 1e11: # Seconds
        print("Detected Seconds")
        df['time'] = (df['time'] * 1000).astype(int)
    else: # Already ms or us/ns
        if max_t > 1e16: # ns
             print("Detected Nanoseconds")
             df['time'] = (df['time'] / 1e6).astype(int)
        elif max_t > 1e13: # us
             print("Detected Microseconds")
             df['time'] = (df['time'] / 1000).astype(int)
        else: # ms
             print("Detected Milliseconds")
             df['time'] = df['time'].astype(int)

    # Ensure valid float values for prices
    cols = ['open', 'high', 'low', 'close', 'volume']
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce')
            
    # Check for NaN prices
    nan_prices = df[cols].isna().sum() 
    print(f"NaNs in columns:\n{nan_prices}")
    
    df = df.dropna(subset=['close']) # Need at least close
    print(f"After dropping null close: {len(df)}")
    
    # Ensure sorted
    df = df.sort_values('time')
    
    # Convert to list of dicts
    keep_cols = ['time'] + [c for c in cols if c in df.columns]
    candles = df[keep_cols].to_dict(orient='records')
    print(f"Final candle count: {len(candles)}")
    
    if not candles:
        print("No candles after conversion.")
        return

    last_candle = candles[-1]
    live_price = float(last_candle['close']) 
    
    last_update = datetime.now().isoformat()
    
    output = {
        "symbol": ticker_safe.replace("-", "/"), 
        "last_update": last_update,
        "live_price": live_price,
        "candles": candles
    }
    
    with open(json_path, 'w') as f:
        json.dump(output, f, indent=2)
        
    print(f"Successfully Regenerated {json_path}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        regenerate_json(sys.argv[1])
    else:
        print("Regenerating ALL live JSON files from parquets...")
        for file in os.listdir(LIVE_DIR):
            if file.startswith("live_storage_") and file.endswith(".parquet"):
                ticker = file.replace("live_storage_", "").replace(".parquet", "")
                regenerate_json(ticker)
