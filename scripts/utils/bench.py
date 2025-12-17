import json
import time
from pathlib import Path

DATA_DIR = Path("web/public/data/NQ1_1m")

with open(DATA_DIR / "meta.json") as f:
    meta = json.load(f)

CHUNK_SIZE = 20000
BARS_PER_MONTH = 30000

print("NQ1 1m Loading Benchmark")
print("=" * 50)

for months in [4, 8, 12, 16, 20]:
    target_bars = months * BARS_PER_MONTH
    chunks_needed = (target_bars + CHUNK_SIZE - 1) // CHUNK_SIZE
    chunks_needed = min(chunks_needed, meta['numChunks'])
    
    start = time.time()
    data = []
    for i in range(chunks_needed):
        with open(DATA_DIR / f"chunk_{i}.json") as f:
            chunk = json.load(f)
        data.extend(chunk)
    elapsed = time.time() - start
    
    print(f"{months:2} months | {len(data):>9,} bars | {chunks_needed:2} chunks | {elapsed*1000:>6.0f} ms")
