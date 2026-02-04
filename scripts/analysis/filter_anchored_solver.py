
import json
import math
from collections import defaultdict, Counter

# Configuration
PROFILER_JSON = "data/NQ1_profiler.json"
REF_JSON = "data/analysis/reference_data_full.json"
TARGET_MATCHES = 37 # The user's ref had 37 matches for the filter
TARGET_COUNT = 4584

def get_bucket(val):
    if val is None or val < 0: return 0.0
    b = math.floor(round(val, 4) * 10) / 10.0
    return b if b < 5.0 else 5.0

def calc_stats(my, ref):
    max_d = 0
    all_k = set(my.keys()) | set(ref.keys())
    for k in all_k:
        max_d = max(max_d, abs(my.get(k, 0) - ref.get(k, 0)))
    return max_d

def solve():
    print(f"Loading profiler data...")
    with open(PROFILER_JSON, 'r') as f:
        data_list = json.load(f)
    
    # 1. Daily Aggregation with Filter Logic
    # Criteria: Asia(LF+Broken) -> London(LT) -> NY1(LT)
    daily = defaultdict(lambda: {"h_pct": 0, "l_pct": 0, "match": False, "s": {}})
    for e in data_list:
        d = e['date']
        sess = e['session'].lower()
        daily[d]['s'][sess] = e
        if sess == 'ny2': # Use NY2 as proxy for Daily High from open (or just high_pct)
            # Actually, the unadjusted data is the source for High
            # But the profiler has high_pct from the unadjusted data already (if it was regenerated)
            pass

    # Load Unadjusted for precise buckets
    with open("data/NQ1_daily_hod_lod_unadjusted.json", 'r') as f:
        unadj = json.load(f)

    sorted_dates = sorted(daily.keys())
    day_seq = []
    
    for d in sorted_dates:
        entry = daily[d]
        s = entry['s']
        
        # Filter Logic
        # Asia LF+Broken
        a = s.get('asia', {})
        l = s.get('london', {})
        n1 = s.get('ny1', {})
        
        is_match = False
        if a.get('status') == 'Long False' and a.get('broken') == True:
            if l.get('status') == 'Long True':
                if n1.get('status') == 'Long True':
                    is_match = True
        
        # Bucket Data
        u = unadj.get(d, {})
        h_b = 0.0
        l_b = 0.0
        if u:
            op = u['daily_open']
            if op > 0:
                h_b = get_bucket((u['daily_high'] - op) / op * 100)
                l_b = get_bucket(abs((u['daily_low'] - op) / op * 100))
        
        day_seq.append({
            'd': d,
            'match': 1 if is_match else 0,
            'h': h_b,
            'l': l_b
        })

    # 2. Search for windows matching Filter Count and minimizing Bucket MaxDiff
    with open(REF_JSON, 'r') as f:
        ref_data = json.load(f)
    ref_h = {float(k): v for k, v in ref_data['distributions']['daily']['high'].items()}
    ref_l = {float(abs(float(k))): v for k, v in ref_data['distributions']['daily']['low'].items()}

    curr_matches = sum(x['match'] for x in day_seq[:TARGET_COUNT])
    curr_h = Counter(x['h'] for x in day_seq[:TARGET_COUNT])
    curr_l = Counter(x['l'] for x in day_seq[:TARGET_COUNT])
    
    best_results = []
    
    print(f"Scanning {len(day_seq) - TARGET_COUNT + 1} windows...")
    
    for i in range(len(day_seq) - TARGET_COUNT + 1):
        # We only consider windows where the filter count is close to 37
        # (Allowing a small margin if the filter logic changed slightly)
        if abs(curr_matches - TARGET_MATCHES) <= 2:
            mh = calc_stats(curr_h, ref_h)
            ml = calc_stats(curr_l, ref_l)
            max_d = max(mh, ml)
            
            best_results.append({
                'start': day_seq[i]['d'],
                'end': day_seq[i+TARGET_COUNT-1]['d'],
                'matches': curr_matches,
                'max_diff': max_d
            })
            
            if max_d <= 5:
                print(f"HIGH PRECISION CANDIDATE: {day_seq[i]['d']} to {day_seq[i+TARGET_COUNT-1]['d']} (Matches: {curr_matches}, MaxDiff: {max_d})")

        # Slide
        if i < len(day_seq) - TARGET_COUNT:
            # Out
            curr_matches -= day_seq[i]['match']
            curr_h[day_seq[i]['h']] -= 1
            if curr_h[day_seq[i]['h']] == 0: del curr_h[day_seq[i]['h']]
            curr_l[day_seq[i]['l']] -= 1
            if curr_l[day_seq[i]['l']] == 0: del curr_l[day_seq[i]['l']]
            # Oops loop variable error l_buckets[i]
            # Fix: day_seq[i]['l'] 
            
            # In
            curr_matches += day_seq[i+TARGET_COUNT]['match']
            curr_h[day_seq[i+TARGET_COUNT]['h']] += 1
            curr_l[day_seq[i+TARGET_COUNT]['l']] += 1

    print("\n--- Filter-Anchored Top Results ---")
    top = sorted(best_results, key=lambda x: (x['max_diff']))[:20]
    for r in top:
        print(f"{r['start']} to {r['end']} | Matches: {r['matches']} | MaxDiff: {r['max_diff']}")

if __name__ == "__main__":
    solve()
