import pandas as pd
from pathlib import Path

# The parquets that were mistakenly appended to
files_to_fix = [
    "data/YM1_1m.parquet",
    "data/ES1_1m.parquet",
    "data/NQ1_1m.parquet",
    "data/RTY1_1m.parquet",
    "data/GC1_1m.parquet",
    "data/CL1_1m.parquet"
]

def revert_erroneous_merge():
    print("Reverting mistakenly merged 1m data (April 12 - May 1)...")
    
    # We know the original data ended around Jan 2026, 
    # and the mistaken merge started on April 12, 2026.
    # We will remove any rows on or after April 1, 2026 to be safe.
    cutoff_date = pd.Timestamp("2026-04-01", tz=None)
    
    for file_path in files_to_fix:
        path = Path(file_path)
        if not path.exists():
            print(f"Skipping {file_path}, not found.")
            continue
            
        print(f"\nProcessing {file_path}...")
        df = pd.read_parquet(path)
        
        # Ensure the index is tz-naive for comparison, like convert_all_csv does
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
            
        original_len = len(df)
        
        # Keep only data before the cutoff
        df_clean = df[df.index < cutoff_date]
        clean_len = len(df_clean)
        
        removed = original_len - clean_len
        print(f"  Rows before: {original_len:,}")
        print(f"  Rows removed: {removed:,}")
        print(f"  Rows after:  {clean_len:,}")
        print(f"  New End Date: {df_clean.index.max()}")
        
        if removed > 0:
            df_clean.to_parquet(path)
            print("  Successfully reverted and saved!")
        else:
            print("  No rows removed (already clean).")

if __name__ == "__main__":
    revert_erroneous_merge()
