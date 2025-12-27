
import json
import os
import datetime
import pytz

def check_timestamps():
    base_dir = r"c:\Users\vinay\tvDownloadOHLC\web\public\data\NQ1_1m"
    target_date = datetime.date(2025, 11, 24)
    est = pytz.timezone('US/Eastern')
    
    # We know Nov 24 is in chunk_1 based on previous range dump
    fname = "chunk_1.json"
    fpath = os.path.join(base_dir, fname)
    
    print(f"Scanning {fname} for {target_date}...")
    
    if not os.path.exists(fpath):
        print(f"File {fpath} not found.")
        return

    with open(fpath, 'r') as f:
        data = json.load(f)

    found_count = 0
    for bar in data:
        ts = bar['time']
        dt_utc = datetime.datetime.fromtimestamp(ts, datetime.UTC)
        dt_est = dt_utc.astimezone(est)
        
        if dt_est.date() == target_date:
            found_count += 1
            should_print = False
            # Print first 5
            if found_count <= 5: should_print = True
            # Print around Gap (15:00 - 19:00 EST)
            if 11 <= dt_est.hour <= 14: should_print = True
            if 15 <= dt_est.hour <= 19: should_print = True
            # Print last 5? (Hard to know total ahead of time, let's just print gaps)
            
            if should_print:
                 print(f"Unix: {ts} | EST: {dt_est.time()} | Price: {bar['close']}")
                 
    print(f"Total bars for {target_date}: {found_count}")

if __name__ == "__main__":
    check_timestamps()
