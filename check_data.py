import pandas as pd
from pathlib import Path

data_dir = Path("data")
file_path = data_dir / "ES1_1m.parquet"

print(f"Checking {file_path}...")
if file_path.exists():
    df = pd.read_parquet(file_path)
    print(f"Rows: {len(df)}")
    if not df.empty and 'time' in df.columns:
        print(f"Start: {pd.to_datetime(df['time'].min(), unit='s')}")
        print(f"End:   {pd.to_datetime(df['time'].max(), unit='s')}")
    elif not df.empty:
         print("Columns:", df.columns)
else:
    print("File does not exist.")
