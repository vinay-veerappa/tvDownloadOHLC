
import pandas as pd
from pathlib import Path

def inspect_csv(csv_path):
    print(f"Inspecting {csv_path}...")
    try:
        # Read first few lines to detect format
        df_head = pd.read_csv(csv_path, nrows=5)
        print("Header:")
        print(df_head.columns.tolist())
        print("First 5 rows:")
        print(df_head)

        # Read full file for range (using generic parser for speed if needed, but NinjaTrader usually needs custom)
        # Attempt minimal read
        df = pd.read_csv(csv_path, usecols=[0, 1], names=['Date', 'Time'])
        # If header exists, skip it
        if not df.iloc[0,0].replace('/','').isdigit():
             df = pd.read_csv(csv_path, usecols=[0, 1])
        
        # Combine date/time
        df['datetime_str'] = df.iloc[:,0].astype(str) + ' ' + df.iloc[:,1].astype(str)
        # Parse start and end only
        start_dt = pd.to_datetime(df['datetime_str'].iloc[0])
        end_dt = pd.to_datetime(df['datetime_str'].iloc[-1])
        
        print(f"\nRange found:")
        print(f"Start: {start_dt}")
        print(f"End:   {end_dt}")
        print(f"Total Rows: {len(df)}")
        
    except Exception as e:
        print(f"Error reading CSV: {e}")

if __name__ == "__main__":
    inspect_csv("data/Ninjatrader/NQ Monday 1755.csv")
