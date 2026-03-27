import pandas as pd
import os
import sys

LIVE_DIR = r"c:\Users\vinay\tvDownloadOHLC\data\live"
symbol = sys.argv[1] if len(sys.argv) > 1 else "/NQ"
safe_symbol = symbol.replace("/", "-")
LIVE_FILE = f"live_storage_{safe_symbol}.parquet"
path = os.path.join(LIVE_DIR, LIVE_FILE)

if os.path.exists(path):
    try:
        df = pd.read_parquet(path)
        print(f"--- {symbol} ---")
        print("Columns:", df.columns)
        print("Sample Data:")
        print(df.tail())
        if 'time' in df.columns:
             print("Last Time Value (UTC):", pd.to_datetime(df['time'].iloc[-1], unit='ms'))
    except Exception as e:
        print(f"Error reading parquet: {e}")
else:
    print(f"File not found: {path}")
