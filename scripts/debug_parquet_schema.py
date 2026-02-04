import pandas as pd
import os

path = r"c:\Users\vinay\tvDownloadOHLC\data\NQ1_5m.parquet"

try:
    df = pd.read_parquet(path)
    print("--- Columns ---")
    print(df.columns.tolist())
    print("\n--- Index Name ---")
    print(df.index.name)
    print("\n--- First 2 Rows ---")
    print(df.head(2))
except Exception as e:
    print(f"Error reading {path}: {e}")
