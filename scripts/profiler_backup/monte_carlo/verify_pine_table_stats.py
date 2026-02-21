
import json
import numpy as np
import pandas as pd
from pathlib import Path
import sys

# Load Data
DATA_DIR = Path("data")
PROFILER_FILE = DATA_DIR / "NQ1_profiler.json"
DAILY_FILE = DATA_DIR / "NQ1_daily_hod_lod.json"

# Helper Functions mirroring Pine Logic
def pine_fmt_time(minutes_from_1800):
    # 0 = 18:00, 360 = 00:00, 1080 = 12:00
    # Wraps at 1440
    total_min = (minutes_from_1800 + 1080) % 1440
    h = total_min // 60
    m = total_min % 60
    return f"{h:02d}:{m:02d}"

def calc_mode_time(times_arr):
    if not times_arr: return "N/A"
    buckets = [0] * 96
    for t in times_arr:
        # Time array from daily_hod_lod is already HH:MM converted to minutes from 00:00
        # Pine Gen Logic: "rel = (t - 1080 + 1440) % 1440"
        rel = (t - 1080 + 1440) % 1440
        b_idx = min(int(rel / 15), 95)
        buckets[b_idx] += 1
    max_c = max(buckets)
    max_b = buckets.index(max_c)
    start_rel = max_b * 15
    end_rel = start_rel + 15
    return f"{pine_fmt_time(start_rel)}-{pine_fmt_time(end_rel)}"

def calc_mode_dist(vals_arr):
    if not vals_arr: return "N/A"
    step = 0.1
    n_b = 120
    buckets = [0] * n_b
    
    # Filter out insane values
    clean_vals = [v for v in vals_arr if -99 < v < 99]
    if not clean_vals: return "N/A"
    
    for v in clean_vals:
        b_idx = min(max(int((v + 6.0) / step), 0), n_b - 1)
        buckets[b_idx] += 1
    max_c = max(buckets)
    max_b = buckets.index(max_c)
    mode_s = (max_b * step) - 6.0
    mode_e = mode_s + step
    
    srtd = sorted(clean_vals)
    mid_idx = len(clean_vals) // 2
    med_val = srtd[mid_idx]
    med_s = int(np.floor(med_val / step)) * step
    med_e = med_s + step
    
    u_min = min(mode_s, med_s)
    u_max = max(mode_e, med_e)
    return f"{u_max:.1f} to {u_min:.1f}%"

def calculate_table_stats():
    print(f"Loading {PROFILER_FILE} and {DAILY_FILE}...")
    sys.stdout.flush()
    
    try:
        with open(PROFILER_FILE, 'r') as f:
            data = json.load(f)
        with open(DAILY_FILE, 'r') as f:
            daily_data = json.load(f)
    except Exception as e:
        print(f"Error loading JSON: {e}")
        return

    # Process Profiler for Classification
    days_map = {}
    if isinstance(data, list): items = data 
    else: items = data.values()

    for item in items:
        d = item.get('date')
        if not d: continue
        if d not in days_map: days_map[d] = []
        days_map[d].append(item)
        
    asia_outcomes = [] 
    arr_s_hp = [] 
    arr_s_lp = []
    arr_d_ht = []
    arr_d_lt = []
    
    valid_count = 0
    sorted_dates = sorted(days_map.keys())
    unique_dates = set()

    for d in sorted_dates:
        if d in unique_dates: continue
        
        sessions = days_map[d]
        asia_sess = next((s for s in sessions if s.get('session') == 'Asia'), None)
        if not asia_sess: continue 
        
        # Check matching daily data
        if d not in daily_data:
            continue
            
        unique_dates.add(d)
        
        status = asia_sess.get('status', 'None')
        code = 0
        if status == 'Long True': code = 1
        elif status == 'Long False': code = 2
        elif status == 'Short True': code = 3
        elif status == 'Short False': code = 4
        
        # Get Stats from DAILY_HOD_LOD (Source of truth for Table)
        # generator: data_map[d_int]['hod_p'] = round((d_high - d_open) / d_open * 100, 2)
        
        d_stats = daily_data[d]
        
        # Calculate Pct manually to ensure logic match
        d_open = d_stats.get('daily_open', 0)
        d_high = d_stats.get('hod_price', 0)
        d_low = d_stats.get('lod_price', 0)
        
        # Time conversion
        ht_str = d_stats.get('hod_time', '00:00')
        lt_str = d_stats.get('lod_time', '00:00')
        
        if d_open == 0: continue
        
        hp = (d_high - d_open) / d_open * 100
        lp = (d_low - d_open) / d_open * 100
        
        h_parts = ht_str.split(':')
        d_ht = int(h_parts[0])*60 + int(h_parts[1])
        
        l_parts = lt_str.split(':')
        d_lt = int(l_parts[0])*60 + int(l_parts[1])
        
        asia_outcomes.append(code)
        arr_s_hp.append(hp)
        arr_s_lp.append(lp)
        arr_d_ht.append(d_ht)
        arr_d_lt.append(d_lt)
        valid_count += 1

    res_map = {1: "Long True", 2: "Long False", 3: "Short True", 4: "Short False"}
    
    print("-" * 140)
    print(f"{'Outcome':<12} | {'Stats':<18} | {'LOD Time':<12} | {'HOD Time':<12} | {'LOD Dist':<16} | {'HOD Dist':<16}")
    print("-" * 140)
    sys.stdout.flush()
    
    total_valid = 0
    for c in [1, 2, 3, 4]: total_valid += asia_outcomes.count(c)

    for code in [1, 2, 3, 4]:
        indices = [i for i, x in enumerate(asia_outcomes) if x == code]
        cnt = len(indices)
        if cnt == 0: continue
        
        pct_count = (cnt / total_valid * 100)
        stats_str = f"{pct_count:.1f}% ({cnt})"
        
        sub_s_hp = [arr_s_hp[i] for i in indices]
        sub_s_lp = [arr_s_lp[i] for i in indices]
        sub_d_ht = [arr_d_ht[i] for i in indices]
        sub_d_lt = [arr_d_lt[i] for i in indices]
        
        lod_time_str = calc_mode_time(sub_d_lt)
        hod_time_str = calc_mode_time(sub_d_ht)
        lod_dist_str = calc_mode_dist(sub_s_lp)
        hod_dist_str = calc_mode_dist(sub_s_hp)
        
        print(f"{res_map[code]:<12} | {stats_str:<18} | {lod_time_str:<12} | {hod_time_str:<12} | {lod_dist_str:<16} | {hod_dist_str:<16}")
        sys.stdout.flush()

    print("-" * 140)
    sys.stdout.flush()

if __name__ == "__main__":
    calculate_table_stats()
