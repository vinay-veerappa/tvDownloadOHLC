import json
import os
import sys

def load_chunk_simulated(ticker, timeframe, chunk_index):
    path = f"web/public/data/{ticker}_{timeframe}/chunk_{chunk_index}.json"
    print(f"Reading {path}...")
    try:
        with open(path, 'r') as f:
            data = json.load(f)
        print(f"  -> Success. Loaded {len(data)} bars.")
        return data
    except Exception as e:
        print(f"  -> FAILED: {e}")
        return None

def simulate_frontend_load(ticker):
    print(f"=== Simulating Frontend Load for {ticker} 1m ===")
    
    # 1. Load Meta
    meta_path = f"web/public/data/{ticker}_1m/meta.json"
    if not os.path.exists(meta_path):
        print("Meta file not found!")
        return
        
    with open(meta_path, 'r') as f:
        meta = json.load(f)
    print(f"Meta: {meta['totalBars']} bars, {meta['numChunks']} chunks.")
    
    # 2. Simulate Initial Load (Limit 0 -> 1 Chunk)
    print("\n[Step 1] Initial Load (Chunk 0)")
    chunk0 = load_chunk_simulated(ticker, "1m", 0)
    
    if chunk0:
        print(f"First Bar Time: {chunk0[0]['time']} (Date: {chunk0[0].get('date', 'N/A')})")
        print(f"Last Bar Time:  {chunk0[-1]['time']}")
        
        # Check integrity
        if chunk0[0]['time'] > chunk0[-1]['time']:
            print("ERROR: Chunk 0 is not sorted by time (Ascending)!")
        else:
            print("Chunk 0 is sorted correctly (Ascending).")
            
    # 3. Simulate Load More (Chunks 1..5)
    print("\n[Step 2] Load More (Chunks 1-5)")
    combined = []
    # Frontend logic: Loop chunks 1..5, push to array, then flatten Reverse
    loaded_chunks = []
    for i in range(1, 6):
        c = load_chunk_simulated(ticker, "1m", i)
        if c: loaded_chunks.append(c)
    
    # Validation: Combine
    # Frontend: for (let i = validChunks.length - 1; i >= 0; i--)
    # Here validChunks = [Chunk1, Chunk2, Chunk3, Chunk4, Chunk5]
    # Reverse loop -> Chunk5, Chunk4...
    
    stitch_res = []
    print("Stitching order check:")
    for i in range(len(loaded_chunks) - 1, -1, -1):
        c = loaded_chunks[i]
        print(f"  Appending Chunk {i+1} (Start: {c[0]['time']}, End: {c[-1]['time']})")
        stitch_res.extend(c)
        
    # Appending Chunk 0 (Newest)
    if chunk0:
        print(f"  Appending Chunk 0 (Start: {chunk0[0]['time']}, End: {chunk0[-1]['time']})")
        stitch_res.extend(chunk0)
        
    # Verify Continuity
    print("\nChecking Continuity of stitched data...")
    is_continuous = True
    for i in range(1, len(stitch_res)):
        prev = stitch_res[i-1]['time']
        curr = stitch_res[i]['time']
        if curr < prev:
            print(f"!! DISCONTINUITY DETECTED at index {i} !!")
            print(f"  Prev: {prev}, Curr: {curr}")
            is_continuous = False
            break
            
    if is_continuous:
        print("SUCCESS: Data is continuous.")
    else:
        print("FAIL: Data is NOT continuous.")

if __name__ == "__main__":
    simulate_frontend_load("ES1")
    simulate_frontend_load("NQ1")
