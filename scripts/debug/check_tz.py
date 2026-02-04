
import pandas as pd
from pathlib import Path

path = Path("data/NQ1_1m.parquet")
if path.exists():
    df = pd.read_parquet(path)
    print(f"Index TZ: {df.index.tz}")
    print(f"Sample Index: {df.index[0]}")
    # Check if naive
    if df.index.tz is None:
        print("Date is Naive. Checking sample hour...")
        # If naive, is it UTC or EST?
        # NQ trading starts sunday 18:00 EST / 23:00 UTC (winter) or 22:00 UTC (summer).
        # Sample might tell us.
else:
    print("File not found")
