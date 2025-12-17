import pandas as pd
from pathlib import Path

def debug_chunking():
    parquet_path = Path("data/NQ1_1m.parquet")
    print(f"Reading {parquet_path}...")
    df = pd.read_parquet(parquet_path)
    
    print(f"Loaded {len(df)} rows.")
    print(f"Index Head: {df.index.min()}")
    print(f"Index Tail: {df.index.max()}")
    
    # Simulate Logic from convert_to_chunked_json.py
    df.columns = [c.lower() for c in df.columns]
    
    # Check time col
    has_time = 'time' in df.columns
    print(f"Has 'time' column: {has_time}")
    
    if has_time:
        print(f"Time Col Head: {df['time'].min()}")
        print(f"Time Col Tail: {df['time'].max()}")
    
    # Reset Index logic
    if has_time:
        df.reset_index(drop=True, inplace=True)
    else:
        df.reset_index(inplace=True)
        if 'index' in df.columns:
             df.rename(columns={'index': 'time'}, inplace=True)

    print(f"After Reset Index, Columns: {df.columns}")
    
    # Convert time to int
    if pd.api.types.is_datetime64_any_dtype(df['time']):
        print("Converting datetime column to int...")
        df['time'] = (df['time'].astype('int64') // 10**9).astype(int)
    
    # Sort
    print("Sorting by time...")
    df.sort_values('time', inplace=True)
    
    print(f"Sorted Time Head: {df['time'].iloc[0]}")
    print(f"Sorted Time Tail: {df['time'].iloc[-1]}")
    
    last_timestamp = df['time'].iloc[-1]
    print(f"Last Timestamp: {last_timestamp}")
    import datetime
    print(f"Last Date: {datetime.datetime.utcfromtimestamp(last_timestamp)}")

if __name__ == "__main__":
    debug_chunking()
