"""Check how much data SessionBoxEngine actually needs."""
import sys
from pathlib import Path
_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import time
import pandas as pd
import pyarrow.parquet as pq

path = _REPO / "data" / "live" / "live_storage_-NQ.parquet"

# Schema
pf = pq.ParquetFile(str(path))
schema = pf.schema_arrow
print("Schema:")
for f in schema:
    print(f"  {f.name}: {f.type}")

# Timestamp range
df_ts = pd.read_parquet(str(path), columns=["timestamp"])
print(f"\nRows: {len(df_ts)}")
print(f"First: {pd.to_datetime(df_ts['timestamp'].iloc[0], unit='s', utc=True)}")
print(f"Last:  {pd.to_datetime(df_ts['timestamp'].iloc[-1], unit='s', utc=True)}")

# How many rows in last 2 days?
import pandas as pd
cutoff = df_ts["timestamp"].iloc[-1] - pd.Timedelta(days=2)
recent = df_ts[df_ts["timestamp"] >= cutoff]
print(f"\nLast 2 days: {len(recent)} rows (~{len(recent)/60:.0f} hours)")

# How many rows in last 3 days?
cutoff3 = df_ts["timestamp"].iloc[-1] - pd.Timedelta(days=3)
recent3 = df_ts[df_ts["timestamp"] >= cutoff3]
print(f"Last 3 days: {len(recent3)} rows (~{len(recent3)/60:.0f} hours)")

# Benchmark: read full vs read with filter
print("\n--- Benchmark ---")

t0 = time.perf_counter()
df_full = pd.read_parquet(str(path))
t1 = time.perf_counter()
print(f"Full read: {(t1-t0)*1000:.0f} ms, {len(df_full)} rows")

# Read with pandas filter on timestamp
cutoff_val = df_ts["timestamp"].iloc[-1] - pd.Timedelta(days=3)
t0 = time.perf_counter()
df_filt = pd.read_parquet(str(path), filters=[("timestamp", ">=", cutoff_val)])
t1 = time.perf_counter()
print(f"Pandas filtered read (last 3d): {(t1-t0)*1000:.0f} ms, {len(df_filt)} rows")
