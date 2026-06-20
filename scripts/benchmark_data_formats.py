"""
benchmark_data_formats.py
Compares data serving approaches for chunked OHLC history.
Run: $env:PYTHONIOENCODING='utf-8'; python scripts/benchmark_data_formats.py
"""
import os, sys, time, json, io
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pandas as pd
import numpy as np

# CONFIG
TICKER = "ES1"
TIMEFRAME = "1m"
PARQUET_PATH = Path(r"c:\Users\vinay\tvDownloadOHLC\data") / f"{TICKER}_{TIMEFRAME}.parquet"
JSON_CHUNK_DIR = Path(r"c:\Users\vinay\tvDownloadOHLC\web\public\data") / f"{TICKER}_1m"
CHUNK_INDEX = 1       # start chunk (going back in history; 1=second most recent)
CHUNKS_TO_LOAD = 1    # mirrors CHUNKS_PER_LOAD in use-data-loading.ts
CHUNK_SIZE = 20_000   # bars per chunk
REPEAT = 5

print(f"\n{'='*65}")
print(f"  OHLC Data Format Benchmark")
print(f"  {TICKER} {TIMEFRAME} | {CHUNKS_TO_LOAD} chunk x {CHUNK_SIZE:,} bars | {REPEAT} runs")
print(f"{'='*65}\n")

# Load parquet once (simulates server-side in-memory cache)
print("  Loading full parquet into memory (one-time cost)...")
t0 = time.perf_counter()
tbl_full = pq.read_table(PARQUET_PATH, columns=["time","open","high","low","close"])
parquet_load_ms = (time.perf_counter()-t0)*1000
total_rows = len(tbl_full)
print(f"  Parquet loaded: {total_rows:,} rows in {parquet_load_ms:.0f}ms\n")
print("  Running benchmarks...\n")


def run(fn, label):
    times, sz = [], 0
    for _ in range(REPEAT):
        t0 = time.perf_counter()
        payload = fn()
        times.append(time.perf_counter() - t0)
        sz = len(payload)
    ms = sorted(times)[REPEAT//2] * 1000
    return ms, sz


# Helper: get row range for chunk
def row_range():
    end = total_rows - (CHUNK_INDEX * CHUNK_SIZE)
    start = max(0, end - CHUNKS_TO_LOAD * CHUNK_SIZE)
    return start, end - start


# 1. Baseline: read existing JSON chunk files from disk (what Node.js does today)
def baseline_json_files():
    bars = []
    for i in range(CHUNK_INDEX, CHUNK_INDEX + CHUNKS_TO_LOAD):
        p = JSON_CHUNK_DIR / f"chunk_{i}.json"
        with open(p, "rb") as f:
            chunk = json.loads(f.read())
        bars.extend(chunk)
    return json.dumps(bars).encode()

# 2. Parquet slice -> JSON via pandas (fast vectorized)
def parquet_to_json():
    start, length = row_range()
    df = tbl_full.slice(start, length).to_pandas().dropna()
    df["time"] = df["time"].round().astype(np.int64)
    return df.to_json(orient="records").encode()

# 3. Parquet slice -> compact JSON (only 5 fields, no extra keys via numpy)
def parquet_to_json_compact():
    start, length = row_range()
    df = tbl_full.slice(start, length).to_pandas().dropna()
    df["time"] = df["time"].round().astype(np.int64)
    # Compact: array of arrays instead of objects  [[t,o,h,l,c], ...]
    data = df[["time","open","high","low","close"]].values.tolist()
    return json.dumps(data).encode()

# 4. Parquet slice -> raw float32 binary (smallest, fastest for browser Float32Array)
def parquet_to_float32():
    start, length = row_range()
    df = tbl_full.slice(start, length).to_pandas().dropna()
    arr = df[["time","open","high","low","close"]].values.astype(np.float32)
    return arr.tobytes()

# 5. Parquet slice -> float64 binary (double precision, same as JS Number)
def parquet_to_float64():
    start, length = row_range()
    df = tbl_full.slice(start, length).to_pandas().dropna()
    arr = df[["time","open","high","low","close"]].values.astype(np.float64)
    return arr.tobytes()

# 6. Arrow IPC (feather v2) - needs apache-arrow JS lib to decode
def parquet_to_arrow_ipc():
    start, length = row_range()
    slice_tbl = tbl_full.slice(start, length)
    buf = io.BytesIO()
    with pa.ipc.new_file(buf, slice_tbl.schema) as w:
        w.write_table(slice_tbl)
    return buf.getvalue()


results = []
results.append(("JSON chunk files (CURRENT - Node.js)",  *run(baseline_json_files, "baseline")))
results.append(("Parquet slice -> JSON objects",         *run(parquet_to_json, "parquet_json")))
results.append(("Parquet slice -> JSON arrays (compact)",*run(parquet_to_json_compact, "parquet_compact")))
results.append(("Parquet slice -> float32 binary",       *run(parquet_to_float32, "float32")))
results.append(("Parquet slice -> float64 binary",       *run(parquet_to_float64, "float64")))
results.append(("Parquet slice -> Arrow IPC",            *run(parquet_to_arrow_ipc, "arrow")))

baseline_ms, baseline_sz = results[0][1], results[0][2]

print(f"  {'Method':<42} {'Time':>8}  {'Size':>8}  {'Speedup':>8}  {'Size reduction'}")
print(f"  {'-'*42} {'-'*8}  {'-'*8}  {'-'*8}  {'-'*14}")
for label, ms, sz in results:
    speedup = baseline_ms / ms
    size_ratio = baseline_sz / sz
    marker = " <-- CURRENT" if "CURRENT" in label else ""
    print(f"  {label:<42} {ms:7.1f}ms  {sz/1024:6.0f}KB  {speedup:7.1f}x  {size_ratio:5.1f}x smaller{marker}")

best_alt = min(results[1:], key=lambda x: x[1])
print(f"\n  Fastest alternative: {best_alt[0]}")
print(f"  {baseline_ms:.0f}ms -> {best_alt[1]:.0f}ms ({baseline_ms/best_alt[1]:.1f}x faster)")
print(f"  {baseline_sz/1024:.0f}KB -> {best_alt[2]/1024:.0f}KB on the wire\n")

print(f"  NOTE: Parquet results assume data is cached in Python process memory.")
print(f"  First read from disk: {parquet_load_ms:.0f}ms for {total_rows:,} rows ({PARQUET_PATH.stat().st_size/1e6:.1f}MB)")
print(f"  Once warm, slicing is instant. The full parquet fits in RAM.\n")
print(f"  For the current JSON chunks:")
print(f"  Each chunk_N.json = ~2MB. Node reads from disk per request.")
print(f"  CHUNK_CACHE in data-actions.ts caches PARSED chunks (not raw bytes)")
print(f"  meaning JSON.parse() cost is amortized after first load,")
print(f"  but JSON.stringify() back to the client still happens every time.\n")
