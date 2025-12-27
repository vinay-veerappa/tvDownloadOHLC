import pandas as pd
import data_utils
from pathlib import Path

def fix_schema(ticker="ES1"):
    path = Path(f"data/{ticker}_1m.parquet")
    print(f"Checking {path}...")
    
    df = pd.read_parquet(path)
    print(f"Columns: {df.columns.tolist()}")
    print(f"Index Name: {df.index.name}")
    
    # Check for duplicates
    if len(df.columns) != len(set(df.columns)):
        print("Duplicate columns detected!")
        # Remove duplicates, keeping the first
        df = df.loc[:, ~df.columns.duplicated()]
        print(f"Fixed Columns: {df.columns.tolist()}")
        
        # Ensure 'time' column is correct (Unix)
        if 'time' in df.columns:
            # Re-calculate to be safe
            if isinstance(df.index, pd.DatetimeIndex):
                df['time'] = df.index.astype(int) // 10**9
        
        data_utils.safe_save_parquet(df, str(path))
        print("Saved fixed file.")
    else:
        print("No duplicate columns found.")
        
        # Check index name conflict
        if df.index.name == 'time' and 'time' in df.columns:
            print("Index name conflict with column. Renaming index to 'datetime'.")
            df.index.name = 'datetime'
            data_utils.safe_save_parquet(df, str(path))
            print("Saved with renamed index.")

if __name__ == "__main__":
    fix_schema("ES1")
