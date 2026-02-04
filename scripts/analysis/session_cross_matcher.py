
import json

# Target from Reference Data
TARGETS = {
    "asia_long": 2325,
    "asia_short": 2091,
    "london_long": 2299,
    "london_short": 2203,
    "ny1_long": 2326,
    "ny1_short": 2253
}
TARGET_COUNT = 4584

PROFILER_JSON = "data/NQ1_profiler.json"

def solve():
    print(f"Loading session stats from {PROFILER_JSON}...")
    with open(PROFILER_JSON, 'r') as f:
        data = json.load(f)
    
    sorted_dates = sorted(data.keys())
    print(f"Total days in profiler: {len(sorted_dates)}")
    
    # Pre-calculate sequences
    # Asia Direction: 1 for Long, -1 for Short, 0 for None
    asia_seq = []
    london_seq = []
    ny1_seq = []
    
    for d in sorted_dates:
        s = data[d]['sessions']
        
        # Mapping: Ref uses 'long', 'short'. Our JSON check:
        # We need to know where direction is stored. 
        # Usually it's in sessions[session_name]['outcome'] or similar.
        a = s.get('asia', {})
        l = s.get('london', {})
        n = s.get('ny1', {})
        
        # Outcome logic: 
        # If 'Long True' or 'Long False' -> Direction is Long.
        # If 'Short True' or 'Short False' -> Direction is Short.
        def get_dir(sess):
            status = sess.get('status', '').lower()
            if 'long' in status: return 'long'
            if 'short' in status: return 'short'
            return 'none'
            
        asia_seq.append(get_dir(a))
        london_seq.append(get_dir(l))
        ny1_seq.append(get_dir(n))

    print(f"Scanning windows...")
    
    # Sliding counts
    curr = {
        "asia_long": 0, "asia_short": 0,
        "london_long": 0, "london_short": 0,
        "ny1_long": 0, "ny1_short": 0
    }
    
    # Initialize first window
    for i in range(TARGET_COUNT):
        def add(d, prefix):
            if d == 'long': curr[f"{prefix}_long"] += 1
            elif d == 'short': curr[f"{prefix}_short"] += 1
            
        add(asia_seq[i], "asia")
        add(london_seq[i], "london")
        add(ny1_seq[i], "ny1")

    best_err = float('inf')
    best_results = []

    for i in range(len(sorted_dates) - TARGET_COUNT + 1):
        err = 0
        for k, v in TARGETS.items():
            err += abs(curr[k] - v)
            
        if err < best_err:
            best_err = err
            res = {
                'start': sorted_dates[i],
                'end': sorted_dates[i+TARGET_COUNT-1],
                'error': err,
                'state': curr.copy()
            }
            best_results.append(res)
            print(f"New Best Window Match: {res['start']} to {res['end']} (Total Error: {err})")
            
        if err == 0:
            print(">>> PERFECT SESSION MATCH FOUND! <<<")
            break
            
        # Slide
        if i < len(sorted_dates) - TARGET_COUNT:
            def sub(d, prefix):
                if d == 'long': curr[f"{prefix}_long"] -= 1
                elif d == 'short': curr[f"{prefix}_short"] -= 1
            def add(d, prefix):
                if d == 'long': curr[f"{prefix}_long"] += 1
                elif d == 'short': curr[f"{prefix}_short"] += 1
            
            sub(asia_seq[i], "asia")
            sub(london_seq[i], "london")
            sub(ny1_seq[i], "ny1")
            
            add(asia_seq[i + TARGET_COUNT], "asia")
            add(london_seq[i + TARGET_COUNT], "london")
            add(ny1_seq[i + TARGET_COUNT], "ny1")

    print("\nSearch Completed.")
    # Show last few bests
    for r in best_results[-3:]:
        print(f"\nWindow: {r['start']} to {r['end']}")
        print(f"Error: {r['error']}")
        print(f"Stats: {r['state']}")

if __name__ == "__main__":
    solve()
