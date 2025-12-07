"""
Benchmark data loading times for different amounts of 1m data.
Tests loading 4, 8, 12, 16, 20 months of NQ1 1m data.
"""
import json
import time
from pathlib import Path

DATA_DIR = Path("web/public/data/NQ1_1m")
CHUNK_SIZE = 20000  # bars per chunk

# Load metadata
with open(DATA_DIR / "meta.json") as f:
    meta = json.load(f)

print(f"NQ1 1m Data Stats:")
print(f"  Total bars: {meta['totalBars']:,}")
print(f"  Chunk size: {CHUNK_SIZE:,}")
print(f"  Num chunks: {meta['numChunks']}")
print()

# Calculate bars per month
# NQ1 trades ~23 hours/day, 5 days/week
# 23 * 60 = 1380 bars/day * 22 trading days/month = ~30,360 bars/month
BARS_PER_MONTH = 30000

def load_chunks(num_chunks):
    """Load specified number of chunks, return data and time taken."""
    start = time.time()
    data = []
    for i in range(min(num_chunks, meta['numChunks'])):
        chunk_path = DATA_DIR / f"chunk_{i}.json"
        with open(chunk_path) as f:
            chunk_data = json.load(f)
        if i == 0:
            data = chunk_data
        else:
            data = chunk_data + data  # Prepend older data
    elapsed = time.time() - start
    return data, elapsed

# Test different amounts
print(f"{'Months':<8} {'Bars':<12} {'Chunks':<8} {'Load Time':<12} {'MB':<8}")
print("-" * 52)

for months in [4, 8, 12, 16, 20]:
    target_bars = months * BARS_PER_MONTH
    chunks_needed = (target_bars + CHUNK_SIZE - 1) // CHUNK_SIZE
    
    # Run 3 times and average
    times = []
    data = []
    for _ in range(3):
        data, elapsed = load_chunks(chunks_needed)
        times.append(elapsed)
    
    avg_time = sum(times) / len(times)
    
    # Calculate data size in memory (rough estimate)
    size_mb = (len(data) * 5 * 8) / (1024 * 1024)  # 5 fields, 8 bytes each
    
    print(f"{months:<8} {len(data):<12,} {chunks_needed:<8} {avg_time*1000:<12.0f}ms {size_mb:<8.1f}")

print()
print("Note: Times are for reading JSON from disk. In browser, data is sent over network which is similar or faster.")
