import pandas as pd
from pathlib import Path

data_dir = Path("data")
tickers = ["ES1", "NQ1"]

for ticker in tickers:
    file_path = data_dir / f"{ticker}_1m.parquet"
    if file_path.exists():
        df = pd.read_parquet(file_path)
        print(f"{ticker} 1m range: {df.index.min()} to {df.index.max()}")
        print(f"  Rows: {len(df)}")
    else:
        print(f"{ticker} 1m file not found!")
