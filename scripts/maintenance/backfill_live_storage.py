import os
import sys
import pandas as pd
from datetime import datetime
import argparse

# Ensure we can import data_utils from local dir
# Assuming this script is in scripts/maintenance/
current_dir = os.path.dirname(os.path.abspath(__file__))
utils_dir = os.path.abspath(os.path.join(current_dir, "../utils"))
sys.path.append(utils_dir)

import data_utils
from data_utils import DATA_DIR

# Live storage is in data/live/
LIVE_DIR = os.path.join(DATA_DIR, "live")
os.makedirs(LIVE_DIR, exist_ok=True)

# Map App Ticker -> Schwab Ticker
SCHWAB_MAP = {
    "NQ1": "/NQ",
    "ES1": "/ES",
    "YM1": "/YM",
    "RTY1": "/RTY",
    "CL1": "/CL",
    "GC1": "/GC"
}

def backfill_live(ticker):
    schwab_ticker = SCHWAB_MAP.get(ticker, ticker)
    
    # Determined Safe Symbol for Filename: /NQ -> -NQ
    safe_symbol = schwab_ticker.replace("/", "-")
    filename = f"live_storage_{safe_symbol}.parquet"
    filepath = os.path.join(LIVE_DIR, filename)
    
    # User Request: Source from Historical Parquet (Jan 1 2025 -> Present)
    # This bypasses Schwab API limits for >45 day old data.
    
    # 1. Load Historical File
    hist_file = os.path.join(DATA_DIR, f"{ticker}_1m.parquet")
    if not os.path.exists(hist_file):
        print(f"Error: Historical file {hist_file} not found.")
        return

    print(f"Loading historical source: {hist_file}...")
    df_hist = pd.read_parquet(hist_file)
    
    # 2. Filter for Range (Jan 1 2025 -> Now)
    # Historical 'time' is in SECONDS (Unix Timestamp)
    start_ts_sec = int(datetime(2025, 1, 1).timestamp())
    
    if 'time' not in df_hist.columns:
        # Fallback if time is index
        df_hist = df_hist.reset_index()
        if 'time' not in df_hist.columns and 'datetime' in df_hist.columns:
             df_hist['time'] = df_hist['datetime'].astype('int64') // 10**9
    
    df_subset = df_hist[df_hist['time'] >= start_ts_sec].copy()
    print(f"  Filtered {len(df_subset)} rows from Jan 1, 2025.")

    # 3. Convert to Live Format (Milliseconds)
    # Live storage expects 'time' in ms. Historical is s.
    df_subset['time'] = df_subset['time'] * 1000
    
    # Ensure columns match live format
    cols = ['time', 'open', 'high', 'low', 'close', 'volume']
    # Live often lacks volume or has it as 0, but we have it, so keep it.
    df_subset = df_subset[cols]

    # 4. Merge with existing Live Storage?
    # User said "copy data from that into live storage".
    # Since historical is now "up to date" (we ran fetch_schwab_data earlier today),
    # this subset effectively covers everything we need.
    # We can just overwrite.
    
    combined = df_subset.sort_values('time')

    # Save
    try:
        combined.to_parquet(filepath, index=False)
        print(f"Successfully backfilled {filename} from local history.")
        print(f"   Total rows: {len(combined)}")
        print(f"   Range: {pd.to_datetime(combined['time'].min(), unit='ms')} -> {pd.to_datetime(combined['time'].max(), unit='ms')}")
    except Exception as e:
        print(f"Save Failed: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("ticker", help="Ticker (e.g. NQ1)")
    args = parser.parse_args()
    
    backfill_live(args.ticker)
