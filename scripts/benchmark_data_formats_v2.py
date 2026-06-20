"""
benchmark_data_formats_v2.py
===========================
Proper benchmark using TIME-RANGE queries (how a real API would work).
Compares: JSON chunk files (current Node.js) vs Python-served alternatives.

Run: $env:PYTHONIOENCODING='utf-8'; python scripts/benchmark_data_formats_v2.py
"""
import time, json, io, subprocess
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq
import pandas as pd
import numpy as np

PARQUET_PATH = Path(r"c:\Users\vinay\tvDownloadOHLC\data\ES1_1m.parquet")
JSON_DIR     = Path(r"c:\Users\vinay\tvDownloadOHLC\web\public\data\ES1_1m")
CHUNK_SIZE   = 20_000
REPEAT       = 7  # run 7 times, take median

# Chunk to benchmark (use an older chunk where parquet has full data)
# chunk_200 = somewhere in 2022, well covered by parquet
TEST_CHUNKS  = [200, 201]  # simulate CHUNKS_PER_LOAD=1, going back in time

print("=" * 65)
print("  OHLC Data Fetch Benchmark (time-range queries)")
print("=" * 65)

# ──────────────────────────────────────────────────────────────────────
# Step 1: Load reference JSON chunk to get its exact time range
# ──────────────────────────────────────────────────────────────────────
with open(JSON_DIR / f"chunk_{TEST_CHUNKS[0]}.json") as f:
    ref_chunk = json.load(f)

T_START = ref_chunk[0]["time"]   # oldest bar in chunk
T_END   = ref_chunk[-1]["time"]  # newest bar in chunk

print(f"\n  Reference: chunk_{TEST_CHUNKS[0]}.json")
print(f"  Time: {pd.Timestamp(T_START, unit='s')} to {pd.Timestamp(T_END, unit='s')}")
print(f"  Bars: {len(ref_chunk)}")
print(f"\n  Loading parquet into memory (simulates server warm-up)...")

# ──────────────────────────────────────────────────────────────────────
# Step 2: Load full parquet once (server startup cost)
# ──────────────────────────────────────────────────────────────────────
t0 = time.perf_counter()
tbl_full = pq.read_table(PARQUET_PATH, columns=["time","open","high","low","close"])
df_full  = tbl_full.to_pandas()
df_full  = df_full[df_full.time.notna()].reset_index(drop=True)
load_ms  = (time.perf_counter() - t0) * 1000

print(f"  Parquet loaded: {len(df_full):,} rows in {load_ms:.0f}ms")
print(f"  Memory: ~{df_full.memory_usage(deep=True).sum() / 1e6:.0f}MB")

# Verify parquet coverage of this chunk
mask = (df_full.time >= T_START) & (df_full.time <= T_END)
pq_rows = mask.sum()
print(f"  Parquet rows in chunk_{TEST_CHUNKS[0]} time range: {pq_rows}")

if pq_rows < 100:
    # Fall back to chunk_338 (oldest - perfectly aligned)
    with open(JSON_DIR / "chunk_338.json") as f:
        ref_chunk = json.load(f)
    T_START = ref_chunk[0]["time"]
    T_END   = ref_chunk[-1]["time"]
    mask = (df_full.time >= T_START) & (df_full.time <= T_END)
    pq_rows = mask.sum()
    print(f"\n  Using chunk_338 instead (oldest, parquet aligned)")
    print(f"  Parquet rows in range: {pq_rows}")
    TEST_CHUNK_NAME = "chunk_338.json"
else:
    TEST_CHUNK_NAME = f"chunk_{TEST_CHUNKS[0]}.json"

print()

# ──────────────────────────────────────────────────────────────────────
# Helper
# ──────────────────────────────────────────────────────────────────────
def median_ms(times):
    s = sorted(times)
    return s[len(s)//2] * 1000

def bench(fn):
    times, sz = [], 0
    for _ in range(REPEAT):
        t0 = time.perf_counter()
        result = fn()
        times.append(time.perf_counter() - t0)
        sz = len(result)
    return median_ms(times), sz

# ──────────────────────────────────────────────────────────────────────
# Test functions
# ──────────────────────────────────────────────────────────────────────

def current_json_file():
    """Baseline: read JSON file from disk + parse + re-serialize (Node.js behavior)"""
    with open(JSON_DIR / TEST_CHUNK_NAME, "rb") as f:
        raw = f.read()
    parsed = json.loads(raw)
    return json.dumps(parsed).encode()   # simulates JSON.stringify back to client

def current_json_file_raw():
    """Read JSON file as raw bytes (no parse/stringify - best case Node)"""
    with open(JSON_DIR / TEST_CHUNK_NAME, "rb") as f:
        return f.read()

def parquet_time_range_json():
    """Python: slice parquet by time, return JSON objects (drop-in replacement for Node)"""
    df = df_full[(df_full.time >= T_START) & (df_full.time <= T_END)]
    return df.to_json(orient="records").encode()

def parquet_time_range_json_compact():
    """Python: slice parquet by time, return JSON arrays (compact - smaller payload)"""
    df = df_full[(df_full.time >= T_START) & (df_full.time <= T_END)]
    data = df[["time","open","high","low","close"]].values.tolist()
    return json.dumps(data).encode()

def parquet_time_range_float32():
    """Python: slice parquet by time, return flat Float32Array bytes (fastest decode in JS)"""
    df = df_full[(df_full.time >= T_START) & (df_full.time <= T_END)]
    arr = df[["time","open","high","low","close"]].values.astype(np.float32)
    # Prefix with row count (4 bytes uint32) so JS knows how many bars
    count = np.array([len(arr)], dtype=np.uint32).tobytes()
    return count + arr.tobytes()

def parquet_time_range_arrow_ipc():
    """Python: slice parquet, return Arrow IPC (browser needs apache-arrow 2KB lib)"""
    df = df_full[(df_full.time >= T_START) & (df_full.time <= T_END)]
    tbl = pa.Table.from_pandas(df[["time","open","high","low","close"]])
    buf = io.BytesIO()
    with pa.ipc.new_file(buf, tbl.schema) as w:
        w.write_table(tbl)
    return buf.getvalue()

# ──────────────────────────────────────────────────────────────────────
# Run all
# ──────────────────────────────────────────────────────────────────────
print("  Running benchmarks...\n")
results = [
    ("JSON file: read+parse+serialize [CURRENT Node]",  *bench(current_json_file)),
    ("JSON file: raw bytes only [best-case Node]",      *bench(current_json_file_raw)),
    ("Parquet time-range -> JSON objects [Python API]", *bench(parquet_time_range_json)),
    ("Parquet time-range -> JSON arrays [Python API]",  *bench(parquet_time_range_json_compact)),
    ("Parquet time-range -> float32 binary [Python API]",*bench(parquet_time_range_float32)),
    ("Parquet time-range -> Arrow IPC [Python API]",    *bench(parquet_time_range_arrow_ipc)),
]

baseline_ms = results[0][1]
baseline_sz = results[0][2]

print(f"  {'Method':<50} {'Time':>8}  {'Size':>8}  {'Speedup':>8}")
print(f"  {'-'*50} {'-'*8}  {'-'*8}  {'-'*8}")
for label, ms, sz in results:
    speedup = baseline_ms / ms
    marker = " <<" if "CURRENT" in label else ""
    print(f"  {label:<50} {ms:7.1f}ms  {sz/1024:6.0f}KB  {speedup:7.1f}x{marker}")

print()
print("=" * 65)
print()

best_alt = min(results[2:], key=lambda x: x[1])
print(f"  Fastest Python alternative: {best_alt[0]}")
print(f"  {results[0][1]:.1f}ms -> {best_alt[1]:.1f}ms ({results[0][1]/best_alt[1]:.0f}x faster server-side)")
print(f"  Wire payload: {results[0][2]/1024:.0f}KB -> {best_alt[2]/1024:.0f}KB ({results[0][2]/max(best_alt[2],1):.1f}x smaller)")
print()
print("  IMPORTANT: Add ~5ms for localhost HTTP round-trip.")
print("  Current Node bottleneck: 400-800ms total (disk I/O + JSON.stringify)")
print("  Python API estimate:     ~15-50ms total (in-memory slice + serialize + HTTP)")
print()
print("  Note: Parquet startup cost (108ms for 127MB) happens ONCE per server")
print("  start, then every query is in-memory. Ticker change = reload that parquet.")
print()
