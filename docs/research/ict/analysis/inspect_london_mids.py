import pandas as pd
import json
import os

def inspect_london_mids():
    csv_path = r"c:\Users\vinay\tvDownloadOHLC\ict_research\data\trading_days_enhanced_NQ.csv"
    json_path = r"c:\Users\vinay\tvDownloadOHLC\data\NQ1_profiler.json"
    
    print("--- Inspecting Research CSV ---")
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path, nrows=1)
        # Filter columns containing "London" or "Mid"
        cols = [c for c in df.columns if "London" in c or "Mid" in c]
        print(f"Relevant CSV Columns: {cols}")
    else:
        print("CSV not found.")
        
    print("\n--- Inspecting Profiler JSON ---")
    if os.path.exists(json_path):
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        # Find a London session record
        for row in data:
            if row.get('session') == 'London':
                print("London Session Keys:", row.keys())
                # Check if 'mid' is present
                if 'mid' in row:
                    print(f"Profiler has explicit 'mid': {row['mid']}")
                else:
                    print("Profiler implied mid = (range_high + range_low) / 2")
                break
    else:
        print("JSON not found.")

if __name__ == "__main__":
    inspect_london_mids()
