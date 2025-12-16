import sys
import os
import argparse
from pathlib import Path
import json
import subprocess
import pandas as pd
import shutil
import data_utils

# Fix Path to allow imports
sys.path.append(os.getcwd())

# Import Generation Logic
import scripts.update_intraday as update_intraday
import scripts.precompute_profiler as profiler
import scripts.precompute_level_touches as level_touches
import scripts.precompute_range_dist as range_dist
import scripts.precompute_hod_lod as hod_lod
import scripts.precompute_daily_hod_lod as daily_hod
import scripts.precompute_sessions as sessions
import scripts.precompute_vwap as vwap

def ensure_time_column(ticker):
    print(f">> Step 0: Ensuring Schema Compatibility for {ticker}...")
    file_path = Path("data") / f"{ticker}_1m.parquet"
    if not file_path.exists():
        print(f"  Error: {file_path} not found.")
        return

    df = pd.read_parquet(file_path)
    dirty = False
    
    # Check for 'time' column (Unix Epoch)
    if 'time' not in df.columns:
        print("  Missing 'time' column. Adding it from Index...")
        if not isinstance(df.index, pd.DatetimeIndex):
            print("  Index is not DatetimeIndex. Attempting conversion...")
            df.index = pd.to_datetime(df.index)
            
        df['time'] = df.index.astype(int) // 10**9
        dirty = True
        
    if dirty:
        data_utils.safe_save_parquet(df, str(file_path))
        print(f"  ✅ Schema updated and saved to {file_path}")
    else:
        print("  ✅ Schema is already compatible.")

def regenerate_all(ticker="ES1"):
    print(f"\n=== REGENERATING DATA FOR {ticker} ===\n")
    
    # 0. FIX SCHEMA
    ensure_time_column(ticker)
    
    # 1. UPSAMPLE (1m -> 5m, 15m, 1h, 4h)
    print("\n>> Step 1: Upsampling Timeframes...")
    update_intraday.upsample_from_1m(ticker)
    
    # 2. RUN ANALYSIS PROFILERS
    print(f"\n>> Step 2: Running Analysis Profilers for {ticker}...")
    
    print("  - Daily Sessions (Profiler Core)...")
    sessions.precompute_daily_sessions(ticker)
    
    print("  - Profiler Stats (Recomputing)...")
    profiler.precompute_ticker(ticker)
    
    print("  - Level Touches...")
    results = level_touches.compute_level_touches(ticker)
    output_path = Path("data") / f'{ticker}_level_touches.json'
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"    Saved {output_path}")

    print("  - Range Distribution...")
    range_dist.precompute_range_distribution(ticker)
    
    print("  - Intraday HOD/LOD...")
    hod_lod.precompute_hod_lod(ticker)
    
    print("  - VWAP (1m)...")
    vwap.precompute_vwap(ticker, '1m')
    
    # 3. CHUNK FOR WEB
    print("\n>> Step 3: Generating Web JSON Chunks (Global)...")
    cmd = ["python", "scripts/convert_to_chunked_json.py", ticker]
    subprocess.run(cmd, check=True)
    
    print(f"\n=== REGENERATION COMPLETE FOR {ticker} ===")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("ticker", nargs="?", default="ES1", help="Ticker to regenerate (default: ES1)")
    args = parser.parse_args()
    
    regenerate_all(args.ticker)
