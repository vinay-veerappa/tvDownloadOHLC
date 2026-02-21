
import json
import pandas as pd
import numpy as np
import sys
from pathlib import Path
from api.services.profiler_service import ProfilerService

def verify_value_to_value():
    ticker = "NQ1"
    
    # 1. Define Filter
    # Asia: Long True, Broken
    # London: Short
    filters = {"Asia": "Long True", "London": "Short"}
    broken_filters = {"Asia": "Broken"}
    
    print(f"--- QUERYING PROFILER SERVICE ---")
    print(f"Filters: {filters}")
    print(f"Broken: {broken_filters}")
    
    # Load all sessions for filtering
    stats_result = ProfilerService.analyze_profiler_stats(ticker, days=10000)
    all_sessions = stats_result['sessions']
    
    # Apply Filters via Service Logic
    matched_dates = ProfilerService.apply_filters(all_sessions, "NY1", filters, broken_filters)
    print(f"Matched Dates: {len(matched_dates)}")
    
    # 2. Get the "TRUTH" Price Model for these specific dates
    # We'll use the Daily target session (Asia Open anchor)
    print("\nCalculating Service Price Model (Filtered Subset)...")
    truth_model = ProfilerService.get_custom_price_model(ticker, "Daily", matched_dates, bucket_minutes=5)
    
    # 3. Get the "PINE" Price Model (Current LT Global)
    # This is what's in ProfilerData_Model_LT.pine
    from detailed_verification import extract_pine_model
    p_t, p_h, p_l = extract_pine_model("LT")
    
    # 4. Compare Values
    print("\n--- VALUE COMPARISON (HIGH PATH) ---")
    print(f"{'Minute':<10} | {'Service (Filtered)':<20} | {'Pine (Global LT)':<20} | {'Match?'}")
    print("-" * 75)
    
    # Map service model to dict for lookup
    s_map = {item['time_idx']: item['high'] for item in truth_model['median']}
    
    # Compare first 10 points
    for i in range(min(20, len(p_t))):
        t = p_t[i]
        p_val = p_h[i]
        s_val = s_map.get(t, "N/A")
        
        match = "YES" if s_val != "N/A" and abs(s_val - p_val) < 0.001 else "NO"
        if s_val == "N/A": 
            s_str = "N/A"
        else:
            s_str = f"{s_val:.4f}"
            
        print(f"{t:<10d} | {s_str:<20} | {p_val:<20.4f} | {match}")

if __name__ == "__main__":
    # Ensure we can import from the root
    sys.path.append(str(Path.cwd()))
    verify_value_to_value()
