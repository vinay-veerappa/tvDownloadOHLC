import json
import os
import datetime
import pytz

# Config
DATA_DIR = "C:/Users/vinay/tvDownloadOHLC/web/public/data"
TICKERS = ["ES1", "YM1"]

def repair_ticker(ticker):
    print(f"--- Repairing {ticker} ---")
    folder_path = os.path.join(DATA_DIR, f"{ticker}_1m")
    
    if not os.path.exists(folder_path):
        print(f"Folder not found: {folder_path}")
        return

    files = sorted([f for f in os.listdir(folder_path) if f.endswith(".json")])
    total_removed = 0
    files_modified = 0

    for filename in files:
        filepath = os.path.join(folder_path, filename)
        
        with open(filepath, "r") as f:
            data = json.load(f)
        
        original_count = len(data)
        new_data = []
        modified = False

        if isinstance(data, list) and len(data) > 0 and isinstance(data[0], list):
             # List format [time, o, h, l, c]
             for bar in data:
                 ts = bar[0]
                 dt_utc = datetime.datetime.fromtimestamp(ts, pytz.utc)
                 dt_ny = dt_utc.astimezone(pytz.timezone('America/New_York'))
                 if dt_ny.hour == 17:
                     modified = True
                 else:
                     new_data.append(bar)
        else:
             # Object format {time: ...}
             for bar in data:
                 # Check if bar is a dict or a list (handle mixed formats if mostly one type)
                 if isinstance(bar, dict):
                     ts = bar.get('time')
                 elif isinstance(bar, list):
                     ts = bar[0]
                 else:
                     continue # Skip unknown

                 if ts is None: continue

                 dt_utc = datetime.datetime.fromtimestamp(ts, pytz.utc)
                 dt_ny = dt_utc.astimezone(pytz.timezone('America/New_York'))
                 if dt_ny.hour == 17:
                     modified = True
                 else:
                     new_data.append(bar)

        if modified:
            removed_count = original_count - len(new_data)
            total_removed += removed_count
            files_modified += 1
            print(f"  Fixed {filename}: Removed {removed_count} bars.")
            
            with open(filepath, "w") as f:
                json.dump(new_data, f) # No indent to keep compact

    print(f"Done. Removed {total_removed} bad bars across {files_modified} files for {ticker}.")

if __name__ == "__main__":
    for t in TICKERS:
        repair_ticker(t)
