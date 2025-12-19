import sys
import os
import argparse
from pathlib import Path
import json
import subprocess
import pandas as pd
import shutil
# Fix Path to allow imports
sys.path.append(os.getcwd())

# Import Generation Logic
from scripts.utils import data_utils
from scripts.market_data import update_intraday
from scripts.derived import precompute_profiler as profiler
from scripts.derived import precompute_level_touches as level_touches
from scripts.derived import precompute_range_dist as range_dist
from scripts.derived import precompute_hod_lod as hod_lod
from scripts.derived import precompute_daily_hod_lod as daily_hod
from scripts.derived import precompute_sessions as sessions
from scripts.derived import precompute_vwap as vwap
from scripts.data_processing import resample_parquet

def ensure_time_column(file_path):
    print(f">> Step 0: Ensuring Schema Compatibility for {file_path}...")
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
    elif df['time'].isna().any():
        print("  Found NaNs in 'time' column. Backfilling from Index...")
        fill_values = pd.Series(df.index.astype(int) // 10**9, index=df.index)
        df['time'] = df['time'].fillna(fill_values)
        df['time'] = df['time'].astype(int)
        dirty = True
        
    if dirty:
        data_utils.safe_save_parquet(df, str(file_path))
        print(f"  ✅ Schema updated and saved to {file_path}")
    else:
        print("  ✅ Schema is already compatible.")

def regenerate_all(ticker="ES1"):
    print(f"\n=== REGENERATING DATA FOR {ticker} ===\n")
    
    # Check for best available source
    source_1m = Path("data") / f"{ticker}_1m.parquet"
    source_5m = Path("data") / f"{ticker}_5m.parquet"
    
    best_tf = None
    best_source = None
    
    if source_1m.exists():
        best_tf = "1m"
        best_source = source_1m
    elif source_5m.exists():
        best_tf = "5m"
        best_source = source_5m
    
    if not best_source:
        print(f"  Error: No 1m or 5m source found for {ticker}. Aborting.")
        return

    print(f">> Using {best_tf} as primary source for analysis.")

    # 0. FIX SCHEMA
    ensure_time_column(best_source)
    
    # 1. UPSAMPLE
    print(f"\n>> Step 1: Upsampling Timeframes from {best_tf}...")
    resample_parquet.resample_and_save(best_source, best_tf, ticker)
    
    # 2. RUN ANALYSIS PROFILERS
    print(f"\n>> Step 2: Running Analysis Profilers for {ticker}...")
    
    print("  - Daily HOD/LOD (True Timing)...")
    if best_tf == "1m":
        try:
            results = daily_hod.compute_daily_hod_lod(ticker)
            output_path = Path("data") / f'{ticker}_daily_hod_lod.json'
            with open(output_path, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"    Saved {output_path}")
        except Exception as e:
            print(f"    Error in Daily HOD/LOD: {e}")
    else:
        print(f"    Skipping Daily HOD/LOD: Requires 1m source.")

    print(f"  - Daily Sessions (Profiler Core) using {best_tf}...")
    sessions.precompute_daily_sessions(ticker, timeframe=best_tf)
    
    print("  - Profiler Stats (Recomputing)...")
    profiler.precompute_ticker(ticker)
    
    print("  - Level Touches...")
    if best_tf == "1m":
        try:
            results = level_touches.compute_level_touches(ticker)
            output_path = Path("data") / f'{ticker}_level_touches.json'
            with open(output_path, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"    Saved {output_path}")
        except Exception as e:
            print(f"    Error in Level Touches: {e}")
    else:
        print(f"    Skipping Level Touches: Requires 1m source.")

    print("  - Range Distribution...")
    range_dist.precompute_range_distribution(ticker, timeframe=best_tf)
    
    print("  - Intraday HOD/LOD...")
    if best_tf == "1m":
        hod_lod.precompute_hod_lod(ticker)
    else:
        print(f"    Skipping Intraday HOD/LOD: Requires 1m source.")
    
    print(f"  - VWAP ({best_tf})...")
    vwap.precompute_vwap(ticker, best_tf)
    
    # 3. CHUNK FOR WEB
    print("\n>> Step 3: Generating Web JSON Chunks (Global)...")
    cmd = ["python", "scripts/data_processing/convert_to_chunked_json.py", ticker]
    subprocess.run(cmd, check=True)
    
    print(f"\n=== REGENERATION COMPLETE FOR {ticker} ===")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("ticker", nargs="?", default="ES1", help="Ticker to regenerate (default: ES1)")
    args = parser.parse_args()
    
    regenerate_all(args.ticker)
