import pandas as pd
import os
from datetime import datetime

files = [
    r"c:\Users\vinay\tvDownloadOHLC\data\NQ1_1d.parquet",
    r"c:\Users\vinay\tvDownloadOHLC\data\NQ1_1d_unadjusted.parquet"
]

print(f"Current System Time: {datetime.now()}")

for path in files:
    if os.path.exists(path):
        try:
            df = pd.read_parquet(path)
            # Check for timestamp or index
            last_ts = None
            if 'timestamp' in df.columns:
                last_ts = df['timestamp'].iloc[-1]
                last_date = pd.to_datetime(last_ts, unit='s', utc=True).tz_convert('US/Eastern')
            elif isinstance(df.index, pd.DatetimeIndex):
                last_date = df.index[-1]
                if last_date.tz is None:
                     last_date = last_date.tz_localize('UTC').tz_convert('US/Eastern')
                else:
                     last_date = last_date.tz_convert('US/Eastern')
            
            print(f"\nFile: {os.path.basename(path)}")
            print(f"Last Bar Time: {last_date}")
            print(f"Rows: {len(df)}")
            
            # Print last few rows to see what 'today' looks like
            print(df.tail(2))
            
        except Exception as e:
            print(f"Error reading {path}: {e}")
    else:
        print(f"\nFile not found: {path}")
