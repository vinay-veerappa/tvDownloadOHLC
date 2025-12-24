
import pandas as pd
from pathlib import Path
import time
import shutil

def merge_live_to_historical(ticker="NQ1", live_symbol="-NQ"):
    """
    Merges live storage data (ms timestamps) into historical standard parquet (s timestamps).
    """
    data_dir = Path("data")
    hist_path = data_dir / f"{ticker}_1m.parquet"
    live_path = data_dir / f"live_storage_{live_symbol}.parquet"
    
    print(f"--- Merging {live_path.name} -> {hist_path.name} ---")
    
    if not hist_path.exists():
        print("Historical file not found.")
        return
        
    if not live_path.exists():
        print("Live file not found.")
        return

    # Backup
    backup_path = data_dir / "backup" / f"{ticker}_1m_pre_merge.parquet"
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(hist_path, backup_path)
    print(f"Backed up to {backup_path}")

    # Load
    df_hist = pd.read_parquet(hist_path)
    df_live = pd.read_parquet(live_path)
    
    print(f"Hist: {len(df_hist):,} rows, End: {df_hist['time'].max()}")
    print(f"Live: {len(df_live):,} rows, Start: {df_live['time'].min()}, End: {df_live['time'].max()}")

    # Normalize Live
    # Live is typically ms, Hist is seconds
    # Check live max to confirm
    if df_live['time'].max() > 3000000000: # > year 2065 in seconds, safely assumes ms
        df_live['time'] = df_live['time'] // 1000
    
    # Ensure columns match
    # Hist: ['open', 'high', 'low', 'close', 'volume', 'time']
    # Live: ['time', 'open', 'high', 'low', 'close', 'volume', 'timestamp']
    
    cols = ['time', 'open', 'high', 'low', 'close', 'volume']
    df_live = df_live[cols]
    
    # Filter live for new data
    last_hist_time = df_hist['time'].max()
    new_data = df_live[df_live['time'] > last_hist_time]
    
    print(f"New rows to add: {len(new_data):,}")
    
    if len(new_data) > 0:
        # Concat
        # Ensure Hist has same columns order
        df_hist = df_hist[cols]
        combined = pd.concat([df_hist, new_data])
        
        # Sort
        combined = combined.sort_values('time')
        
        # Drop duplicates just in case
        combined = combined.drop_duplicates(subset=['time'], keep='last')
        
        print(f"Combined: {len(combined):,} rows")
        
        # Save
        combined.to_parquet(hist_path)
        print("Saved successfully.")
        
        # Also need to trigger chunk update? 
        # For immediate fix, we rely on the user running regeneration later or we can run just the chunker.
        # But this script just fixes the parquet.
    else:
        print("No new data to merge.")

if __name__ == "__main__":
    merge_live_to_historical("NQ1", "-NQ")
    merge_live_to_historical("ES1", "-ES")
