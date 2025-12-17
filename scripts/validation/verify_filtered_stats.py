
import json
import numpy as np
import pandas as pd
from pathlib import Path
import sys
import os
import argparse
from collections import Counter

# Add project root
sys.path.append(os.getcwd())

from api.services.data_loader import DATA_DIR

def parse_filter_string(filter_str):
    """
    Parse filter string e.g. "Short True Broken"
    Returns dict of requirements.
    """
    if not filter_str: return None
    
    reqs = {}
    parts = filter_str.lower().split()
    
    # Direction
    if 'short' in parts: reqs['direction'] = 'Short'
    elif 'long' in parts: reqs['direction'] = 'Long'
    
    # Session Status
    if 'true' in parts: reqs['session_status'] = 'True'
    elif 'false' in parts: reqs['session_status'] = 'False'
    
    # Broken Status
    if 'broken' in parts: reqs['broken'] = True
    elif 'complete' in parts: reqs['broken'] = False # Assuming 'complete' means Not Broken? 
    # Or 'unbroken'? 'Complete' usually means Target Hit? 
    # User said "Broken".
    
    return reqs

def check_session_match(session_data, reqs):
    if not reqs: return True # No filter
    if not session_data: return False 

    # Check Direction/Session (Status string "Short True")
    if 'direction' in reqs:
        if reqs['direction'] not in session_data['status']: return False
    
    if 'session_status' in reqs:
        if reqs['session_status'] not in session_data['status']: return False
        
    # Check Broken
    if 'broken' in reqs:
        is_broken = session_data.get('broken', False)
        if reqs['broken'] != is_broken: return False
        
    return True

def get_session_info(profiler_data):
    by_date = {}
    for entry in profiler_data:
        d = entry['date']
        sess = entry['session']
        if d not in by_date: by_date[d] = {}
        by_date[d][sess] = entry
    return by_date

def get_stats_from_buckets(buckets):
    if not buckets: return 0, 0
    data = []
    for k, v in buckets.items():
        try:
            val = float(k)
            data.append((val, v))
        except: continue
    
    if not data: return 0, 0
    
    data.sort(key=lambda x: x[0])
    total = sum(d[1] for d in data)
    
    # Mode
    mode = max(data, key=lambda x: x[1])[0]
    
    # Median
    cum = 0
    med = 0
    for val, count in data:
        cum += count
        if cum >= total / 2:
            med = val
            break
    return med, mode

def main():
    parser = argparse.ArgumentParser(description="Verify Filtered Range Stats")
    parser.add_argument("--ticker", default="NQ1")
    parser.add_argument("--ref", required=True, help="Path to Reference JSON")
    parser.add_argument("--asia", help="Asia Filter (e.g. 'Short True Broken')")
    parser.add_argument("--london", help="London Filter")
    parser.add_argument("--ny1", help="NY1 Filter")
    parser.add_argument("--ny2", help="NY2 Filter")
    
    args = parser.parse_args()
    
    # 1. Load Data
    p_path = Path("data") / f"{args.ticker}_profiler.json"
    h_path = Path("data") / f"{args.ticker}_daily_hod_lod.json"
    
    if not p_path.exists() or not h_path.exists():
        print(f"Data files missing for {args.ticker}")
        return

    try:
        with open(p_path) as f: profiler_data = json.load(f)
        with open(h_path) as f: daily_data = json.load(f)
        with open(args.ref) as f: ref_data = json.load(f)
    except Exception as e:
        print(f"Error loading files: {e}")
        return

    # 2. Parse Filters
    filters = {
        'Asia': parse_filter_string(args.asia),
        'London': parse_filter_string(args.london),
        'NY1': parse_filter_string(args.ny1),
        'NY2': parse_filter_string(args.ny2)
    }
    
    print(f"\n--- Filters Applied ({args.ticker}) ---")
    for k, v in filters.items():
        if v: print(f"{k}: {v}")
    
    # 3. Filter Dates
    session_map = get_session_info(profiler_data)
    matching_dates = []
    
    for date, sessions in session_map.items():
        match = True
        for sess_name, reqs in filters.items():
            if reqs: # If filter exists for this session
                if sess_name not in sessions:
                    match = False
                    break
                if not check_session_match(sessions[sess_name], reqs):
                    match = False
                    break
        if match:
            matching_dates.append(date)
            
    matching_dates.sort()
    count = len(matching_dates)
    print(f"\nFound {count} matching days.")
    
    # 4. Calc Stats
    highs = []
    lows = []
    
    for d in matching_dates:
        if d in daily_data:
            r = daily_data[d]
            op = r['daily_open']
            hi = r['daily_high']
            lo = r['daily_low']
            
            if op > 0:
                h_pct = (hi - op) / op * 100
                l_pct = (lo - op) / op * 100
                highs.append(h_pct)
                lows.append(l_pct)
    
    # 5. Compare
    l_h_med = np.median(highs) if highs else 0
    l_l_med = np.median(lows) if lows else 0
    
    if 'distributions' in ref_data and 'daily' in ref_data['distributions']:
        ref_daily = ref_data['distributions']['daily']
        r_h_med, r_h_mode = get_stats_from_buckets(ref_daily.get('high', {}))
        r_l_med, r_l_mode = get_stats_from_buckets(ref_daily.get('low', {}))
        ref_count = ref_data.get('meta', {}).get('count', 0)
    else:
        print("Reference JSON structure mismatch (missing distributions.daily)")
        return

    print("\n" + "="*60)
    print(f"{'METRIC':<15} | {'LOCAL':<10} | {'REF':<10} | {'DIFF':<10}")
    print("="*60)
    print(f"{'Count':<15} | {count:<10} | {ref_count:<10} | {count - ref_count:<10}")
    print(f"{'High Median':<15} | {l_h_med:<10.2f} | {r_h_med:<10.2f} | {l_h_med - r_h_med:<10.2f}")
    print(f"{'Low Median':<15} | {l_l_med:<10.2f} | {r_l_med:<10.2f} | {l_l_med - r_l_med:<10.2f}")

    # 6. Detailed Buckets
    print("\n--- Top High Buckets ---")
    local_h_buckets = Counter([round(x, 1) for x in highs])
    print(f"Local: {local_h_buckets.most_common(5)}")
    
    ref_h_list = []
    for k,v in ref_daily.get('high', {}).items():
        try: ref_h_list.append((float(k), v))
        except: pass
    ref_h_list.sort(key=lambda x: x[1], reverse=True)
    print(f"Ref  : {ref_h_list[:5]}")
    
    print("\n--- Top Low Buckets ---")
    local_l_buckets = Counter([round(x, 1) for x in lows])
    print(f"Local: {local_l_buckets.most_common(5)}")
    
    ref_l_list = []
    for k,v in ref_daily.get('low', {}).items():
        try: ref_l_list.append((float(k), v))
        except: pass
    ref_l_list.sort(key=lambda x: x[1], reverse=True)
    print(f"Ref  : {ref_l_list[:5]}")

if __name__ == "__main__":
    main()
