
import pandas as pd
import os

DATA_DIR = "C:/Users/vinay/tvDownloadOHLC/data"
SPY_PATH = os.path.join(DATA_DIR, "SPY_1d.parquet")

def inspect_daily():
    if not os.path.exists(SPY_PATH):
        print("SPY Daily file not found.")
        return

    df = pd.read_parquet(SPY_PATH)
    
    # Ensure datetime index
    if not isinstance(df.index, pd.DatetimeIndex):
         time_cols = [c for c in df.columns if 'time' in c.lower() or 'date' in c.lower()]
         if time_cols:
             df['datetime'] = pd.to_datetime(df[time_cols[0]])
             df.set_index('datetime', inplace=True)
    
    # Filter for Nov 2025
    start_date = "2025-11-03"
    end_date = "2025-11-10"
    
    mask = (df.index >= start_date) & (df.index <= end_date)
    subset = df.loc[mask]
    
    print(f"--- SPY Daily Data {start_date} to {end_date} ---")
    print(subset[['open', 'high', 'low', 'close', 'volume']])
    
    # Specific Check
    try:
        val = subset.loc[subset.index.strftime('%Y-%m-%d') == '2025-11-05', 'close'].values[0]
        print(f"\nNov 5 Close: {val}")
    except IndexError:
        print("\nNov 5 not found in Daily data.")

if __name__ == "__main__":
    inspect_daily()
