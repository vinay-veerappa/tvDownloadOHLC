
import pandas as pd
from pathlib import Path

files = [
    Path("data/NQ1_1m.parquet"),
    Path("data/live_storage_-NQ.parquet")
]

for f in files:
    print(f"\n--- {f.name} ---")
    if f.exists():
        try:
            df = pd.read_parquet(f)
            print("Columns:", df.columns.tolist())
            print("Index:", df.index.name or "RangeIndex")
            if not df.empty:
                print("First Row:", df.iloc[0].to_dict())
                print("Last Row:", df.iloc[-1].to_dict())
                print("Dtypes:\n", df.dtypes)
        except Exception as e:
            print(f"Error reading: {e}")
    else:
        print("File not found.")
