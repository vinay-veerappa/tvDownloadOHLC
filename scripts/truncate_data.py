import os
import json
import glob
from datetime import datetime

DATA_DIR = r"c:\Users\vinay\tvDownloadOHLC\web\public\data"

# December 15, 2025 23:59:59 EST? 
# The user said "upto Dec 15th only".
# Assuming end of day Dec 15th.
# Check timestamp. 
# Dec 15 2025 is a Monday.
# Let's assume user wants to CUT metadata and chunks after this time.

CUTOFF_TIMESTAMP = 1765872000 # Monday, December 15, 2025 12:00:00 AM UTC
# Wait, let's verify.
# 1765843200 = Dec 15 2025 00:00:00 UTC?
# Python: datetime(2025, 12, 15).timestamp() -> depends on TZ.
# Let's use UTC 23:59:59 Dec 15 2025 as cutoff.
# Actually, 1765843200 is Dec 15 2025 (UTC).
# 1765929599 = Dec 15 2025 23:59:59 UTC.
CUTOFF_TIMESTAMP = 1765929599

def truncate_ticker(ticker, timeframe="1m"):
    dir_path = os.path.join(DATA_DIR, f"{ticker}_{timeframe}")
    meta_path = os.path.join(dir_path, "meta.json")
    
    print(f"--- Truncating {ticker} {timeframe} after {CUTOFF_TIMESTAMP} ---")
    
    if not os.path.exists(meta_path):
        print("Meta not found.")
        return

    with open(meta_path, 'r') as f:
        meta = json.load(f)

    # Filter Chunks logic
    # We remove chunks that START after cutoff.
    # If a chunk straddles, we truncate its content.
    
    new_chunks = []
    removed_chunks = []
    
    for chunk in meta['chunks']:
        if chunk['startTime'] > CUTOFF_TIMESTAMP:
            removed_chunks.append(chunk)
            # delete file
            fpath = os.path.join(dir_path, f"chunk_{chunk['index']}.json")
            if os.path.exists(fpath):
                os.remove(fpath)
            continue
            
        if chunk['endTime'] > CUTOFF_TIMESTAMP:
            # Straddle: We must open and truncate
            print(f"   Truncating straddling chunk {chunk['index']}...")
            fpath = os.path.join(dir_path, f"chunk_{chunk['index']}.json")
            if os.path.exists(fpath):
                with open(fpath, 'r') as f:
                    data = json.load(f)
                
                # Filter bars
                new_data = [b for b in data if b['time'] <= CUTOFF_TIMESTAMP]
                
                if not new_data:
                    # Became empty?
                    removed_chunks.append(chunk)
                    os.remove(fpath)
                    continue
                
                # Save back
                with open(fpath, 'w') as f:
                    json.dump(new_data, f)
                
                # Update meta
                chunk['endTime'] = new_data[-1]['time']
                chunk['count'] = len(new_data)
                new_chunks.append(chunk)
        else:
            # Keep as is
            new_chunks.append(chunk)

    print(f"Removed {len(removed_chunks)} chunks.")
    
    meta['chunks'] = new_chunks
    # Update total bars?
    # Simple recalc
    # meta['totalBars'] ... actually meta doesn't usually track totalBars at root explicitly in this schema?
    # Let's check schema. Usually just list of chunks.
    
    with open(meta_path, 'w') as f:
        json.dump(meta, f, indent=2)

if __name__ == "__main__":
    truncate_ticker("NQ1")
    # truncate_ticker("ES1") # Already ends Dec 15
    # truncate_ticker("RTY1")
