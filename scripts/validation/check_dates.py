import pandas as pd
from pathlib import Path

data_dir = Path("data")
tickers = ["ES1", "NQ1"]
tfs = ["1m", "5m", "15m", "1h", "4h", "1D", "1W"]

for ticker in tickers:
    print(f"{ticker}:")
    for tf in tfs:
        f = data_dir / f"{ticker}_{tf}.parquet"
        if f.exists():
            df = pd.read_parquet(f)
            print(f"  {tf:4s}: {df.index.min()} to {df.index.max()}")
    print()
