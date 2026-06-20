"""Quick parquet alignment check"""
import pyarrow.parquet as pq, pandas as pd, numpy as np, json
from pathlib import Path

PARQUET_PATH = r"c:\Users\vinay\tvDownloadOHLC\data\ES1_1m.parquet"
JSON_DIR = Path(r"c:\Users\vinay\tvDownloadOHLC\web\public\data\ES1_1m")

tbl = pq.read_table(PARQUET_PATH, columns=["time","open","high","low","close"])
df_full = tbl.to_pandas()
df_valid = df_full.dropna()
print(f"Parquet total rows: {len(df_full)}")
print(f"Parquet non-NaN rows: {len(df_valid)}")
print(f"Parquet time range: {df_valid.time.min():.0f} to {df_valid.time.max():.0f}")
print(f"NaN rows: {df_full.isnull().any(axis=1).sum()}")

for cname in ["chunk_0.json", "chunk_1.json", "chunk_338.json"]:
    fpath = JSON_DIR / cname
    if fpath.exists():
        with open(fpath) as f:
            chunk = json.load(f)
        t0, t1 = chunk[0]["time"], chunk[-1]["time"]
        print(f"\n{cname}: {len(chunk)} rows")
        print(f"  time: {t0} to {t1}")
        print(f"  from: {pd.Timestamp(t0, unit='s')} to {pd.Timestamp(t1, unit='s')}")
        match = ((df_full.time >= t0) & (df_full.time <= t1)).sum()
        print(f"  parquet rows in this time range: {match}")
