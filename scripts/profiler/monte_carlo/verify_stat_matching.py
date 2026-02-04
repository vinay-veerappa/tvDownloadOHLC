
import json
import numpy as np
import sys
import re
from pathlib import Path

# Replicate extraction of individual day stats from Pine
def extract_pine_values(lib_name, v_name):
    path = Path(f"scripts/profiler/{lib_name}.pine")
    if not path.exists(): return []
    with open(path, 'r') as f:
        content = f.read()
    
    # Matches _get_hod_pct_0() => array.from(...)
    # Note: There might be multiple chunks (0, 1, 2...)
    pattern = rf"_get_{v_name}_\d+\(\) =>\s+array\.from\(([\d\.,\s-]+)\)"
    chunks = re.findall(pattern, content)
    
    all_vals = []
    for chunk in chunks:
        all_vals.extend([float(x) for x in chunk.split(',')])
    return all_vals

def extract_pine_bits(lib_name, v_name):
    path = Path(f"scripts/profiler/{lib_name}.pine")
    if not path.exists(): return []
    with open(path, 'r') as f:
        content = f.read()
    
    pattern = rf"_get_{v_name}_\d+\(\) =>\s+array\.from\(([\d\.,\s-]+)\)"
    chunks = re.findall(pattern, content)
    
    all_vals = []
    for chunk in chunks:
        all_vals.extend([int(x) for x in chunk.split(',')])
    return all_vals

def f_get_code(val, i):
    return (val >> (3 * (14 - (i % 15)))) & 7

def f_get_bit(val, i):
    return (val >> (14 - (i % 15))) & 1

def run_verification():
    print("--- INDIVIDUAL DAY STAT VERIFICATION ---")
    
    # 1. Load Truth (JSON)
    with open("data/NQ1_profiler.json", "r") as f:
        sessions = json.load(f)
    
    # Group by date
    by_date = {}
    for s in sessions:
        d = s['date']
        if d not in by_date: by_date[d] = {}
        by_date[d][s['session']] = s
    
    sorted_dates = sorted(by_date.keys())
    
    # 2. Replicate Pine Libraries (Loading bit-packed arrays)
    asia_packed = extract_pine_bits("ProfilerData_Asia", "asia")
    lon_packed = extract_pine_bits("ProfilerData_London", "london")
    asia_bk_packed = extract_pine_bits("ProfilerData_Broken", "asia")
    
    # Load HOD/LOD pcts from Pine
    pine_hod_pcts = extract_pine_values("ProfilerData_Levels", "hod_pct")
    pine_lod_pcts = extract_pine_values("ProfilerData_Levels", "lod_pct")
    
    # Debug Lengths
    n_days_pine = len(pine_hod_pcts)
    print(f"JSON Days: {len(sorted_dates)}")
    print(f"Pine Days: {n_days_pine}")
    
    # Pine data is likely the LATEST N days.
    # We need to slice sorted_dates to match the LATEST n_days_pine.
    if len(sorted_dates) > n_days_pine:
        comparison_dates = sorted_dates[-n_days_pine:]
    else:
        comparison_dates = sorted_dates
        n_days_pine = len(comparison_dates)

    # 3. Filter for: Asia LT (1) Broken (1), London Short (3 or 4)
    target_indices = []
    # Note: Indices here are relative to the comparison_dates / pine arrays
    for i in range(n_days_pine):
        # Unpack bits for this index
        a_s = f_get_code(asia_packed[i//15], i)
        a_bk = f_get_bit(asia_bk_packed[i//15], i)
        l_s = f_get_code(lon_packed[i//15], i)
        
        if a_s == 1 and a_bk == 1:
            if l_s == 3 or l_s == 4:
                target_indices.append(i)
                
    print(f"Filter matched {len(target_indices)} days in the available Pine data.")
    
    # 4. Calculate Median HOD/LOD Pct from Pine Data
    if not target_indices:
        print("No matches found in the available timeframe.")
        return

    filtered_pine_hod = [pine_hod_pcts[i] for i in target_indices]
    filtered_pine_lod = [pine_lod_pcts[i] for i in target_indices]
    
    pine_median_hod = np.median(filtered_pine_hod)
    pine_median_lod = np.median(filtered_pine_lod)
    
    # 5. Get Truth from JSON for the SAME DATES
    matched_dates = [comparison_dates[i] for i in target_indices]
    
    # Open daily hod/lod json to get the real pct
    with open("data/NQ1_daily_hod_lod.json", "r") as f:
        hl_data = json.load(f)
        
    truth_hods = []
    truth_lods = []
    for d in matched_dates:
        stats = hl_data.get(d)
        if stats:
            # Replicate generate_profiler_pine logic: round((h-o)/o*100, 2)
            o = stats.get('daily_open')
            if o and o > 0:
                h_pct = round((stats.get('hod_price') - o) / o * 100, 2)
                l_pct = round((stats.get('lod_price') - o) / o * 100, 2)
                truth_hods.append(h_pct)
                truth_lods.append(l_pct)
                
    truth_median_hod = np.median(truth_hods)
    truth_median_lod = np.median(truth_lods)
    
    # 6. Final Report
    print(f"\nMetric | Pine Script (Filtered Median) | Profiler Service (Truth) | Match?")
    print("-" * 80)
    
    match_hod = "YES" if abs(pine_median_hod - truth_median_hod) < 0.05 else "NO"
    match_lod = "YES" if abs(pine_median_lod - truth_median_lod) < 0.05 else "NO"
    
    print(f"HOD % | {pine_median_hod:<22.2f} | {truth_median_hod:<24.2f} | {match_hod}")
    print(f"LOD % | {pine_median_lod:<22.2f} | {truth_median_lod:<24.2f} | {match_lod}")
    
    print(f"\nSamples compared: {len(target_indices)}")

if __name__ == "__main__":
    run_verification()
