import pandas as pd
from pathlib import Path
import os

path = Path("data/GC1_1m.parquet")
print(f"File: {path}")
print(f"Size: {path.stat().st_size / (1024*1024):.2f} MB")

try:
    df = pd.read_parquet(path)
    print(f"Rows: {len(df)}")
    print(f"Columns: {df.columns.tolist()}")
    if not df.empty:
        print(f"Start: {df.index[0]}")
        print(f"End:   {df.index[-1]}")
        
    print("\nTail:")
    print(df.tail())
except Exception as e:
    print(f"Error reading: {e}")
