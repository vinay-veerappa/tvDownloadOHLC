
import pandas as pd
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

# Import logic from service (or duplicate for standalone script if imports are tricky)
# To avoid import issues with relative paths in scripts, we'll setup path
import sys
import os
sys.path.append(os.getcwd())

from api.services.profiler_service import ProfilerService

def precompute_ticker(ticker="NQ1"):
    print(f"Loading data for {ticker}...")
    
    # Force load locally to bypass API context if needed, but Service has logic
    # We can use the service logic but passing a large 'days' count to cover all history
    # Or better: refactor service to exposure "process_dataframe"
    
    # For now, let's use the Service but with a hack to get ALL data.
    # The service takes "days". Let's pass 10000 days.
    
    print("Running analysis (this may take a minute)...")
    start = time.time()
    
    # Note: ensure api.services.data_loader DATA_DIR is correct relative to CWD
    result = ProfilerService.analyze_profiler_stats(ticker, days=10000)
    
    if "error" in result:
        print(f"Error: {result['error']}")
        return

    sessions = result["sessions"]
    count = len(sessions)
    elapsed = time.time() - start
    
    print(f"Analyzed {count} sessions in {elapsed:.2f}s")
    
    # Enrich with Daily Data (High/Low/Open) from NQ1_daily_hod_lod.json
    try:
        daily_json_path = Path(f"data/{ticker}_daily_hod_lod.json")
        if daily_json_path.exists():
            with open(daily_json_path) as f:
                daily_data = json.load(f)
            
            enrich_count = 0
            for s in sessions:
                d = s.get('date')
                if d and d in daily_data:
                    day_info = daily_data[d]
                    s['daily_open'] = day_info.get('daily_open')
                    s['daily_high'] = day_info.get('daily_high')
                    s['daily_low'] = day_info.get('daily_low')
                    enrich_count += 1
            print(f"Enriched {enrich_count} sessions with daily stats.")
        else:
            print(f"Warning: {daily_json_path} not found. Skipping enrichment.")
    except Exception as e:
        print(f"Enrichment Error: {e}")

    # Save to JSON
    output_file = Path(f"data/{ticker}_profiler.json")
    with open(output_file, "w") as f:
        json.dump(sessions, f, indent=2)
        
    print(f"Saved to {output_file}")

if __name__ == "__main__":
    precompute_ticker("NQ1")
