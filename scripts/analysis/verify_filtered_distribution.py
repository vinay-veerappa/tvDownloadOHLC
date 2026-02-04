
import pandas as pd
import json
import numpy as np

# Config
PROFILER_JSON = "data/NQ1_profiler.json"
UNADJUSTED_JSON = "data/NQ1_daily_hod_lod_unadjusted.json"
FILTER_DESC = "Asia(LF+Broken) -> London(LT) -> NY1(LT)"

def get_bucket(val):
    import math
    if pd.isna(val): return 0.0
    val_clamped = max(-5.0, min(5.0, val))
    # Round magnitude down to nearest 0.1
    mag = abs(val_clamped)
    b = math.floor(mag * 10) / 10.0
    return b if b < 5.0 else 5.0

def run_filtered_analysis():
    print(f"Applying Filter: {FILTER_DESC}")
    
    # 1. Load Profiler Data
    with open(PROFILER_JSON, 'r') as f:
        pro_data = json.load(f)
        
    # Group by Date
    sessions_by_date = {}
    for sess in pro_data:
        d = sess['date']
        if d not in sessions_by_date:
            sessions_by_date[d] = {}
        sessions_by_date[d][sess['session']] = sess
        
    filtered_dates = []
    
    for d, sessions in sessions_by_date.items():
        asia = sessions.get('Asia')
        london = sessions.get('London')
        ny1 = sessions.get('NY1')
        
        if not (asia and london and ny1):
            continue
            
        # Check Filters
        # Asia: Long False AND Broken
        pass_asia = (asia['status'] == "Long False" and asia['broken'] is True)
        
        # London: Long True
        pass_london = (london['status'] == "Long True")
        
        # NY1: Long True
        pass_ny1 = (ny1['status'] == "Long True")
        
        if pass_asia and pass_london and pass_ny1:
            filtered_dates.append(d)
            
    print(f"Matched Dates: {len(filtered_dates)}")
    if len(filtered_dates) == 0:
        return

    # 2. Load Unadjusted Price Data
    with open(UNADJUSTED_JSON, 'r') as f:
        price_data = json.load(f)
        
    high_pcts = []
    low_pcts = []
    
    valid_count = 0
    missing_data_dates = []
    
    for d in filtered_dates:
        if d in price_data:
            entry = price_data[d]
            open_p = entry['daily_open']
            high_p = entry['daily_high']
            low_p = entry['daily_low']
            
            if open_p > 0:
                h = (high_p - open_p) / open_p * 100
                l = (low_p - open_p) / open_p * 100
                high_pcts.append(h)
                low_pcts.append(l)
                valid_count += 1
        else:
            missing_data_dates.append(d)
            
    print(f"Valid Price Data Found: {valid_count} days")
    
    # 3. Generate Distribution Table
    buckets = [round(x * 0.1, 1) for x in range(51)] # 0.0 to 5.0
    
    high_counts = {}
    low_counts = {}
    
    for val in high_pcts:
        b = get_bucket(val)
        b_key = f"{b:.1f}"
        high_counts[b_key] = high_counts.get(b_key, 0) + 1
        
    for val in low_pcts:
        b = get_bucket(val)
        b_key = f"{b:.1f}"
        low_counts[b_key] = low_counts.get(b_key, 0) + 1
        
    print("\n=== FILTERED DISTRIBUTION SIDE-BY-SIDE ===")
    print(f"{'Bucket':<6} | {'HIGH Count':<10} | {'HIGH %':<8} | {'LOW Count':<10} | {'LOW %':<8}")
    print("-" * 60)
    
    for b in buckets:
        b_key = f"{b:.1f}"
        h_cnt = high_counts.get(b_key, 0)
        l_cnt = low_counts.get(b_key, 0)
        
        h_pct = (h_cnt / valid_count * 100) if valid_count else 0
        l_pct = (l_cnt / valid_count * 100) if valid_count else 0
        
        # Only print rows with data to save space if sparse
        if h_cnt > 0 or l_cnt > 0:
            print(f"{b_key:<6} | {h_cnt:<10} | {h_pct:6.1f}% | {l_cnt:<10} | {l_pct:6.1f}%")
            
    print("-" * 60)
    print(f"Total Samples: {valid_count}")

if __name__ == "__main__":
    run_filtered_analysis()
