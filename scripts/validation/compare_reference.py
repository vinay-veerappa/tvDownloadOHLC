
import json
import os
from collections import defaultdict

def parse_time_str(t_str):
    try:
        h, m = map(int, t_str.split(':'))
        return h * 60 + m
    except:
        return -1

def bucket_times(time_list, granular=5):
    hist = defaultdict(int)
    for t_val in time_list:
        val = int(t_val)
        bucket = (val // granular) * granular
        hist[str(bucket)] = hist[str(bucket)] + 1
    return hist

def run():
    ref_path = r"c:\Users\vinay\tvDownloadOHLC\docs\ReferenceDailyLevels.json"
    my_path = r"c:\Users\vinay\tvDownloadOHLC\data\NQ1_level_stats.json"

    if not os.path.exists(ref_path):
        print(f"Reference file not found: {ref_path}")
        return
    if not os.path.exists(my_path):
        print(f"My stats file not found: {my_path}")
        return

    with open(ref_path, 'r') as f:
        ref_data = json.load(f)
    
    with open(my_path, 'r') as f:
        my_data = json.load(f)

    # We compare Ref['ny'] with My['All']
    ref_target = ref_data.get('ny', {})
    my_all = my_data.get('All', {})
    
    # Offset: 480 mins (08:00 start)
    OFFSET = 480 

    key_map = {
        "pdh": "PDH",
        "pdl": "PDL",
        "pdm": "PDMid",
        "midnight_open": "MidnightOpen",
        "globex_open": "GlobexOpen"
    }

    # DEBUG SECTION
    print("DEBUG: My Keys:", list(my_all.keys()))
    if "PDH" in my_all:
        pdh_data = my_all["PDH"]
        print(f"DEBUG: PDH Keys: {list(pdh_data.keys())}")
        print(f"DEBUG: PDH Hits: {pdh_data.get('hits')}")
        times = pdh_data.get('times', [])
        print(f"DEBUG: PDH Times Count: {len(times)}")
        print(f"DEBUG: PDH Times Sample: {times[:10]}")
    # END DEBUG

    print(f"{'Level':<15} | {'Ref (NY) Hits':<15} | {'My (NY1) Hits':<15} | {'Diff':<10} | {'Top Ref Bucket':<15} | {'Top My Bucket':<15}")
    print("-" * 100)

    for ref_k, my_k in key_map.items():
        if ref_k not in ref_target or my_k not in my_all:
            continue
        
        ref_hist_raw = ref_target[ref_k] 
        ref_total = sum(ref_hist_raw.values())
        
        my_times_raw = my_all[my_k].get('times', [])
        my_total = len(my_times_raw)
        
        my_times_shifted = [t + OFFSET for t in my_times_raw]
        my_hist = bucket_times(my_times_shifted, granular=5)

        ref_peak = max(ref_hist_raw.items(), key=lambda x: x[1]) if ref_hist_raw else ("-", 0)
        my_peak = max(my_hist.items(), key=lambda x: x[1]) if my_hist else ("-", 0)
        
        ref_peak_str = f"{ref_peak[0]} ({ref_peak[1]})"
        my_peak_str = f"{my_peak[0]} ({my_peak[1]})"

        print(f"{my_k:<15} | {ref_total:<15} | {my_total:<15} | {my_total - ref_total:<10} | {ref_peak_str:<15} | {my_peak_str:<15}")

        if my_k == "PDH":
            print("\n--- Detailed PDH Histogram Comparison (Top 5 Diff) ---")
            all_buckets = set(ref_hist_raw.keys()) | set(my_hist.keys())
            diffs = []
            for b in all_buckets:
                r_val = ref_hist_raw.get(b, 0)
                m_val = my_hist.get(b, 0)
                diff = m_val - r_val
                if diff != 0:
                    diffs.append((b, r_val, m_val, diff))
            
            diffs.sort(key=lambda x: abs(x[3]), reverse=True)
            for b, r, m, d in diffs[:10]:
                print(f"Bucket {b}: Ref={r}, My={m}, Diff={d}")
            print("------------------------------------------------------\n")

if __name__ == "__main__":
    run()
