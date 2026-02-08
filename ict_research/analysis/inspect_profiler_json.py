import json
import pandas as pd
import os

profiler_path = r"c:\Users\vinay\tvDownloadOHLC\data\NQ1_profiler.json"
research_path = r"c:\Users\vinay\tvDownloadOHLC\ict_research\data\trading_days_enhanced_NQ.csv"

def inspect_data():
    # 1. Inspect Profiler JSON
    if os.path.exists(profiler_path):
        print(f"Loading {profiler_path}...")
        with open(profiler_path, 'r') as f:
            data = json.load(f)
            
        print(f"Total Records: {len(data)}")
        if len(data) > 0:
            print("\nSample Record Keys:")
            print(list(data[0].keys()))
            print("\nSample Record Values:")
            for k, v in data[-1].items(): # Look at a recent one
                print(f"  {k}: {v}")
    else:
        print("Profiler JSON not found.")

    # 2. Inspect Research CSV
    if os.path.exists(research_path):
        print(f"\nLoading {research_path}...")
        df = pd.read_csv(research_path, nrows=5)
        print("\nCSV Columns:")
        print(list(df.columns))
    else:
        print("Research CSV not found.")

if __name__ == "__main__":
    inspect_data()
