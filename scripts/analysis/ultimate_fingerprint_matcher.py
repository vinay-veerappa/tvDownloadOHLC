
import json
from collections import defaultdict

# Target from Reference Data
TARGET_COUNT = 4584
TARGETS = {
    "asia_long": 2325, "asia_short": 2091, "asia_none": 168,
    "asia_broken": 3780, "asia_complete": 804,
    "london_long": 2299, "london_short": 2203, "london_none": 82,
    "london_broken": 3674, "london_complete": 910,
    "ny1_long": 2326, "ny1_short": 2253, "ny1_none": 5,
    "ny1_broken": 2182, "ny1_complete": 2402
}

PROFILER_JSON = "data/NQ1_profiler.json"

def solve():
    print(f"Loading session stats from {PROFILER_JSON}...")
    with open(PROFILER_JSON, 'r') as f:
        list_data = json.load(f)
    
    # 1. Aggregate to Daily Summary
    daily_stats = defaultdict(lambda: {
        "asia_dir": "none", "asia_broken": False,
        "london_dir": "none", "london_broken": False,
        "ny1_dir": "none", "ny1_broken": False
    })
    
    for entry in list_data:
        d = entry['date']
        session = entry['session'].lower()
        if session not in ["asia", "london", "ny1"]:
            continue
            
        status = entry.get('status', '').lower()
        direction = "none"
        if "long" in status: direction = "long"
        elif "short" in status: direction = "short"
        
        broken = entry.get('broken', False)
        
        daily_stats[d][f"{session}_dir"] = direction
        daily_stats[d][f"{session}_broken"] = broken
        
    sorted_dates = sorted(daily_stats.keys())
    print(f"Total trading days available: {len(sorted_dates)}")
    
    # 2. Pre-calculate fingerprint sequences
    seq = []
    for d in sorted_dates:
        ds = daily_stats[d]
        seq.append({
            "asia_long": 1 if ds['asia_dir'] == "long" else 0,
            "asia_short": 1 if ds['asia_dir'] == "short" else 0,
            "asia_none": 1 if ds['asia_dir'] == "none" else 0,
            "asia_broken": 1 if ds['asia_broken'] else 0,
            "asia_complete": 1 if not ds['asia_broken'] else 0,
            
            "london_long": 1 if ds['london_dir'] == "long" else 0,
            "london_short": 1 if ds['london_dir'] == "short" else 0,
            "london_none": 1 if ds['london_dir'] == "none" else 0,
            "london_broken": 1 if ds['london_broken'] else 0,
            "london_complete": 1 if not ds['london_broken'] else 0,
            
            "ny1_long": 1 if ds['ny1_dir'] == "long" else 0,
            "ny1_short": 1 if ds['ny1_dir'] == "short" else 0,
            "ny1_none": 1 if ds['ny1_dir'] == "none" else 0,
            "ny1_broken": 1 if ds['ny1_broken'] else 0,
            "ny1_complete": 1 if not ds['ny1_broken'] else 0
        })

    # 3. Sliding Window Fingerprint Search
    curr_counts = defaultdict(int)
    # Init first window
    for i in range(TARGET_COUNT):
        for k, v in seq[i].items():
            curr_counts[k] += v
            
    best_err = float('inf')
    best_window = None
    
    print(f"Searching {len(seq) - TARGET_COUNT} windows for fingerprint match...")
    
    for i in range(len(seq) - TARGET_COUNT + 1):
        err = 0
        for k, target_v in TARGETS.items():
            err += abs(curr_counts[k] - target_v)
            
        if err < best_err:
            best_err = err
            best_window = (sorted_dates[i], sorted_dates[i+TARGET_COUNT-1])
            print(f"New Best: {best_window[0]} to {best_window[1]} (Error Points: {err})")
            
        if err == 0:
            print("\n>>> CRITICAL HIT: EXACT FINGERPRINT MATCH FOUND! <<<")
            print(f"Precise Date Range: {best_window[0]} to {best_window[1]}")
            break
            
        # Slide
        if i < len(seq) - TARGET_COUNT:
            # Out
            for k, v in seq[i].items():
                curr_counts[k] -= v
            # In
            for k, v in seq[i + TARGET_COUNT].items():
                curr_counts[k] += v

    print("\nSearch Completed.")
    print(f"Resulting Period: {best_window[0]} to {best_window[1]} (Min Error: {best_err})")

if __name__ == "__main__":
    solve()
