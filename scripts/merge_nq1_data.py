"""
Merge new TradingView CSV data with existing NQ1 parquet files.
Extends data from Nov 27 to Dec 5, 2025.
"""
import pandas as pd
from pathlib import Path

data_dir = Path("data")
csv_dir = Path("data/TV_OHLC")

# Mapping of CSV files to timeframes
csv_files = {
    "CME_MINI_NQ1!, 1_e0c08.csv": "1m",
    "CME_MINI_NQ1!, 5_f992d.csv": "5m", 
    "CME_MINI_NQ1!, 15_6da21.csv": "15m",
    "CME_MINI_NQ1!, 60_3aff7.csv": "1h",
    "CME_MINI_NQ1!, 240_1c692.csv": "4h",
}

for csv_name, timeframe in csv_files.items():
    csv_path = csv_dir / csv_name
    parquet_path = data_dir / f"NQ1_{timeframe}.parquet"
    
    print(f"\n=== Processing NQ1_{timeframe} ===")
    
    if not csv_path.exists():
        print(f"  CSV not found: {csv_name}")
        continue
    
    # Load existing parquet
    if parquet_path.exists():
        existing = pd.read_parquet(parquet_path)
        existing_end = existing.index.max()
        print(f"  Existing: {existing.index.min()} to {existing_end} ({len(existing):,} bars)")
    else:
        existing = pd.DataFrame()
        existing_end = pd.Timestamp.min
        print(f"  No existing parquet")
    
    # Load new CSV (TradingView format with Unix timestamps)
    new_df = pd.read_csv(csv_path)
    new_df.columns = [c.lower() for c in new_df.columns]
    new_df["datetime"] = pd.to_datetime(new_df["time"], unit="s")
    new_df = new_df.set_index("datetime")
    new_df = new_df[["open", "high", "low", "close", "volume"]]
    new_df = new_df.sort_index()
    
    print(f"  New CSV: {new_df.index.min()} to {new_df.index.max()} ({len(new_df):,} bars)")
    
    # Filter new data for rows after existing end date
    if not existing.empty:
        new_rows = new_df[new_df.index > existing_end]
        print(f"  New rows after {existing_end}: {len(new_rows):,}")
        
        if len(new_rows) > 0:
            # Combine
            combined = pd.concat([existing, new_rows])
            combined = combined[~combined.index.duplicated(keep="last")]
            combined = combined.sort_index()
        else:
            combined = existing
    else:
        combined = new_df
    
    print(f"  Combined: {combined.index.min()} to {combined.index.max()} ({len(combined):,} bars)")
    
    # Save
    combined.to_parquet(parquet_path)
    print(f"  Saved to {parquet_path}")

print("\n=== Done! ===")
