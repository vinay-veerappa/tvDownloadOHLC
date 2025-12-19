
import pandas as pd
import os
from datetime import datetime

# Path to data
DATA_DIR = "C:/Users/vinay/tvDownloadOHLC/data"
SPY_PATH = os.path.join(DATA_DIR, "SPY_15m.parquet")

def inspect_data():
    if not os.path.exists(SPY_PATH):
        print("SPY file not found.")
        return

    df = pd.read_parquet(SPY_PATH)
    
    # Filter for Nov 2024
    # Timestamps are likely UTC or ET? The filename says 15m.
    # Let's inspect rows around Nov 4 - Nov 12 2024.
    
    # Check index type
    if not isinstance(df.index, pd.DatetimeIndex):
        if 'time' in df.columns:
            df['datetime'] = pd.to_datetime(df['time'], unit='s')
            df.set_index('datetime', inplace=True)
        elif 'datetime' in df.columns:
            df['datetime'] = pd.to_datetime(df['datetime'])
            df.set_index('datetime', inplace=True)
            
    # Filter
    print(f"Index Type: {df.index.dtype}")
    if not df.empty:
        print(f"Range: {df.index.min()} to {df.index.max()}")
        
    start_date = "2025-11-04"
    end_date = "2025-11-12"
    
    mask = (df.index >= start_date) & (df.index <= end_date)
    subset = df.loc[mask]
    
    print(f"--- SPY Data {start_date} to {end_date} ---")
    print(subset[['open', 'high', 'low', 'close', 'volume']].tail(50))
    
    # Check specifically Nov 5 Close (EOD)
    nov5 = subset.loc[subset.index.date == pd.Timestamp("2025-11-05").date()]
    if not nov5.empty:
        print("\n--- Nov 5 Last 5 Bars ---")
        print(nov5.tail(5))
        
    # Check Nov 7-9
    nov7_9 = subset.loc[(subset.index >= "2025-11-07") & (subset.index <= "2025-11-10")]
    print("\n--- Nov 7-9 Data ---")
    print(nov7_9[['close']].head(20))
    print("...")
    print(nov7_9[['close']].tail(20))
    
    mask = (df.index >= start_date) & (df.index <= end_date)
    subset = df.loc[mask]
    
    print(f"--- SPY Data {start_date} to {end_date} ---")
    print(subset[['open', 'high', 'low', 'close', 'volume']].tail(50))
    
    # Check specifically Nov 5 Close (EOD)
    nov5 = subset.loc[subset.index.date == pd.Timestamp("2024-11-05").date()]
    if not nov5.empty:
        print("\n--- Nov 5 Last 5 Bars ---")
        print(nov5.tail(5))
        
    # Check Nov 7-9
    nov7_9 = subset.loc[(subset.index >= "2024-11-07") & (subset.index <= "2024-11-10")]
    print("\n--- Nov 7-9 Data ---")
    print(nov7_9[['close']].head(20))
    print("...")
    print(nov7_9[['close']].tail(20))

if __name__ == "__main__":
    inspect_data()
