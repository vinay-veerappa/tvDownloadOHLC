import pandas as pd
import os

FILE_PATH = r"c:\Users\vinay\tvDownloadOHLC\data\VVIX_1d.parquet"

def inspect():
    if not os.path.exists(FILE_PATH):
        print("File not found.")
        return
        
    df = pd.read_parquet(FILE_PATH)
    print("Columns:", df.columns)
    print("Head:")
    print(df.head())
    print("\nTail:")
    print(df.tail())
    
    # Check max values
    if 'open' in df.columns:
        print(f"\nMax Open: {df['open'].max()}")
        print(f"Min Open: {df['open'].min()}")
        print(f"Mean Open: {df['open'].mean()}")
        
    # Check Date parsing
    if 'time' in df.columns:
        df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True).dt.tz_convert('America/New_York')
        print("\nDate Sample:")
        print(df['dt'].head())

if __name__ == "__main__":
    inspect()
