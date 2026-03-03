import json
import os
from collections import defaultdict

DATA_FILE = r"C:\Users\vinay\tvDownloadOHLC\data\NQ1_profiler.json"

def main():
    if not os.path.exists(DATA_FILE):
        print(f"File not found: {DATA_FILE}")
        return

    with open(DATA_FILE, 'r') as f:
        sessions = json.load(f)
        
    print(f"Loaded {len(sessions)} total sessions.")

    # Group sessions by date and calculate previous day context
    days = defaultdict(dict)
    
    for s in sessions:
        if 'date' in s and 'session' in s and 'status' in s:
            days[s['date']][s['session']] = s['status']
        
    sorted_dates = sorted(list(days.keys()))
    
    # Context trackers
    asia_contexts = defaultdict(int)
    london_contexts = defaultdict(int)
    ny1_contexts = defaultdict(int)
    ny2_contexts = defaultdict(int)
    
    MIN_SAMPLE_SIZE = 5

    for i in range(1, len(sorted_dates)):
        prev_date = sorted_dates[i-1]
        curr_date = sorted_dates[i]
        
        prev_day = days[prev_date]
        curr_day = days[curr_date]
        
        prev_ny1 = prev_day.get('NY1', 'None')
        prev_ny2 = prev_day.get('NY2', 'None')
        
        curr_asia = curr_day.get('Asia', 'None')
        curr_lon = curr_day.get('London', 'None')
        curr_ny1 = curr_day.get('NY1', 'None')
        curr_ny2 = curr_day.get('NY2', 'None')
        
        # 1. Asia: Context = Prev NY1 + Prev NY2
        if curr_asia not in ['None', 'Broken', 'Neutral']:
            key = f"{prev_ny1}|{prev_ny2}|{curr_asia}"
            asia_contexts[key] += 1
            
        # 2. London: Context = Asia + Prev NY2
        if curr_lon not in ['None', 'Broken', 'Neutral']:
            key = f"{curr_asia}|{prev_ny2}|{curr_lon}"
            london_contexts[key] += 1
            
        # 3. NY1: Context = Asia + London
        if curr_ny1 not in ['None', 'Broken', 'Neutral']:
            key = f"{curr_asia}|{curr_lon}|{curr_ny1}"
            ny1_contexts[key] += 1
            
        # 4. NY2: Context = Asia + London + NY1
        if curr_ny2 not in ['None', 'Broken', 'Neutral']:
            key = f"{curr_asia}|{curr_lon}|{curr_ny1}|{curr_ny2}"
            ny2_contexts[key] += 1

    print("\n=== THEORETICAL MAX VS ACTUAL IN HISTORY (ANY COUNT) ===")
    
    print(f"Asia (PrevNY1, PrevNY2): {len(asia_contexts)} unique paths")
    print(f"London (Asia, PrevNY2): {len(london_contexts)} unique paths")
    print(f"NY1 (Asia, London): {len(ny1_contexts)} unique paths")
    print(f"NY2 (Asia, London, NY1): {len(ny2_contexts)} unique paths")
    print(f"TOTAL MODELS IN HISTORY: {len(asia_contexts) + len(london_contexts) + len(ny1_contexts) + len(ny2_contexts)}")
    
    print(f"\n=== STATISTICALLY VIABLE MODELS (COUNT >= {MIN_SAMPLE_SIZE}) ===")
    
    valid_asia = [k for k, v in asia_contexts.items() if v >= MIN_SAMPLE_SIZE]
    valid_lon = [k for k, v in london_contexts.items() if v >= MIN_SAMPLE_SIZE]
    valid_ny1 = [k for k, v in ny1_contexts.items() if v >= MIN_SAMPLE_SIZE]
    valid_ny2 = [k for k, v in ny2_contexts.items() if v >= MIN_SAMPLE_SIZE]
    
    print(f"Asia (PrevNY1, PrevNY2): {len(valid_asia)} viable models")
    print(f"London (Asia, PrevNY2): {len(valid_lon)} viable models")
    print(f"NY1 (Asia, London): {len(valid_ny1)} viable models")
    print(f"NY2 (Asia, London, NY1): {len(valid_ny2)} viable models")
    print(f"TOTAL VIABLE MODELS TO GENERATE: {len(valid_asia) + len(valid_lon) + len(valid_ny1) + len(valid_ny2)}")

if __name__ == "__main__":
    main()
