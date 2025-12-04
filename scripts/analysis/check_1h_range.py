import pandas as pd
from pathlib import Path

data_dir = Path("data")
tickers = ["ES1", "NQ1"]
timeframes = ["1h"]

for ticker in tickers:
    for tf in timeframes:
        file_path = data_dir / f"{ticker}_{tf}.parquet"
        if file_path.exists():
            df = pd.read_parquet(file_path)
            print(f"{ticker} {tf} range: {df.index.min()} to {df.index.max()}")
            print(f"  Rows: {len(df)}")
