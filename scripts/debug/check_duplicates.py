import pandas as pd
import glob
import os

def check_duplicates():
    files = glob.glob("data/*.parquet")
    for f in files:
        try:
            df = pd.read_parquet(f)
            # Check for duplicate indices or 'datetime' column
            if 'datetime' in df.columns:
                df = df.set_index('datetime')
            
            duplicates = df.index.duplicated()
            if duplicates.any():
                count = duplicates.sum()
                print(f"FAILED: {f} has {count} duplicate timestamps!")
                # Show first few
                print(df[duplicates].head())
            else:
                print(f"OK: {f} - {len(df)} rows, no duplicates.")
        except Exception as e:
            print(f"ERROR reading {f}: {e}")

if __name__ == "__main__":
    check_duplicates()
