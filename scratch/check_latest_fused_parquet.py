import os
import pandas as pd
from datetime import datetime, timezone

path = os.path.join("data", "live", "live_storage_-NQ.parquet")
print(f"Reading live parquet: {path}")
if os.path.exists(path):
    df = pd.read_parquet(path)
    df = df.sort_values('time')
    print(f"Total rows: {len(df)}")
    print("\nLast 15 rows in live storage:")
    for idx, row in df.tail(15).iterrows():
        t = row['time']
        dt = datetime.fromtimestamp(t / 1000, tz=timezone.utc)
        print(f"Time: {t}, UTC: {dt}, O: {row['open']}, H: {row['high']}, L: {row['low']}, C: {row['close']}")
else:
    print("File not found.")
