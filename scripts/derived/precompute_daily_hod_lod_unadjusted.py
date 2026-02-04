
import pandas as pd
import json
import argparse
from pathlib import Path
from datetime import datetime
import os

# Config
DATA_DIR = Path("data")
TICKERS = ["NQ1", "ES1", "YM1", "RTY1", "GC1", "CL1"]

def compute_unadjusted_hod_lod():
    print("Generating Hybrid Daily Stats (Unadjusted Prices + Adjusted Times)...")
    
    for ticker in TICKERS:
        input_parquet = DATA_DIR / f"{ticker}_1d_unadjusted.parquet"
        adjusted_json_path = DATA_DIR / f"{ticker}_daily_hod_lod.json"
        output_json = DATA_DIR / f"{ticker}_daily_hod_lod_unadjusted.json"
        
        if not input_parquet.exists():
            print(f"Skipping {ticker}: {input_parquet} not found.")
            continue
            
        # Load Adjusted Data (Source of Truth for Time)
        adjusted_data = {}
        if adjusted_json_path.exists():
            print(f"  Loading timing data from {adjusted_json_path}...")
            with open(adjusted_json_path, 'r') as f:
                adjusted_data = json.load(f)
        else:
            print(f"  Warning: Adjusted data not found for {ticker}. Timing will be missing.")

        print(f"Processing {ticker} Unadjusted Prices...")
        df = pd.read_parquet(input_parquet)
        
        results = {}
        
        for ts, row in df.iterrows():
            # Apply +5h shift to get past midnight for "Next Day" logic
            # UTC 23:00 + 5h = 04:00 (Next Day)
            trading_dt = ts + pd.Timedelta(hours=5) 
            date_str = trading_dt.strftime('%Y-%m-%d')
            
            # 1. Get Prices from Unadjusted (Source of Truth for Distribution)
            daily_open = float(row['open'])
            daily_high = float(row['high'])
            daily_low = float(row['low'])
            daily_close = float(row['close'])
            volume = float(row['volume']) if 'volume' in row else 0
            
            # 2. Get Times from Adjusted 1m Data (Source of Truth for Timing)
            # Default placeholders
            hod_time = "00:00"
            lod_time = "00:00"
            hod_ts = int(ts.timestamp())
            lod_ts = int(ts.timestamp())
            
            # Try to find matching date in adjusted data
            if date_str in adjusted_data:
                adj_entry = adjusted_data[date_str]
                # Copy timing fields
                hod_time = adj_entry.get("hod_time", "00:00")
                lod_time = adj_entry.get("lod_time", "00:00")
                hod_ts = adj_entry.get("hod_ts", int(ts.timestamp()))
                lod_ts = adj_entry.get("lod_ts", int(ts.timestamp()))
            
            results[date_str] = {
                "daily_open": daily_open,
                "daily_high": daily_high,
                "daily_low": daily_low,
                "daily_close": daily_close,
                "volume": volume,
                # Using Unadjusted Prices for HOD/LOD reference
                "hod_price": daily_high, 
                "lod_price": daily_low,
                # Using Adjusted Times
                "hod_time": hod_time,
                "lod_time": lod_time,
                "hod_ts": hod_ts,
                "lod_ts": lod_ts
            }

        with open(output_json, 'w') as f:
            json.dump(results, f, indent=2)
            
        print(f"  ✅ Saved {len(results)} hybrid entries to {output_json}")

if __name__ == "__main__":
    compute_unadjusted_hod_lod()
