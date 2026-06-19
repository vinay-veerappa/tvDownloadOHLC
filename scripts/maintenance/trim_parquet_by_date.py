import pandas as pd
from pathlib import Path

def trim_historical_to_2025():
    data_dir = Path("data")
    cutoff_date = pd.Timestamp("2025-12-31 23:59:59", tz=None)
    
    # Only get parquet files directly in data/ (not in subdirs like live/)
    parquet_files = [f for f in data_dir.iterdir() if f.is_file() and f.suffix == ".parquet"]
    
    print(f"Trimming {len(parquet_files)} historical parquet files to end of 2025...")
    
    trimmed_count = 0
    
    for path in parquet_files:
        try:
            df = pd.read_parquet(path)
            
            # Check if index is datetime
            if not pd.api.types.is_datetime64_any_dtype(df.index):
                # if there's a timestamp column, maybe use that?
                # but historical files use datetime index.
                continue
                
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
                
            original_len = len(df)
            df_clean = df[df.index <= cutoff_date]
            clean_len = len(df_clean)
            
            removed = original_len - clean_len
            if removed > 0:
                print(f"Trimming {path.name}: Removed {removed:,} rows (End date: {df_clean.index.max()})")
                df_clean.to_parquet(path)
                trimmed_count += 1
                
        except Exception as e:
            print(f"Error processing {path.name}: {e}")
            
    print(f"Done. Trimmed {trimmed_count} files.")

if __name__ == "__main__":
    trim_historical_to_2025()
