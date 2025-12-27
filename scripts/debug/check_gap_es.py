import json
import os
import datetime
import pytz

# Config
DATA_DIR = "C:/Users/vinay/tvDownloadOHLC/web/public/data"
TICKERS = ["ES1", "YM1"]
# 17:00 EST is 22:00 UTC (Standard) or 21:00 UTC (DST)
# 18:00 EST is 23:00 UTC (Standard) or 22:00 UTC (DST)
# We will look for any bars where the time represents 17:MM EST.

def check_ticker(ticker):
    print(f"--- Checking {ticker} ---")
    folder_path = os.path.join(DATA_DIR, f"{ticker}_1m")
    
    if not os.path.exists(folder_path):
        print(f"Folder not found: {folder_path}")
        return

    files = sorted([f for f in os.listdir(folder_path) if f.endswith(".json")])
    
    gap_bars_count = 0
    
    for filename in files:
        filepath = os.path.join(folder_path, filename)
        with open(filepath, "r") as f:
            data = json.load(f)
            
        if isinstance(data, list) and len(data) > 0 and isinstance(data[0], list):
             # It's a list of lists [time, open, high, low, close...]
             # 0: time, 1: open, 2: high, 3: low, 4: close
             for bar in data:
                 ts = bar[0]
                 dt_utc = datetime.datetime.fromtimestamp(ts, pytz.utc)
                 dt_ny = dt_utc.astimezone(pytz.timezone('America/New_York'))
                 
                 # Check if hour is 17 (5 PM)
                 if dt_ny.hour == 17:
                     gap_bars_count += 1
                     if gap_bars_count <= 5: # Print first 5 only
                         print(f"GAP DATA FOUND: Unix={ts} | UTC={dt_utc} | NY={dt_ny} | Price={bar[4]}")
        else:
             # It's a list of objects
            for bar in data:
                ts = bar['time']
                dt_utc = datetime.datetime.fromtimestamp(ts, pytz.utc)
                dt_ny = dt_utc.astimezone(pytz.timezone('America/New_York'))
                
                # Check if hour is 17 (5 PM)
                if dt_ny.hour == 17:
                    gap_bars_count += 1
                    if gap_bars_count <= 5: # Print first 5 only
                        print(f"GAP DATA FOUND: Unix={ts} | UTC={dt_utc} | NY={dt_ny} | Price={bar.get('close', 'N/A')}")
                    
    print(f"Total bars found in 17:00-18:00 EST gap for {ticker}: {gap_bars_count}")

if __name__ == "__main__":
    for t in TICKERS:
        check_ticker(t)
