import pandas as pd
import os

LIVE_DIR = r"c:\Users\vinay\tvDownloadOHLC\data\live"
LIVE_FILE = "live_storage_-NQ.parquet"
path = os.path.join(LIVE_DIR, LIVE_FILE)

if os.path.exists(path):
    try:
        df = pd.read_parquet(path)
        print("Columns:", df.columns)
        print("Index:", df.index.name)
        print("Sample Data:")
        print(df.head())
        print("Time Column Type:", df['time'].dtype if 'time' in df.columns else "No time col")
        if 'time' in df.columns:
            print("First Time Value:", df['time'].iloc[0])
    except Exception as e:
        print(f"Error reading parquet: {e}")
else:
    print(f"File not found: {path}")
