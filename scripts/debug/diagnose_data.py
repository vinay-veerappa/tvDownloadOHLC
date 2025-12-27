import os
import json
import glob

DATA_DIR = r"c:\Users\vinay\tvDownloadOHLC\web\public\data"

def check_ticker(ticker, timeframe="1m"):
    dir_path = os.path.join(DATA_DIR, f"{ticker}_{timeframe}")
    meta_path = os.path.join(dir_path, "meta.json")
    
    print(f"--- Checking {ticker} {timeframe} ---")
    
    if not os.path.exists(dir_path):
        print(f"Directory not found: {dir_path}")
        return

    if not os.path.exists(meta_path):
        print(f"Meta file not found: {meta_path}")
        return

    try:
        with open(meta_path, 'r') as f:
            meta = json.load(f)
    except Exception as e:
        print(f"Error reading meta.json: {e}")
        return

    # Check meta gaps
    chunks = sorted(meta['chunks'], key=lambda x: x['startTime'])
    
    print(f"Found {len(chunks)} chunks in meta.")
    
    gaps = []
    overlaps = []
    
    expected_interval = 60 if timeframe == "1m" else 300 # Simple check
    
    for i in range(len(chunks) - 1):
        curr_chunk = chunks[i]
        next_chunk = chunks[i+1]
        
        diff = next_chunk['startTime'] - curr_chunk['endTime']
        
        # In OHLC, endTime of one chunk might be same as startTime of next if inclusive/exclusive?
        # Usually chunk N ends at T, chunk N+1 starts at T+Interval.
        # Let's verify standard gap.
        
        # If diff > expected_interval * 10 (allow some weekend gaps without flagging EVERYTHING)
        # We are looking for "corruption" which might be huge overlaps or weird gaps.
        
        if diff < 0:
            overlaps.append((i, diff))
        # Ignore normal gaps for now, focus on weirdness
    
    if overlaps:
        print(f"!! Found {len(overlaps)} overlaps (e.g. chunk start < prev chunk end). This indicates bad stitching.")
        for idx, overlap in overlaps[:5]:
             print(f"   Chunk {idx} vs {idx+1}: overlap {overlap}s")
    else:
        print("No meta-level overlaps found.")

    
    # Deep Scan: Check content of chunks
    print("Beginning Deep Scan (checking internal timestamps and prices)...")
    
    total_bars = 0
    bad_chunks = 0
    
    for i, chunk_meta in enumerate(chunks):
        chunk_file = os.path.join(dir_path, f"chunk_{chunk_meta['index']}.json")
        try:
            with open(chunk_file, 'r') as f:
                data = json.load(f)
                
            if not data:
                print(f"   [!] Chunk {chunk_meta['index']} is empty")
                bad_chunks += 1
                continue
                
            total_bars += len(data)
            
            # Check for backward timestamps or dupe times
            prev_time = -1
            chunk_min_time = float('inf')
            chunk_max_time = float('-inf')
            
            internal_errors = 0
            
            for j, bar in enumerate(data):
                t = bar.get('time')
                
                # Check Price Validity
                if bar.get('high', 0) < bar.get('low', 0):
                     if internal_errors < 3: print(f"   [!] Chunk {chunk_meta['index']} Bar {j}: High {bar.get('high')} < Low {bar.get('low')}")
                     internal_errors += 1
                
                if bar.get('close') == 0:
                     if internal_errors < 3: print(f"   [!] Chunk {chunk_meta['index']} Bar {j}: Zero Price")
                     internal_errors += 1

                # Check Time Validity
                if t is None:
                    if internal_errors < 3: print(f"   [!] Chunk {chunk_meta['index']} Bar {j}: No Time")
                    internal_errors += 1
                    continue
                    
                if t <= prev_time:
                    if internal_errors < 3: print(f"   [!] Chunk {chunk_meta['index']} Bar {j}: Time backward/duplicate. Curr: {t}, Prev: {prev_time}")
                    internal_errors += 1
                
                prev_time = t
                chunk_min_time = min(chunk_min_time, t)
                chunk_max_time = max(chunk_max_time, t)

            # Cross check meta
            if chunk_min_time != chunk_meta['startTime']:
                 print(f"   [!] Chunk {chunk_meta['index']} Start Mismatch. Meta: {chunk_meta['startTime']}, Data: {chunk_min_time}")
                 internal_errors += 1
            
            if chunk_max_time != chunk_meta['endTime']:
                 print(f"   [!] Chunk {chunk_meta['index']} End Mismatch. Meta: {chunk_meta['endTime']}, Data: {chunk_max_time}")
                 internal_errors += 1

            if internal_errors > 0:
                print(f"   Chunk {chunk_meta['index']} has {internal_errors} errors.")
                bad_chunks += 1
                
        except Exception as e:
            print(f"   [!] Error reading chunk {chunk_meta['index']}: {e}")
            bad_chunks += 1

    print(f"Deep Scan Complete. Scanned {total_bars} bars. Found {bad_chunks} bad chunks.")

if __name__ == "__main__":
    check_ticker("ES1")
    check_ticker("NQ1")
    check_ticker("RTY1")
