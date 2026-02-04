
import json
from collections import defaultdict, Counter

# Targets from Ref
NY2_LONG = 2431
NY2_NONE = 78
TARGET_COUNT = 4584

PROFILER_JSON = "data/NQ1_profiler.json"

def solve():
    print(f"Loading profiler...")
    with open(PROFILER_JSON, 'r') as f:
        data_list = json.load(f)
    
    # Organize by Date
    daily = defaultdict(dict)
    for e in data_list:
        daily[e['date']][e['session'].lower()] = e['status']
        
    sorted_dates = sorted(daily.keys())
    
    # Sequence of NY2 outcomes
    # 1: Long, -1: Short, 0: None
    seq = []
    for d in sorted_dates:
        status = daily[d].get('ny2', '').lower()
        if 'long' in status: seq.append(1)
        elif 'short' in status: seq.append(-1)
        else: seq.append(0)
        
    # Sliding window
    curr_long = sum(1 for x in seq[:TARGET_COUNT] if x == 1)
    curr_none = sum(1 for x in seq[:TARGET_COUNT] if x == 0)
    
    print(f"Scanning {len(seq) - TARGET_COUNT + 1} windows...")
    
    candidates = []
    
    for i in range(len(seq) - TARGET_COUNT + 1):
        if curr_none == NY2_NONE and abs(curr_long - NY2_LONG) <= 5:
            candidates.append({
                'start': sorted_dates[i],
                'end': sorted_dates[i+TARGET_COUNT-1],
                'long': curr_long,
                'none': curr_none
            })
            print(f"MATCH FOUND: {sorted_dates[i]} to {sorted_dates[i+TARGET_COUNT-1]} | Long: {curr_long}, None: {curr_none}")
            
        # Slide
        if i < len(seq) - TARGET_COUNT:
            # Out
            out_v = seq[i]
            if out_v == 1: curr_long -= 1
            elif out_v == 0: curr_none -= 1
            # In
            in_v = seq[i + TARGET_COUNT]
            if in_v == 1: curr_long += 1
            elif in_v == 0: curr_none += 1

    print("\n--- Summary ---")
    if not candidates:
        print("No exact NY2_NONE match found.")
    else:
        for c in candidates:
            print(f"{c['start']} -> {c['end']} | Long Diff: {abs(c['long'] - NY2_LONG)}")

if __name__ == "__main__":
    solve()
