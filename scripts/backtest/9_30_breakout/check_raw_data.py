
import pandas as pd
import os

def check_raw():
    path = r"c:\Users\vinay\tvDownloadOHLC\data\NQ1_1m.parquet"
    df = pd.read_parquet(path)
    if df.index.tz is not None: 
        df = df.tz_convert('US/Eastern')
    else:
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index, unit='ms' if df.index[0] > 1e12 else 's')
        df = df.tz_localize('UTC').tz_convert('US/Eastern')
        
    print("First 5 rows of raw data:")
    print(df.head())
    
    day = "2022-01-03"
    day_data = df[df.index.normalize() == day]
    print(f"\nData for {day} (Open):")
    print(day_data.between_time('09:29', '09:35'))

if __name__ == "__main__":
    check_raw()
