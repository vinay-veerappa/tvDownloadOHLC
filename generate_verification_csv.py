import pandas as pd
import json
from pathlib import Path

# Paths
DATA_DIR = Path('data')
USER_JSON = DATA_DIR / 'NQ1_level_touches.json'
REF_JSON = DATA_DIR / '../docs/ReferenceDailyLevels.json' # Adjust path if needed
OUTPUT_DIR = DATA_DIR / 'csv_reports'
OUTPUT_DIR.mkdir(exist_ok=True)

def bucket_time(time_str):
    """Convert HH:MM to 5-minute bucket string (e.g. 09:32 -> 570 minutes from 00:00 -> mapped to key?)"""
    # Reference uses MINUTES FROM 00:00? Or MINUTES FROM 18:00?
    # Let's inspect Reference keys. e.g. "480" for 08:00?
    # 480 / 60 = 8.0. So Reference keys are "Minutes from 00:00".
    
    h, m = map(int, time_str.split(':'))
    minutes_from_midnight = h * 60 + m
    
    # Bucket to nearest 5
    bucket = (minutes_from_midnight // 5) * 5
    return str(bucket)

def min_to_time(minutes_str):
    """Convert '480' to '08:00'"""
    m = int(minutes_str)
    h = (m // 60) % 24
    mm = m % 60
    return f"{h:02d}:{mm:02d}"

def generate_verification():
    print("Loading data...")
    with open(USER_JSON, 'r') as f:
        user_data = json.load(f)
        
    with open(REF_JSON, 'r') as f:
        ref_data = json.load(f)

    # Levels to compare: P12 High, PD Mid, Midnight Open
    # Map User Keys -> Ref Keys
    # User keys: p12h, pdm, midnight_open
    # Ref keys (in 'ny' or 'all'?): 
    # Ref 'ny': p12_high, pd_mid, midnight_open?
    # Let's assume common mapping:
    
    level_map = {
        'p12h': 'p12_high',
        'pdm': 'pd_mid',
        'midnight_open': 'midnight_open'
    }
    
    # Initialize Counters
    # All Day: 00:00 to 23:59? (Reference likely 00:00-...)
    # NY1: 08:00 to 12:00
    
    stats_all = {k: {} for k in level_map}
    stats_ny1 = {k: {} for k in level_map}
    
    print("Processing User Data...")
    for date_str, data in user_data.items():
        for user_key, ref_key in level_map.items():
            if user_key not in data: continue
            
            entry = data[user_key]
            # touch_times is list of HH:MM
            times = entry.get('touch_times', [])
            
            # touch_times is list of HH:MM, already 5-min buckets
            times = sorted(entry.get('touch_times', []))
            
            # --- All Day Stats (First hit of the day) ---
            if times:
                first_hit_day = times[0]
                b_all = bucket_time(first_hit_day)
                stats_all[user_key][b_all] = stats_all[user_key].get(b_all, 0) + 1
            
            # --- NY1 Stats (First hit of NY1 Session 08:00 - 12:00) ---
            ny_hits = [t for t in times if "08:00" <= t < "12:00"]
            if ny_hits:
                # FIRST hit only
                first_hit_ny = ny_hits[0]
                b_ny = bucket_time(first_hit_ny)
                stats_ny1[user_key][b_ny] = stats_ny1[user_key].get(b_ny, 0) + 1

    # Generate CSVs
    create_csv(stats_all, ref_data, "all", "Verification_AllDay.csv", level_map)
    create_csv(stats_ny1, ref_data, "ny", "Verification_NY1.csv", level_map)

def create_csv(my_stats, ref_data, ref_section, filename, level_map):
    print(f"Generating {filename}...")
    rows = []
    
    # Get all unique time buckets
    all_buckets = set()
    for l in my_stats:
        all_buckets.update(my_stats[l].keys())
    
    # Also add ref buckets
    if ref_section in ref_data:
        for ref_key in level_map.values():
            if ref_key in ref_data[ref_section]:
                all_buckets.update(ref_data[ref_section][ref_key].keys())
                
    sorted_buckets = sorted(list(all_buckets), key=lambda x: int(x))
    
    for b in sorted_buckets:
        row = {'Time': min_to_time(b), 'Bucket': b}
        
        for user_key, ref_key in level_map.items():
            my_count = my_stats[user_key].get(b, 0)
            
            ref_count = 0
            if ref_section in ref_data and ref_key in ref_data[ref_section]:
                 ref_count = ref_data[ref_section][ref_key].get(b, 0)
            
            diff = my_count - ref_count
            
            row[f'{user_key}_My'] = my_count
            row[f'{user_key}_Ref'] = ref_count
            row[f'{user_key}_Diff'] = diff
            
        rows.append(row)
        
    df = pd.DataFrame(rows)
    # Reorder columns
    cols = ['Time', 'Bucket']
    for k in level_map:
        cols.extend([f'{k}_My', f'{k}_Ref', f'{k}_Diff'])
        
    df = df[cols]
    out_path = OUTPUT_DIR / filename
    df.to_csv(out_path, index=False)
    print(f"Saved {out_path}")

if __name__ == "__main__":
    generate_verification()
