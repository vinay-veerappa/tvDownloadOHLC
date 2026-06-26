import os
import sys
import pandas as pd

# Ensure repository root is in sys.path
repo_root = os.path.abspath(".")
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from api.features.shared.data_loader import load_parquet

print("Calling load_parquet('NQ1', '1m')...")
df = load_parquet("NQ1", "1m")
if df is not None:
    print(f"Fused DataFrame length: {len(df)}")
    print(f"Columns: {list(df.columns)}")
    print("\nFirst 5 rows:")
    print(df.head(5))
    print("\nLast 15 rows:")
    print(df.tail(15))
    
    # Check if time column is float/int and sorted
    print(f"\nIs 'time' column monotonically increasing? {df['time'].is_monotonic_increasing}")
    print(f"Time type: {df['time'].dtype}")
    
    # Convert last few times to readable UTC times
    from datetime import datetime, timezone
    print("\nLast 10 times in UTC:")
    for t in df['time'].tail(10):
        print(f"Timestamp: {t}, UTC: {datetime.fromtimestamp(t, tz=timezone.utc)}")
else:
    print("load_parquet returned None.")
