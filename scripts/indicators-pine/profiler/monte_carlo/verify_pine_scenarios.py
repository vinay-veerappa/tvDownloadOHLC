
import json
import re
import numpy as np
from pathlib import Path
import sys

# Paths
DATA_DIR = Path("data")
PINE_DIR = Path("scripts/profiler")

PROFILER_JSON = DATA_DIR / "NQ1_profiler.json"
DAILY_JSON = DATA_DIR / "NQ1_daily_hod_lod.json"

# Pine Files to Parse
PINE_FILES = {
    'Asia': PINE_DIR / "ProfilerData_Asia.pine",
    'London': PINE_DIR / "ProfilerData_London.pine",
    'NY': PINE_DIR / "ProfilerData_NY.pine",
    'Levels': PINE_DIR / "ProfilerData_Levels.pine",
    'Times': PINE_DIR / "ProfilerData_Times.pine"
}

# --- Parsing Helpers ---
def parse_pine_array(file_path, func_pattern):
    if not file_path.exists(): return []
    with open(file_path, 'r', encoding='utf-8') as f: content = f.read()
    
    regex = re.compile(r'(\w+)\(\) =>\s+array\.from\(([\d\., \-\+e]+)\)')
    matches = regex.findall(content)
    
    relevant_matches = []
    for m in matches:
        fname = m[0]
        if func_pattern in fname:
            try:
                # Find last number in function name (chunk index)
                # e.g. _get_asia_0 -> 0
                idx = int(re.findall(r'\d+', fname)[-1])
                relevant_matches.append((idx, m[1]))
            except: pass
            
    relevant_matches.sort(key=lambda x: x[0])
    final_data = []
    for _, d_str in relevant_matches:
        vals = [float(x.strip()) for x in d_str.split(',')]
        final_data.extend(vals)
    return final_data

# --- Stats Logic (Shared) ---
def pine_fmt_time(minutes_from_1800):
    total_min = (minutes_from_1800 + 1080) % 1440
    h = total_min // 60
    m = total_min % 60
    return f"{int(h):02d}:{int(m):02d}"

def calc_mode_time(times_arr):
    if not times_arr: return "N/A"
    buckets = [0] * 96
    for t in times_arr:
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
    clean = [v for v in vals_arr if -99 < v < 99]
    if not clean: return "N/A"
    
    step = 0.1
    n_b = 120
    buckets = [0] * n_b
    for v in clean:
        b_idx = min(max(int((v + 6.0) / step), 0), n_b - 1)
        buckets[b_idx] += 1
        
    max_c = max(buckets)
    max_b = buckets.index(max_c)
    mode_s = (max_b * step) - 6.0
    mode_e = mode_s + step
    
    srtd = sorted(clean)
    mid_idx = len(clean) // 2
    med_val = srtd[mid_idx]
    med_s = int(np.floor(med_val / step)) * step
    med_e = med_s + step
    
    u_min = min(mode_s, med_s)
    u_max = max(mode_e, med_e)
    # Format high to low magnitude (e.g. 0.6 to 0.3)
    return f"{u_max:.1f} to {u_min:.1f}%"

# --- Unpacking Logic ---
def unpack_all(packed_arr, bits):
    """
    Unpacks a list of 50-bit integers into individual values.
    Mirrors Pine logic: pos = 14 - (i % 15).
    """
    res = []
    items_per_chunk = 15
    mask = (1 << bits) - 1
    
    for pkg in packed_arr:
        pkg = int(pkg)
        for i in range(items_per_chunk):
            pos = 14 - i
            shift = pos * bits
            val = (pkg >> shift) & mask
            res.append(val)
    return res

# --- Main Verification Logic ---
def run_scenarios():
    print("Loading Data...")
    sys.stdout.flush()
    
    # 1. Load JSON Source
    with open(PROFILER_JSON, 'r') as f: prof_data = json.load(f)
    with open(DAILY_JSON, 'r') as f: daily_data = json.load(f)
    
    # Prepare Source DataFrame keys
    prof_map = {}
    if isinstance(prof_data, list): it = prof_data
    else: it = prof_data.values()
    
    # We need to group by Date to get all sessions for a day
    date_sessions = {}
    for item in it:
        d = item.get('date')
        if not d: continue
        if d not in date_sessions: date_sessions[d] = {}
        date_sessions[d][item['session']] = item.get('status', 'None')

    # 2. Load Pine Arrays
    print("Parsing Pine Arrays...")
    # Status Arrays are PACKED (3 bits)
    p_asia_raw = parse_pine_array(PINE_FILES['Asia'], "_get_asia_")
    p_lon_raw = parse_pine_array(PINE_FILES['London'], "_get_london_")
    p_ny1_raw = parse_pine_array(PINE_FILES['NY'], "_get_ny1_")
    p_ny2_raw = parse_pine_array(PINE_FILES['NY'], "_get_ny2_")
    
    print(f"Unpacking Status Arrays (Raw Size: {len(p_asia_raw)})...")
    p_asia = unpack_all(p_asia_raw, 3)
    p_lon = unpack_all(p_lon_raw, 3)
    p_ny1 = unpack_all(p_ny1_raw, 3)
    p_ny2 = unpack_all(p_ny2_raw, 3)
    
    # Metrics are FLOAT (Not packed)
    p_hod_p = parse_pine_array(PINE_FILES['Levels'], "_get_hod_pct_")
    p_lod_p = parse_pine_array(PINE_FILES['Levels'], "_get_lod_pct_")
    p_hod_t = parse_pine_array(PINE_FILES['Times'], "_get_hod_time_")
    p_lod_t = parse_pine_array(PINE_FILES['Times'], "_get_lod_time_")
    
    # Verify Lengths
    n = len(p_asia)
    print(f"Pine Unpacked Length: {n} (Dates: {len(p_hod_p)})")
    
    # Parse Dates from Pine (Master Index)
    print("Parsing Pine Integers (Dates)...")
    p_dates_raw = parse_pine_array(PINE_FILES['Asia'], "_get_dates_")
    
    # Convert dates to string format matching JSON ("YYYY-MM-DD")
    pine_dates_str = []
    for d_int in p_dates_raw:
        s = str(int(d_int))
        formatted = f"{s[:4]}-{s[4:6]}-{s[6:]}"
        pine_dates_str.append(formatted)
        
    print(f"Pine Master Dates: {len(pine_dates_str)}")
    
    limit = len(pine_dates_str)
    
    # Truncate Pine Arrays to Limit (Remove Padding)
    p_asia = p_asia[:limit]
    p_lon = p_lon[:limit]
    p_ny1 = p_ny1[:limit]
    p_ny2 = p_ny2[:limit]
    p_hod_p = p_hod_p[:limit]
    p_lod_p = p_lod_p[:limit]
    p_hod_t = p_hod_t[:limit]
    p_lod_t = p_lod_t[:limit]
    
    # Build Source Vectors using Pine Dates
    s_asia, s_lon, s_ny1, s_ny2 = [], [], [], []
    s_hod_p, s_lod_p, s_hod_t, s_lod_t = [], [], [], []
    
    for d in pine_dates_str:
        if d not in date_sessions or d not in daily_data:
            s_asia.append(-99)
            s_lon.append(-99)
            s_ny1.append(-99)
            s_ny2.append(-99)
            s_hod_p.append(-99.0)
            s_lod_p.append(-99.0)
            s_hod_t.append(0)
            s_lod_t.append(0)
            continue
            
        sess = date_sessions[d]
        def enc(s):
            s = s.lower()
            if "long" in s: return 1 if "true" in s else 2
            if "short" in s: return 3 if "true" in s else 4
            return 0
        s_asia.append(enc(sess.get('Asia', '')))
        s_lon.append(enc(sess.get('London', '')))
        s_ny1.append(enc(sess.get('NY1', '')))
        s_ny2.append(enc(sess.get('NY2', '')))
        
        dm = daily_data[d]
        op = dm.get('daily_open', 0)
        hp = dm.get('hod_price', 0)
        lp = dm.get('lod_price', 0)
        
        if op > 0:
            s_hod_p.append((hp - op)/op * 100)
            s_lod_p.append((lp - op)/op * 100)
        else:
            s_hod_p.append(0.0)
            s_lod_p.append(0.0)
            
        def t_to_min(ts):
            if not ts: return 0
            h, m = map(int, ts.split(':'))
            return h*60 + m
        s_hod_t.append(t_to_min(dm.get('hod_time', '00:00')))
        s_lod_t.append(t_to_min(dm.get('lod_time', '00:00')))


    # SCENARIOS
    scenarios = [
        ("Asia Long True",    lambda i: s_asia[i] == 1, lambda i: int(p_asia[i]) == 1),
        ("Asia Long False",   lambda i: s_asia[i] == 2, lambda i: int(p_asia[i]) == 2),
        ("Asia Short True",   lambda i: s_asia[i] == 3, lambda i: int(p_asia[i]) == 3),
        ("Asia Short False",  lambda i: s_asia[i] == 4, lambda i: int(p_asia[i]) == 4),
        ("London Long True",  lambda i: s_lon[i]  == 1, lambda i: int(p_lon[i])  == 1),
        ("London Short False",lambda i: s_lon[i]  == 4, lambda i: int(p_lon[i])  == 4),
        ("NY1 Long True",     lambda i: s_ny1[i]  == 1, lambda i: int(p_ny1[i])  == 1),
        ("NY1 Short True",    lambda i: s_ny1[i]  == 3, lambda i: int(p_ny1[i])  == 3),
        ("NY2 Long False",    lambda i: s_ny2[i]  == 2, lambda i: int(p_ny2[i])  == 2),
        ("Global (No Filter)",lambda i: True,           lambda i: True),
    ]
    
    print("\n" + "="*120)
    print(f"{'Scenario':<20} | {'Src Count':<10} {'Pine Count':<10} | {'Src HOD%':<16} {'Pine HOD%':<16} | {'Src HOD Time':<12} {'Pine HOD Time':<12}")
    print("="*120)
    
    for name, f_src, f_pine in scenarios:
        # Filter Source
        src_indices = [i for i in range(len(s_asia)) if f_src(i)]
        src_cnt = len(src_indices)
        
        src_hp_vals = [s_hod_p[i] for i in src_indices]
        src_ht_vals = [s_hod_t[i] for i in src_indices]
        
        src_mode_dist = calc_mode_dist(src_hp_vals)
        src_mode_time = calc_mode_time(src_ht_vals)
        
        # Filter Pine
        pine_indices = [i for i in range(len(p_asia)) if f_pine(i)]
        pine_cnt = len(pine_indices)
        
        pine_hp_vals = [p_hod_p[i] for i in pine_indices]
        pine_ht_vals = [p_hod_t[i] for i in pine_indices]
        
        pine_mode_dist = calc_mode_dist(pine_hp_vals)
        pine_mode_time = calc_mode_time(pine_ht_vals)
        
        # Match Indicator
        m_cnt = "OK" if src_cnt == pine_cnt else "FAIL"
        m_dist = "OK" if src_mode_dist == pine_mode_dist else "FAIL"
        
        print(f"{name:<20} | {src_cnt:<10} {pine_cnt:<10} | {src_mode_dist:<16} {pine_mode_dist:<16} | {src_mode_time:<12} {pine_mode_time:<12}")
        
    print("="*120)
    sys.stdout.flush()

def inspect_scenario(scenario_name, limit=20):
    print(f"\nINSPECTING DETAILS: {scenario_name}")
    print("Loading Data...")
    
    # Load same data as run_scenarios (refactor if needed, but keeping self-contained for now)
    with open(PROFILER_JSON, 'r') as f: prof_data = json.load(f)
    with open(DAILY_JSON, 'r') as f: daily_data = json.load(f)
    
    date_sessions = {}
    if isinstance(prof_data, list): it = prof_data
    else: it = prof_data.values()
    
    for item in it:
        d = item.get('date')
        if not d: continue
        if d not in date_sessions: date_sessions[d] = {}
        date_sessions[d][item['session']] = item.get('status', 'None')

    p_asia = unpack_all(parse_pine_array(PINE_FILES['Asia'], "_get_asia_"), 3)
    p_lon = unpack_all(parse_pine_array(PINE_FILES['London'], "_get_london_"), 3)
    p_ny1 = unpack_all(parse_pine_array(PINE_FILES['NY'], "_get_ny1_"), 3)
    p_ny2 = unpack_all(parse_pine_array(PINE_FILES['NY'], "_get_ny2_"), 3)
    p_hod_p = parse_pine_array(PINE_FILES['Levels'], "_get_hod_pct_")
    p_hod_t = parse_pine_array(PINE_FILES['Times'], "_get_hod_time_")
    
    # Master Dates from Pine
    p_dates_raw = parse_pine_array(PINE_FILES['Asia'], "_get_dates_")
    dates = []
    for d_int in p_dates_raw:
        s = str(int(d_int))
        formatted = f"{s[:4]}-{s[4:6]}-{s[6:]}"
        dates.append(formatted)
        
    limit = len(dates)
    
    # Slicing
    p_asia = p_asia[:limit]
    p_lon = p_lon[:limit]
    p_ny1 = p_ny1[:limit]
    p_ny2 = p_ny2[:limit]
    p_hod_p = p_hod_p[:limit]
    p_hod_t = p_hod_t[:limit]
    
    # Source Vectors
    s_asia, s_lon, s_ny1, s_ny2 = [], [], [], []
    s_hod_p, s_hod_t = [], []
    
    for d in dates:
        if d not in date_sessions or d not in daily_data:
            s_asia.append(-99); s_lon.append(-99); s_ny1.append(-99); s_ny2.append(-99)
            s_hod_p.append(0); s_hod_t.append(0)
            continue
            
        sess = date_sessions[d]
        def enc(s):
            s = s.lower()
            if "long" in s: return 1 if "true" in s else 2
            if "short" in s: return 3 if "true" in s else 4
            return 0
        s_asia.append(enc(sess.get('Asia', '')))
        s_lon.append(enc(sess.get('London', '')))
        s_ny1.append(enc(sess.get('NY1', '')))
        s_ny2.append(enc(sess.get('NY2', '')))
        
        dm = daily_data[d]
        op = dm.get('daily_open', 0)
        hp = dm.get('hod_price', 0)
        s_hod_p.append((hp - op)/op * 100 if op > 0 else 0)
        
        def t_to_min(ts):
            if not ts: return 0
            h, m = map(int, ts.split(':'))
            return h*60 + m
        s_hod_t.append(t_to_min(dm.get('hod_time', '00:00')))

    # Define Filters Map (Dynamic)
    filters = {
        "Asia Long True": (s_asia, 1),
        "Asia Long False": (s_asia, 2),
        "Asia Short True": (s_asia, 3),
        "Asia Short False": (s_asia, 4),
        "London Long True": (s_lon, 1),
        "London Short True": (s_lon, 3),
        "NY1 Long True": (s_ny1, 1),
        "NY1 Short True": (s_ny1, 3),
        "Asia None None": (s_asia, -1), # Global/No Filter
    }
    
    if scenario_name not in filters:
        print(f"Scenario '{scenario_name}' not found. Available: {list(filters.keys())}")
        return

    arr, code = filters[scenario_name]
    
    if code == -1:
        indices = range(len(arr)) # Select All
    else:
        indices = [i for i in range(len(arr)) if arr[i] == code]
    
    print("-" * 120)
    print(f"{'Date':<12} | {'Src Status':<12} {'Pine Status':<12} | {'Src HOD%':<10} {'Pine HOD%':<10} | {'Src Time':<10} {'Pine Time':<10} | {'Match?'}")
    print("-" * 120)
    
    mismatch = 0
    count = 0
    for i in indices:
        s_s = arr[i]
        # Map source array to pine array dynamically
        if arr == s_asia: p_s = p_asia[i]
        elif arr == s_lon: p_s = p_lon[i]
        elif arr == s_ny1: p_s = p_ny1[i]
        elif arr == s_ny2: p_s = p_ny2[i]
        else: p_s = 0
        
        s_hp = s_hod_p[i]
        p_hp = p_hod_p[i]
        s_ht = s_hod_t[i]
        p_ht = p_hod_t[i]
        
        ok_stat = s_s == int(p_s)
        ok_val = abs(s_hp - p_hp) < 0.01
        ok_time = s_ht == p_ht
        
        if not (ok_stat and ok_val and ok_time): mismatch +=1
        match_str = "OK" if (ok_stat and ok_val and ok_time) else "FAIL"
        
        if count < limit or match_str == "FAIL":
            print(f"{dates[i]:<12} | {s_s:<12} {int(p_s):<12} | {s_hp:<10.2f} {p_hp:<10.2f} | {s_ht:<10} {p_ht:<10} | {match_str}")
        count += 1
        
    print("-" * 120)
    print(f"Total Matches: {len(indices)}")
    print(f"Mismatches: {mismatch}")

def generate_asia_table_report():
    print("\n" + "="*120)
    print(f"VERIFICATION: ASIA SESSION INDICATOR LOGIC SIMULATION")
    print("="*120)
    
    # 1. Load Data (Same as before)
    with open(PROFILER_JSON, 'r') as f: prof_data = json.load(f)
    with open(DAILY_JSON, 'r') as f: daily_data = json.load(f)
    
    date_sessions = {}
    if isinstance(prof_data, list): it = prof_data
    else: it = prof_data.values()
    for item in it:
        d = item.get('date')
        if not d: continue
        if d not in date_sessions: date_sessions[d] = {}
        date_sessions[d][item['session']] = item.get('status', 'None')

    # 2. Extract Pine Data
    p_asia = unpack_all(parse_pine_array(PINE_FILES['Asia'], "_get_asia_"), 3)
    p_hod_p = parse_pine_array(PINE_FILES['Levels'], "_get_hod_pct_")
    p_lod_p = parse_pine_array(PINE_FILES['Levels'], "_get_lod_pct_")
    p_hod_t = parse_pine_array(PINE_FILES['Times'], "_get_hod_time_")
    p_lod_t = parse_pine_array(PINE_FILES['Times'], "_get_lod_time_")
    
    p_dates_raw = parse_pine_array(PINE_FILES['Asia'], "_get_dates_")
    dates = [f"{str(int(d))[:4]}-{str(int(d))[4:6]}-{str(int(d))[6:]}" for d in p_dates_raw]
    
    limit = len(dates)
    p_asia = p_asia[:limit]
    p_hod_p = p_hod_p[:limit]; p_lod_p = p_lod_p[:limit]
    p_hod_t = p_hod_t[:limit]; p_lod_t = p_lod_t[:limit]
    
    # Debug Data Freshness
    prof_dates = sorted([d['date'] for d in prof_data]) if isinstance(prof_data, list) else sorted([d['date'] for d in prof_data.values()])
    daily_dates = sorted(daily_data.keys())
    
    print("-" * 60)
    print(f"DATA FRESHNESS DEBUG:")
    print(f"Profiler JSON Range : {min(prof_dates)} to {max(prof_dates)} (Count: {len(prof_dates)})")
    print(f"Daily JSON Range    : {min(daily_dates)} to {max(daily_dates)} (Count: {len(daily_dates)})")
    print(f"Pine Library Range  : {dates[0]} to {dates[-1]} (Count: {len(dates)})")
    print("-" * 60)

    # 3. Build Source Data (Exact alignment via 'dates')
    s_asia, s_hod_p, s_lod_p, s_hod_t, s_lod_t = [], [], [], [], []
    
    for d in dates:
        if d not in date_sessions or d not in daily_data:
            s_asia.append(-99)
            s_hod_p.append(-99); s_lod_p.append(-99)
            s_hod_t.append(-99); s_lod_t.append(-99)
            continue
        
        # Encode Source Status
        s_raw = date_sessions[d].get('Asia', '')
        code = 0
        if "long" in s_raw.lower(): code = 1 if "true" in s_raw.lower() else 2
        elif "short" in s_raw.lower(): code = 3 if "true" in s_raw.lower() else 4
        s_asia.append(code)
        
        # Metrics
        dm = daily_data[d]
        op = dm.get('daily_open', 0)
        hp = dm.get('hod_price', 0)
        lp = dm.get('lod_price', 0)
        
        s_hod_p.append((hp - op)/op * 100 if op > 0 else 0)
        s_lod_p.append((lp - op)/op * 100 if op > 0 else 0)
        
        def tmn(ts): 
            if not ts: return 0
            h, m = map(int, ts.split(':'))
            return h*60 + m
        s_hod_t.append(tmn(dm.get('hod_time', '00:00')))
        s_lod_t.append(tmn(dm.get('lod_time', '00:00')))

    # 4. Generate Table Rows (Simulate Indicator Loop)
    outcomes = [
        ("Long True", 1),
        ("Long False", 2),
        ("Short True", 3),
        ("Short False", 4)
    ]
    
    # Compact Header
    print(f"{'Outcome':<12} | {'Src/Pine':<9} | {'HOD Dist':<14} {'HOD Time':<10} | {'LOD Dist':<14} {'LOD Time':<10}")
    print("-" * 120)
    
    for label, code in outcomes:
        # PINE LOGIC
        p_idx = [i for i in range(len(p_asia)) if int(p_asia[i]) == code]
        p_vals_h = [p_hod_p[i] for i in p_idx]; p_vals_l = [p_lod_p[i] for i in p_idx]
        p_time_h = [p_hod_t[i] for i in p_idx]; p_time_l = [p_lod_t[i] for i in p_idx]
        
        p_cnt = len(p_idx)
        p_dist_h = calc_mode_dist(p_vals_h); p_dist_l = calc_mode_dist(p_vals_l)
        p_tm_h = calc_mode_time(p_time_h); p_tm_l = calc_mode_time(p_time_l)
        
        # SOURCE LOGIC
        s_idx = [i for i in range(len(s_asia)) if s_asia[i] == code]
        s_vals_h = [s_hod_p[i] for i in s_idx]; s_vals_l = [s_lod_p[i] for i in s_idx]
        s_time_h = [s_hod_t[i] for i in s_idx]; s_time_l = [s_lod_t[i] for i in s_idx]
        
        s_cnt = len(s_idx)
        s_dist_h = calc_mode_dist(s_vals_h); s_dist_l = calc_mode_dist(s_vals_l)
        s_tm_h = calc_mode_time(s_time_h); s_tm_l = calc_mode_time(s_time_l)
        
        print(f"{label:<12} | {s_cnt}/{p_cnt:<4} | {s_dist_h:<14} {s_tm_h:<10} | {s_dist_l:<14} {s_tm_l:<10} [Src]")
        print(f"{'':<12} | {'':<9} | {p_dist_h:<14} {p_tm_h:<10} | {p_dist_l:<14} {p_tm_l:<10} [Pine]")
        print("-" * 120)

    print("-" * 120)

def simulate_combined_filter(asia_filter=None, london_filter=None, ny1_filter=None):
    # Filters format: "Outcome Name" (e.g., "Long True") or None/"None" for any
    print(f"\nVERIFICATION: COMBINED FILTER SIMULATION")
    print(f"Filters: Asia=[{asia_filter}], London=[{london_filter}], NY1=[{ny1_filter}]")
    print("="*120)
    
    # 1. Load & Extract (Reuse common logic or reload - keeping distinct for safety)
    with open(PROFILER_JSON, 'r') as f: prof_data = json.load(f)
    with open(DAILY_JSON, 'r') as f: daily_data = json.load(f)
    
    # Map Source Days
    date_sessions = {}
    if isinstance(prof_data, list): it = prof_data
    else: it = prof_data.values()
    for item in it:
        d = item.get('date'); 
        if not d: continue
        if d not in date_sessions: date_sessions[d] = {}
        date_sessions[d][item['session']] = item.get('status', 'None')

    # Load Pine
    p_asia = unpack_all(parse_pine_array(PINE_FILES['Asia'], "_get_asia_"), 3)
    p_lon = unpack_all(parse_pine_array(PINE_FILES['London'], "_get_london_"), 3)
    p_ny1 = unpack_all(parse_pine_array(PINE_FILES['NY'], "_get_ny1_"), 3)
    
    p_hod_p = parse_pine_array(PINE_FILES['Levels'], "_get_hod_pct_")
    p_lod_p = parse_pine_array(PINE_FILES['Levels'], "_get_lod_pct_")
    p_hod_t = parse_pine_array(PINE_FILES['Times'], "_get_hod_time_")
    p_lod_t = parse_pine_array(PINE_FILES['Times'], "_get_lod_time_")
    
    # Dates
    p_dates_raw = parse_pine_array(PINE_FILES['Asia'], "_get_dates_")
    dates = [f"{str(int(d))[:4]}-{str(int(d))[4:6]}-{str(int(d))[6:]}" for d in p_dates_raw]
    limit = len(dates)
    
    # Slice
    p_asia = p_asia[:limit]; p_lon = p_lon[:limit]; p_ny1 = p_ny1[:limit]
    p_hod_p = p_hod_p[:limit]; p_lod_p = p_lod_p[:limit]
    p_hod_t = p_hod_t[:limit]; p_lod_t = p_lod_t[:limit]
    
    # Build Source Vectors
    s_asia, s_lon, s_ny1 = [], [], []
    s_hod_p, s_lod_p, s_hod_t, s_lod_t = [], [], [], []
    
    for d in dates:
        if d not in date_sessions or d not in daily_data:
            s_asia.append(-99); s_lon.append(-99); s_ny1.append(-99)
            s_hod_p.append(0); s_lod_p.append(0)
            s_hod_t.append(0); s_lod_t.append(0)
            continue
            
        sess = date_sessions[d]
        def enc(s):
            s = s.lower()
            if "long" in s: return 1 if "true" in s else 2
            if "short" in s: return 3 if "true" in s else 4
            return 0
            
        s_asia.append(enc(sess.get('Asia', '')))
        s_lon.append(enc(sess.get('London', '')))
        s_ny1.append(enc(sess.get('NY1', '')))
        
        dm = daily_data[d]
        op = dm.get('daily_open', 0); hp = dm.get('hod_price', 0); lp = dm.get('lod_price', 0)
        s_hod_p.append((hp - op)/op * 100 if op > 0 else 0)
        s_lod_p.append((lp - op)/op * 100 if op > 0 else 0)
        
        def tmn(ts): 
            if not ts: return 0
            h, m = map(int, ts.split(':')) 
            return h*60 + m
        s_hod_t.append(tmn(dm.get('hod_time', '00:00')))
        s_lod_t.append(tmn(dm.get('lod_time', '00:00')))

    # Resolve Filter Codes
    def get_code(f_str):
        if not f_str or f_str.lower() in ["none", "any"]: return -1
        f_str = f_str.lower()
        if "long" in f_str: return 1 if "true" in f_str else 2
        if "short" in f_str: return 3 if "true" in f_str else 4
        return 0 # Explicit None?
        
    c_asia = get_code(asia_filter)
    c_lon = get_code(london_filter)
    c_ny1 = get_code(ny1_filter)
    
    # Filter Indices
    indices_pine = []
    indices_src = []
    
    for i in range(limit):
        # Pine Check
        p_ok = True
        if c_asia != -1 and int(p_asia[i]) != c_asia: p_ok = False
        if c_lon != -1 and int(p_lon[i]) != c_lon: p_ok = False
        if c_ny1 != -1 and int(p_ny1[i]) != c_ny1: p_ok = False
        if p_ok: indices_pine.append(i)
        
        # Source Check
        s_ok = True
        if c_asia != -1 and s_asia[i] != c_asia: s_ok = False
        if c_lon != -1 and s_lon[i] != c_lon: s_ok = False
        if c_ny1 != -1 and s_ny1[i] != c_ny1: s_ok = False
        if s_ok: indices_src.append(i)
        
    # Calculate Stats
    print(f"{'Source':<12} | {len(indices_src):<8} | {calc_mode_dist([s_hod_p[i] for i in indices_src]):<14} {calc_mode_time([s_hod_t[i] for i in indices_src]):<10} | {calc_mode_dist([s_lod_p[i] for i in indices_src]):<14} {calc_mode_time([s_lod_t[i] for i in indices_src]):<10}")
    print(f"{'Pine':<12} | {len(indices_pine):<8} | {calc_mode_dist([p_hod_p[i] for i in indices_pine]):<14} {calc_mode_time([p_hod_t[i] for i in indices_pine]):<10} | {calc_mode_dist([p_lod_p[i] for i in indices_pine]):<14} {calc_mode_time([p_lod_t[i] for i in indices_pine]):<10}")
    print("-" * 120)

    print("-" * 120)

def generate_stats_report():
    print("\n" + "="*120)
    print(f"VERIFICATION: STATISTICAL DISTRIBUTION COMPARISON (TEXTUAL PRICE MODELS)")
    print("="*120)
    
    # 1. Load Data (Reuse common logic)
    with open(PROFILER_JSON, 'r') as f: prof_data = json.load(f)
    with open(DAILY_JSON, 'r') as f: daily_data = json.load(f)
    
    date_sessions = {}
    if isinstance(prof_data, list): it = prof_data
    else: it = prof_data.values()
    for item in it:
        d = item.get('date'); 
        if not d: continue
        if d not in date_sessions: date_sessions[d] = {}
        date_sessions[d][item['session']] = item.get('status', 'None')

    # Load Pine
    p_asia = unpack_all(parse_pine_array(PINE_FILES['Asia'], "_get_asia_"), 3)
    p_hod_p = parse_pine_array(PINE_FILES['Levels'], "_get_hod_pct_")
    p_lod_p = parse_pine_array(PINE_FILES['Levels'], "_get_lod_pct_")
    p_hod_t = parse_pine_array(PINE_FILES['Times'], "_get_hod_time_")
    p_lod_t = parse_pine_array(PINE_FILES['Times'], "_get_lod_time_")
    
    # Dates
    p_dates_raw = parse_pine_array(PINE_FILES['Asia'], "_get_dates_")
    dates = [f"{str(int(d))[:4]}-{str(int(d))[4:6]}-{str(int(d))[6:]}" for d in p_dates_raw]
    limit = len(dates)
    
    # Slice
    p_asia = p_asia[:limit]
    p_hod_p = p_hod_p[:limit]; p_lod_p = p_lod_p[:limit]
    p_hod_t = p_hod_t[:limit]; p_lod_t = p_lod_t[:limit]
    
    # Build Source Vectors
    s_asia = []
    s_hod_p, s_lod_p, s_hod_t, s_lod_t = [], [], [], []
    
    for d in dates:
        if d not in date_sessions or d not in daily_data:
            s_asia.append(-99)
            s_hod_p.append(0); s_lod_p.append(0)
            s_hod_t.append(0); s_lod_t.append(0)
            continue
            
        sess = date_sessions[d]
        def enc(s):
            s = s.lower()
            if "long" in s: return 1 if "true" in s else 2
            if "short" in s: return 3 if "true" in s else 4
            return 0
            
        s_asia.append(enc(sess.get('Asia', '')))
        
        dm = daily_data[d]
        op = dm.get('daily_open', 0); hp = dm.get('hod_price', 0); lp = dm.get('lod_price', 0)
        s_hod_p.append((hp - op)/op * 100 if op > 0 else 0)
        s_lod_p.append((lp - op)/op * 100 if op > 0 else 0)
        
        def tmn(ts): 
            if not ts: return 0
            h, m = map(int, ts.split(':')) 
            return h*60 + m
        s_hod_t.append(tmn(dm.get('hod_time', '00:00')))
        s_lod_t.append(tmn(dm.get('lod_time', '00:00')))

    # Outcomes
    outcomes = [
        ("Long True", 1),
        ("Long False", 2),
        ("Short True", 3),
        ("Short False", 4)
    ]
    
    def get_stats(vec):
        if not vec: return ["N/A"]*5
        # Min, P25, Med, P75, Max
        try:
            return np.percentile(vec, [0, 25, 50, 75, 100])
        except:
             # Fallback if numpy not avail (but it is in env usually, else simple impl)
             s_v = sorted(vec)
             l = len(s_v)
             return [s_v[0], s_v[int(l*0.25)], s_v[int(l*0.5)], s_v[int(l*0.75)], s_v[-1]]

    def fmt_p(vals):
        return f"{vals[1]:.2f}/{vals[2]:.2f}/{vals[3]:.2f}"
    
    def fmt_t(vals):
        def hm(m): return f"{int(m)//60:02d}:{int(m)%60:02d}"
        return f"{hm(vals[1])}/{hm(vals[2])}/{hm(vals[3])}"

    print(f"{'Outcome':<12} | {'Src/Pine':<9} | {'HOD% (P25/Med/P75)':<20} | {'LOD% (P25/Med/P75)':<20} | {'HOD Time (P25/Med/P75)':<24}")
    print("-" * 120)

    import numpy as np # Ensure import available or move to top

    for label, code in outcomes:
        # PINE
        p_idx = [i for i in range(len(p_asia)) if int(p_asia[i]) == code]
        p_h = [p_hod_p[i] for i in p_idx]; p_l = [p_lod_p[i] for i in p_idx]
        p_ht = [p_hod_t[i] for i in p_idx]
        
        # SOURCE
        s_idx = [i for i in range(len(s_asia)) if s_asia[i] == code]
        s_h = [s_hod_p[i] for i in s_idx]; s_l = [s_lod_p[i] for i in s_idx]
        s_ht = [s_hod_t[i] for i in s_idx]
        
        # Calc
        ps_h = get_stats(p_h); ss_h = get_stats(s_h)
        ps_l = get_stats(p_l); ss_l = get_stats(s_l)
        ps_ht = get_stats(p_ht); ss_ht = get_stats(s_ht)
        
        print(f"{label:<12} | {'Src':<9} | {fmt_p(ss_h):<20} | {fmt_p(ss_l):<20} | {fmt_t(ss_ht):<24}")
        print(f"{'':<12} | {'Pine':<9} | {fmt_p(ps_h):<20} | {fmt_p(ps_l):<20} | {fmt_t(ps_ht):<24}")
        print("-" * 120)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--asia-table":
        generate_asia_table_report()
    elif len(sys.argv) > 2 and sys.argv[1] == "--inspect":
        inspect_scenario(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 20)
    elif len(sys.argv) > 1 and sys.argv[1] == "--combined":
        a = sys.argv[2] if len(sys.argv) > 2 else None
        l = sys.argv[3] if len(sys.argv) > 3 else None
        n = sys.argv[4] if len(sys.argv) > 4 else None
        simulate_combined_filter(a, l, n)
    elif len(sys.argv) > 1 and sys.argv[1] == "--stats":
        generate_stats_report()
    else:
        generate_asia_table_report()
