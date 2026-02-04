
import pandas as pd
import numpy as np
from pathlib import Path
import os
import glob

# Config
SOURCE_DIR = "data/TV_OHLC/Badj"
OUTPUT_DIR = "data"

# Ticker Mapping from filename patterns
TICKER_MAP = {
    "CME_MINI_NQ1!": "NQ1",
    "CME_MINI_ES1!": "ES1",
    "CBOT_MINI_YM1!": "YM1",
    "CME_MINI_RTY1!": "RTY1",
    "COMEX_GC1!": "GC1",
    "NYMEX_CL1!": "CL1"
}

def create_unadjusted_parquet():
    print(f"Scanning {SOURCE_DIR} for unadjusted CSVs...")
    
    csv_files = glob.glob(os.path.join(SOURCE_DIR, "*.csv"))
    
    for fpath in csv_files:
        fname = os.path.basename(fpath)
        
        # Identify Ticker
        ticker = None
        for key, val in TICKER_MAP.items():
            if key in fname:
                ticker = val
                break
        
        if not ticker:
            print(f"Skipping {fname}: No matching ticker found.")
            continue
            
        output_parquet = os.path.join(OUTPUT_DIR, f"{ticker}_1d_unadjusted.parquet")
        
        print(f"\nProcessing {ticker} from {fname}...")
        try:
            df = pd.read_csv(fpath)
        except Exception as e:
            print(f"Error reading CSV: {e}")
            continue

        # Check columns
        required_cols = ['time', 'open', 'high', 'low', 'close']
        
        # Normalize columns
        df.columns = [c.lower() for c in df.columns]
        
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            print(f"Error: Missing columns {missing}. Found: {df.columns}")
            continue

        # Process Timestamp
        # TradingView Daily CSV usually uses Unix Timestamp for 1D bar start (Exchange Time)
        try:
            df['time'] = pd.to_datetime(df['time'], unit='s')
        except:
             # Try parsing if ISO
             df['time'] = pd.to_datetime(df['time'])

        df = df.set_index('time').sort_index()
        
        # Ensure float types
        for col in ['open', 'high', 'low', 'close']:
            df[col] = df[col].astype(float)
            
        if 'volume' in df.columns:
            df['volume'] = df['volume'].astype(float)

        # Basic Stats
        count = len(df)
        start_date = df.index[0]
        end_date = df.index[-1]
        
        print(f"  Processed {count} daily bars.")
        print(f"  Range: {start_date} to {end_date}")
        print(f"  Open Price Range: {df['open'].min()} to {df['open'].max()}")

        # Save
        df.to_parquet(output_parquet)
        print(f"  ✅ Saved to {output_parquet}")

if __name__ == "__main__":
    create_unadjusted_parquet()
