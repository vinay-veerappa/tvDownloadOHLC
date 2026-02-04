
import json
import pandas as pd
import numpy as np
import re
from pathlib import Path

# --- 1. Load Source Data ---
def load_data():
    with open("data/NQ1_profiler.json", "r") as f:
        return json.load(f)

# --- 2. Replicate Pine Logic ---
# Pine encodes statuses: Long True=1, Long False=2, Short True=3, Short False=4
def encode_status(s):
    if not s: return 0
    s_low = s.lower()
    if "long true" in s_low: return 1
    if "long false" in s_low: return 2
    if "short true" in s_low: return 3
    if "short false" in s_low: return 4
    return 0

def check_match(hist_s, hist_b, live_s, live_b):
    # s_ok = lc==0 ? true : hc==lc
    s_ok = True if live_s == 0 else (hist_s == live_s)
    # b_ok = lb ? hb==1 : true
    b_ok = (hist_b == 1) if live_b else True
    return s_ok and b_ok

# --- 3. Filter Execution ---
def run_comparison(sessions, filter_asia, filter_lon):
    # filter_asia: (status_code, broken_bool)
    # filter_lon: (status_code, broken_bool)
    
    matches = []
    for s in sessions:
        if s['session'] == 'Asia':
            # Skip until we find the London for the same date
            # Actually, the JSON is flat. Every object is a session.
            pass
    
    # Group by date
    by_date = {}
    for s in sessions:
        d = s['date']
        if d not in by_date: by_date[d] = {}
        by_date[d][s['session']] = s
        
    matched_dates = []
    for d, sess_map in by_date.items():
        asia = sess_map.get('Asia')
        lon = sess_map.get('London')
        
        if not asia or not lon: continue
        
        # Test Asia
        a_code = encode_status(asia['status'])
        a_bk = 1 if asia.get('broken') else 0
        a_match = check_match(a_code, a_bk, filter_asia[0], filter_asia[1])
        
        # Test London
        l_code = encode_status(lon['status'])
        l_bk = 1 if lon.get('broken') else 0
        l_match = check_match(l_code, l_bk, filter_lon[0], filter_lon[1])
        
        if a_match and l_match:
            matched_dates.append(d)
            
    return matched_dates

# --- 4. Price Model Extraction ---
def extract_pine_model(name):
    path = Path(f"scripts/profiler/ProfilerData_Model_{name}.pine")
    if not path.exists(): return [], [], []
    with open(path, 'r') as f:
        content = f.read()
    
    times = [int(x) for x in re.findall(r"_get_times_0\(\) =>\s+array\.from\(([\d\.,\s-]+)\)", content)[0].split(',')]
    highs = [float(x) for x in re.findall(r"_get_high_0\(\) =>\s+array\.from\(([\d\.,\s-]+)\)", content)[0].split(',')]
    lows = [float(x) for x in re.findall(r"_get_low_0\(\) =>\s+array\.from\(([\d\.,\s-]+)\)", content)[0].split(',')]
    return times, highs, lows

# --- 5. Main ---
if __name__ == "__main__":
    sessions = load_data()
    
    # User's Filters: Asia Long True (1) Broken (True), London Short (3? let's try 3)
    filter_asia = (1, True)
    filter_lon = (3, False) # "London Short none" -> Short True (3), Broken=False
    
    print(f"Applying Filters: Asia(LT, Broken), London(ST, -)")
    matched_dates = run_comparison(sessions, filter_asia, filter_lon)
    print(f"Matched Dates Count: {len(matched_dates)}")
    
    if matched_dates:
        print(f"First 5 Matched Dates: {matched_dates[:5]}")
        
    # Now compare values
    # Pine Model LT (NY2 Long True Global)
    p_t, p_h, p_l = extract_pine_model("LT")
    
    print("\n--- PINE LIBRARY DATA (LT Model) ---")
    for i in range(0, 10):
        if i < len(p_t):
            print(f"Min: {p_t[i]:3d} | High: {p_h[i]:.4f} | Low: {p_l[i]:.4f}")
    
    # We should also compare this to the API endpoint if possible, but I'll 
    # just calculate it from Parquet here to be the "Truth".
    
    print("\nNote: Pine Model LT is GLOBAL (all NY2 Long True days).")
    print("User Filtered Model would be a subset of these days.")
