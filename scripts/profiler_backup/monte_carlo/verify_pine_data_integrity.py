
import json
import re
from pathlib import Path
import sys

# Paths
DATA_DIR = Path("data")
PINE_DIR = Path("scripts/profiler")

PROFILER_JSON = DATA_DIR / "NQ1_profiler.json"
DAILY_JSON = DATA_DIR / "NQ1_daily_hod_lod.json"

PINE_ASIA = PINE_DIR / "ProfilerData_Asia.pine"
PINE_LEVELS = PINE_DIR / "ProfilerData_Levels.pine"

# Helper to parse Pine array data
def parse_pine_array(file_path, func_name_pattern):
    """
    Parses a Pine Script file and extracts numbers from array.from() calls 
    inside functions matching the pattern (e.g., '_get_asia_').
    """
    if not file_path.exists():
        print(f"Error: {file_path} not found.")
        return []

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find all chunks: _get_asia_0() => \n    array.from(1, 2, 3...)
    # Regex to find the function body containing array.from
    # logic: find function def, then capture content inside array.from(...)
    
    # We expect multiple functions like _get_asia_0, _get_asia_1...
    # We need to extract them IN ORDER.
    
    # Simple regex to find "array.from( ... )" doesn't guarantee order if we just findall.
    # But usually they act in file order.
    
    # Better approach: Find all `_get_<name>_<idx>()` and sort by idx.
    
    # 1. capture (func_name, args)
    regex = re.compile(r'(\w+)\(\) =>\s+array\.from\(([\d\., \-\+e]+)\)')
    matches = regex.findall(content)
    
    # Filter by pattern
    relevant_matches = []
    for m in matches:
        fname = m[0] # e.g. _get_asia_0
        data_str = m[1]
        
        if func_name_pattern in fname:
            # Extract index
            parts = fname.split('_')
            try:
                idx = int(parts[-1])
                relevant_matches.append((idx, data_str))
            except:
                pass
                
    # Sort by index
    relevant_matches.sort(key=lambda x: x[0])
    
    final_data = []
    for _, d_str in relevant_matches:
        # split by comma
        vals = [float(x.strip()) for x in d_str.split(',')]
        final_data.extend(vals)
        
    return final_data

def decode_status(code):
    # 0=None, 1=LT, 2=LF, 3=ST, 4=SF
    mapping = {0: "None", 1: "Long True", 2: "Long False", 3: "Short True", 4: "Short False"}
    return mapping.get(int(code), "Unknown")

def run_verification():
    print(f"Loading JSON Sources...")
    try:
        with open(PROFILER_JSON, 'r') as f:
            prof_data = json.load(f)
        with open(DAILY_JSON, 'r') as f:
            daily_data = json.load(f)
    except Exception as e:
        print(f"Failed to load JSON: {e}")
        return

    # Prepare Source Data (Mirroring Generator Logic)
    # Join on Date
    source_rows = []
    
    # 1. Map Profiler Data
    prof_map = {}
    if isinstance(prof_data, list): iter_prof = prof_data
    else: iter_prof = prof_data.values()
    
    for item in iter_prof:
        d = item.get('date')
        if not d: continue
        # Generator uses int(date.replace('-', '')) logic for sorting usually, 
        # let's stick to string date for joining, but sort later.
        if item.get('session') == 'Asia':
            prof_map[d] = item

    # 2. Map Daily Data
    daily_map = daily_data # Dictionary keyed by date string
    
    # 3. Join & Sort keys
    all_dates = sorted(list(set(prof_map.keys()) & set(daily_map.keys())))
    
    print(f"Found {len(all_dates)} matching dates in Source JSONs.")
    
    # Extract Source Values
    src_statuses = []
    src_hod_p = []
    
    for d in all_dates:
        # Status
        p_item = prof_map[d]
        raw_status = p_item.get('status', 'None')
        # Encode to match Pine (1..4)
        # Generator encode_status logic:
        # if "long" in s: return 1 if "true" in s else 2 ...
        s_lower = raw_status.lower()
        code = 0
        if "long" in s_lower: code = 1 if "true" in s_lower else 2
        elif "short" in s_lower: code = 3 if "true" in s_lower else 4
        
        src_statuses.append(code)
        
        # HOD Pct
        d_item = daily_map[d]
        d_open = d_item.get('daily_open', 0)
        d_high = d_item.get('hod_price', 0)
        
        if d_open and d_open > 0:
            hp = round((d_high - d_open) / d_open * 100, 2)
        else:
            hp = 0.0
        src_hod_p.append(hp)
        
    print(f"Extracted {len(src_statuses)} rows from Source.")

    # --- Load Pine Data ---
    print(f"Parsing Pine Files...")
    
    # Asia Status is in ProfilerData_Asia.pine, encoded in '_get_asia_' chunks
    # Note: Generator uses 'asia' array for Status Codes (3-bit)
    pine_asia_raw = parse_pine_array(PINE_ASIA, "_get_asia_")
    
    # HOD Pct is in ProfilerData_Levels.pine, encoded in '_get_hod_pct_' chunks
    pine_hod_raw = parse_pine_array(PINE_LEVELS, "_get_hod_pct_")
    
    print(f"Pine Asia Array Size: {len(pine_asia_raw)}")
    print(f"Pine HOD Array Size: {len(pine_hod_raw)}")
    
    # --- Comparison ---
    # Length Check
    min_len = min(len(src_statuses), len(pine_asia_raw), len(pine_hod_raw))
    print(f"\nComparing first {min_len} records (Sampled)...")
    
    print("-" * 100)
    print(f"{'Date':<12} | {'Src Status':<12} | {'Pine Code':<10} | {'Match?':<6} | {'Src HOD%':<10} | {'Pine HOD%':<10} | {'Match?':<6}")
    print("-" * 100)
    
    mismatch_count_s = 0
    mismatch_count_h = 0
    
    # Validate entire dataset logic
    for i in range(min_len):
        d_str = all_dates[i]
        
        # Status
        s_src = src_statuses[i]
        s_pine = int(pine_asia_raw[i]) # Pine float to int
        match_s = "OK" if s_src == s_pine else "FAIL"
        if s_src != s_pine: is_fail = True; mismatch_count_s += 1
        
        # HOD
        h_src = src_hod_p[i]
        h_pine = pine_hod_raw[i]
        # Float tolerance
        match_h = "OK" if abs(h_src - h_pine) < 0.001 else "FAIL"
        if match_h == "FAIL": mismatch_count_h += 1
        
        # Print Sample (First 10, Last 10, and any Failures)
        if i < 10 or i > min_len - 10 or match_s == "FAIL" or match_h == "FAIL":
             print(f"{d_str:<12} | {decode_status(s_src):<12} | {s_pine:<10} | {match_s:<6} | {h_src:<10.2f} | {h_pine:<10.2f} | {match_h:<6}")

    print("-" * 100)
    print(f"Total Status Mismatches: {mismatch_count_s} / {min_len}")
    print(f"Total HOD % Mismatches : {mismatch_count_h} / {min_len}")
    
    sys.stdout.flush()

if __name__ == "__main__":
    run_verification()
