import pandas as pd
import os

def check_daily_range():
    file_path = r"C:\Users\vinay\tvDownloadOHLC\data\ES1_1D.parquet"
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return

    print(f"Reading {file_path}...")
    df = pd.read_parquet(file_path)
    
    # Handle schema
    if 'time' in df.columns:
        if pd.api.types.is_numeric_dtype(df['time']):
             df['datetime'] = pd.to_datetime(df['time'], unit='s')
        else:
             df['datetime'] = pd.to_datetime(df['time'])
    elif isinstance(df.index, pd.DatetimeIndex):
        df['datetime'] = df.index
        
    if 'datetime' in df.columns:
        print(f"Range: {df['datetime'].min()} to {df['datetime'].max()}")
        print(f"Rows: {len(df)}")
    else:
        print("Could not determine datetime column.")

if __name__ == "__main__":
    check_daily_range()
