import json
import os
from datetime import datetime
import pytz

DATA_FILE = r"c:\Users\vinay\tvDownloadOHLC\web\public\data\NQ1_1m\chunk_0.json"

def check_gap():
    if not os.path.exists(DATA_FILE):
        print("File not found")
        return

    with open(DATA_FILE, 'r') as f:
        data = json.load(f)

    est = pytz.timezone('America/New_York')
    base_count = 0
    gap_bars = []

    print(f"Total bars in chunk: {len(data)}")
    print(f"First bar: {data[0]['time']}")

    chunks_to_check = [4, 5]
    
    for c_idx in chunks_to_check:
        fpath = os.path.join(os.path.dirname(DATA_FILE), f"chunk_{c_idx}.json")
        if not os.path.exists(fpath):
            print(f"File not found: {fpath}")
            continue
        
        print(f"\n--- Checking Chunk {c_idx} ---")
        with open(fpath, 'r') as f:
            data = json.load(f)

        print(f"First Bar: {datetime.utcfromtimestamp(data[0]['time'] / (1000 if data[0]['time'] > 30000000000 else 1)).replace(tzinfo=pytz.utc).astimezone(est)}")
        print(f"Last Bar: {datetime.utcfromtimestamp(data[-1]['time'] / (1000 if data[-1]['time'] > 30000000000 else 1)).replace(tzinfo=pytz.utc).astimezone(est)}")
    
        print(f"Scanning {len(data)} bars for 17:00-18:00 EDT gap...")
        
        found_gap_samples = 0
        for i, bar in enumerate(data):
            ts = bar['time']
            if ts > 30000000000: ts = ts / 1000
            dt_utc = datetime.utcfromtimestamp(ts).replace(tzinfo=pytz.utc)
            dt_est = dt_utc.astimezone(est)
            
            # Strict Gap Check
            if dt_est.hour == 17:
                print(f"[{i}] GAP BAR FOUND! {ts} -> EST {dt_est}")
                found_gap_samples += 1
                if found_gap_samples > 5: break
        
        if found_gap_samples == 0:
            print("No bars found in 17:00-18:00 gap.")

if __name__ == "__main__":
    check_gap()
