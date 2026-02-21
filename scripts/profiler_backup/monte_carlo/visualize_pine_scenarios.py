import json
import os
import sys
import matplotlib.pyplot as plt
import numpy as np

# Adjust path to find modules if needed, or just run from root
# We need the parsing logic. Explicitly copying relevant parts to ensure standalone execution without dependency hell.

BASE_DIR = r"c:\Users\vinay\tvDownloadOHLC"
DATA_DIR = os.path.join(BASE_DIR, "data")
SCRIPTS_DIR = os.path.join(BASE_DIR, "scripts", "profiler")
PINE_FILES = {
    'Asia': os.path.join(SCRIPTS_DIR, "ProfilerData_Asia.pine"),
    'London': os.path.join(SCRIPTS_DIR, "ProfilerData_London.pine"),
    'NY': os.path.join(SCRIPTS_DIR, "ProfilerData_NY.pine"),
    'Levels': os.path.join(SCRIPTS_DIR, "ProfilerData_Levels.pine"),
    'Times': os.path.join(SCRIPTS_DIR, "ProfilerData_Times.pine")
}
PROFILER_JSON = os.path.join(DATA_DIR, "NQ1_profiler.json")
DAILY_JSON = os.path.join(DATA_DIR, "NQ1_daily_hod_lod.json")
ARTIFACTS_DIR = r"c:\Users\vinay\.gemini\antigravity\brain\3e5d7058-e84e-4d5d-9db3-c5426dd9f917"

def parse_pine_array(filepath, var_name_fragment):
    data = []
    import re
    # matches: array.from(1,2,3)
    # But files might be split across multiple functions _get_asia_0, _get_asia_1
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # Find all function bodies that contain the var_name
    # Actually checking for "_get_asia_" in function names usually
    # Pattern: _get_asia_0() => \n    array.from(val, val...)
    
    # Simple regex to find all array.from(...) contents inside relevant blocks?
    # Better: find lines with array.from( and check context? 
    # Or just extract ALL array.from inside the file if the file is dedicated?
    # The files are dedicated libraries. _get_asia_0, _get_asia_1 etc.
    
    # We want strict matching to the variable type requested?
    # All requested files seem to have specific data.
    
    # Let's iterate functions matching the fragment
    func_pattern = re.compile(r"func\s+" + re.escape(var_name_fragment) + r"\d+\(\)\s*=>\s*array\.from\(([\d.,\s-]+)\)", re.MULTILINE)
    # Actually Pine syntax: _get_asia_0() =>
    
    # Regex to capture all numbers inside array.from(...)
    # We can iterate line by line.
    
    in_target_func = False
    full_vals = []
    
    lines = content.split('\n')
    for line in lines:
        if var_name_fragment in line and "=>" in line:
            in_target_func = True
            continue
        
        if in_target_func and "array.from" in line:
            # Extract content between parens
            start = line.find('(')
            end = line.rfind(')')
            if start != -1 and end != -1:
                vals_str = line[start+1:end]
                # Split by comma
                vals = [float(x.strip()) for x in vals_str.split(',') if x.strip()]
                full_vals.extend(vals)
            in_target_func = False # One liner usually?
            # If multiline, pine usually indents. But our generator writes one huge line usually or limited lines.
            
    return full_vals

def unpack_all(packed_arr, bits):
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

def load_data():
    print("Loading Data...")
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

    # Pine Data
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
    
    # Source Data
    s_asia, s_hod_p, s_lod_p, s_hod_t, s_lod_t = [], [], [], [], []
    
    for d in dates:
        if d not in date_sessions or d not in daily_data:
            s_asia.append(-99)
            s_hod_p.append(-99); s_lod_p.append(-99)
            s_hod_t.append(-99); s_lod_t.append(-99)
            continue
            
        sess = date_sessions[d]
        s_raw = sess.get('Asia', '').lower()
        code = 0
        if "long" in s_raw: code = 1 if "true" in s_raw else 2
        elif "short" in s_raw: code = 3 if "true" in s_raw else 4
        s_asia.append(code)
        
        dm = daily_data[d]
        op = dm.get('daily_open', 0)
        s_hod_p.append((dm.get('hod_price',0)-op)/op*100 if op>0 else 0)
        s_lod_p.append((dm.get('lod_price',0)-op)/op*100 if op>0 else 0)
        
        def tmn(ts):
            if not ts: return 0
            h, m = map(int, ts.split(':'))
            return h*60 + m
        s_hod_t.append(tmn(dm.get('hod_time', '00:00')))
        s_lod_t.append(tmn(dm.get('lod_time', '00:00')))
        
    return {
        'dates': dates,
        'p': {'asia': p_asia, 'hp': p_hod_p, 'lp': p_lod_p, 'ht': p_hod_t, 'lt': p_lod_t},
        's': {'asia': s_asia, 'hp': s_hod_p, 'lp': s_lod_p, 'ht': s_hod_t, 'lt': s_lod_t}
    }

def plot_comparison(data):
    # Outcomes
    outcomes = {
        1: "Long True",
        2: "Long False",
        3: "Short True",
        4: "Short False"
    }
    
    p = data['p']
    s = data['s']
    
    for code, name in outcomes.items():
        print(f"Generating plot for {name}...")
        
        # Filter Data
        # Filter BOTH by indices where PINE matches code (Simulating Pine Logic) 
        # vs indices where SOURCE matches code (Simulating Source Logic)
        # Ideally, indices are identical if data is matched.
        
        p_idx = [i for i, x in enumerate(p['asia']) if int(x) == code]
        s_idx = [i for i, x in enumerate(s['asia']) if x == code]
        
        # Prepare Vectors
        p_hp = [p['hp'][i] for i in p_idx]
        s_hp = [s['hp'][i] for i in s_idx]
        
        p_lp = [p['lp'][i] for i in p_idx]
        s_lp = [s['lp'][i] for i in s_idx]
        
        def filter_times(vec): return [x/60.0 for x in vec if x > 0] # Convert to hours
        p_ht = filter_times([p['ht'][i] for i in p_idx])
        s_ht = filter_times([s['ht'][i] for i in s_idx])
        
        p_lt = filter_times([p['lt'][i] for i in p_idx])
        s_lt = filter_times([s['lt'][i] for i in s_idx])
        
        # Plotting
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle(f"Logic Verification: Asia {name} (Pine vs Source)", fontsize=16)
        
        # 1. HOD % Dist
        ax = axes[0,0]
        ax.hist(s_hp, bins=50, alpha=0.5, label=f'Source (n={len(s_hp)})', density=True, color='blue')
        ax.hist(p_hp, bins=50, alpha=0.5, label=f'Pine (n={len(p_hp)})', density=True, color='orange')
        ax.set_title("HOD % Distribution")
        ax.legend()
        
        # 2. LOD % Dist
        ax = axes[0,1]
        ax.hist(s_lp, bins=50, alpha=0.5, label=f'Source', density=True, color='blue')
        ax.hist(p_lp, bins=50, alpha=0.5, label=f'Pine', density=True, color='orange')
        ax.set_title("LOD % Distribution")
        
        # 3. HOD Time
        ax = axes[1,0]
        if s_ht and p_ht:
            ax.hist(s_ht, bins=48, range=(0, 24), alpha=0.5, label='Source', density=True, color='blue')
            ax.hist(p_ht, bins=48, range=(0, 24), alpha=0.5, label='Pine', density=True, color='orange')
        ax.set_title("HOD Time of Day (Hours)")
        ax.set_xticks(range(0, 25, 2))
        
        # 4. LOD Time
        ax = axes[1,1]
        if s_lt and p_lt:
            ax.hist(s_lt, bins=48, range=(0, 24), alpha=0.5, label='Source', density=True, color='blue')
            ax.hist(p_lt, bins=48, range=(0, 24), alpha=0.5, label='Pine', density=True, color='orange')
        ax.set_title("LOD Time of Day (Hours)")
        ax.set_xticks(range(0, 25, 2))
        
        # Save
        fname = f"comparison_asia_{name.lower().replace(' ', '_')}.png"
        out_path = os.path.join(ARTIFACTS_DIR, fname)
        plt.tight_layout()
        plt.savefig(out_path)
        plt.close()
        print(f"Saved: {out_path}")

if __name__ == "__main__":
    d = load_data()
    plot_comparison(d)
