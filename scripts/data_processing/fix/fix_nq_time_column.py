import pandas as pd
from pathlib import Path
import data_utils

def fix_time_column():
    path = Path("data/NQ1_1m.parquet")
    print(f"Loading {path}...")
    df = pd.read_parquet(path)
    
    if 'time' not in df.columns:
        print("Time column missing entirely. Creating...")
        df['time'] = df.index.astype(int) // 10**9
    else:
        nan_count = df['time'].isna().sum()
        print(f"Found {nan_count} NaNs in 'time' column.")
        
        if nan_count > 0:
            print("Backfilling 'time' from Index...")
            # Fill NaNs
            # Must use pd.Series aligned by index to validly fill
            fill_values = pd.Series(df.index.astype(int) // 10**9, index=df.index)
            df['time'] = df['time'].fillna(fill_values)
            
            # Verify
            remaining_nans = df['time'].isna().sum()
            print(f"Remaining NaNs: {remaining_nans}")
            
            # Ensure int type
            df['time'] = df['time'].astype(int)
            
            print("Saving corrected parquet...")
            data_utils.safe_save_parquet(df, str(path))
            print("✅ Saved.")
        else:
            print("No NaNs found. File is already correct?")

if __name__ == "__main__":
    fix_time_column()
