import pandas as pd
from pathlib import Path

tickers = ["CL1", "GC1", "RTY1", "YM1"]
for t in tickers:
    path = Path(f"data/{t}_5m.parquet")
    if path.exists():
        try:
            df = pd.read_parquet(path)
            print(f"{t}_5m: {len(df):,} rows")
        except:
            print(f"{t}_5m: Error reading")
    else:
        print(f"{t}_5m: Not found")
