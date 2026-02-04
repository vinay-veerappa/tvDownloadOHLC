import pandas as pd
import os

path = r"c:\Users\vinay\tvDownloadOHLC\data\live\live_storage_-NQ.parquet"

if os.path.exists(path):
    try:
        df = pd.read_parquet(path)
        print(f"File: {os.path.basename(path)}")
        print(f"Rows: {len(df)}")
        print(f"Columns: {df.columns.tolist()}")
        
        # Check index/timestamp
        if 'timestamp' in df.columns:
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='s', utc=True)
            df = df.set_index('datetime')
        elif 'time' in df.columns: # Sometimes live storage uses 'time'
             df['datetime'] = pd.to_datetime(df['time'], unit='s', utc=True)
             df = df.set_index('datetime')
            
        if isinstance(df.index, pd.DatetimeIndex):
            df.index = df.index.tz_convert('US/Eastern')
            print(f"Start: {df.index[0]}")
            print(f"End:   {df.index[-1]}")
            
            # Check resolution
            if len(df) > 1:
                diffs = df.index.to_series().diff().dropna()
                mode_diff = diffs.mode().iloc[0]
                print(f"Resolution (Mode): {mode_diff}")
            
            # Check last few rows
            print("\nLast 2 Rows:")
            print(df.tail(2))
            
    except Exception as e:
        print(f"Error: {e}")
else:
    print(f"Not found: {path}")
