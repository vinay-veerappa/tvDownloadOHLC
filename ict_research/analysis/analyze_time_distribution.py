import pandas as pd
import numpy as np
import os
import sys

# Add parent dir
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def analyze_time_distribution():
    data_path = "c:\\Users\\vinay\\tvDownloadOHLC\\ict_research\\data\\trading_days_enhanced_NQ.csv"
    if not os.path.exists(data_path):
        print(f"Data file not found: {data_path}")
        return

    print(f"Loading data from {data_path}...")
    df = pd.read_csv(data_path, low_memory=False)
    
    # ----------------------------------------------------
    # 1. Select Key Levels & Targets
    # ----------------------------------------------------
    # We focus on the Probability Engine's main targets:
    # London High, London Low
    
    levels = {
        "London High": "hit_london_high_time",
        "London Low": "hit_london_low_time",
        "7-8 Mid": "hit_7_8_mid_time",
        "Midnight Open": "hit_midnight_open_time",
        "PDC (Settlement)": "hit_prev_day_close_time",
        "07:30 Open": "hit_open_0730_time"
    }

    # ----------------------------------------------------
    # 2. Timing Bucketing Function
    # ----------------------------------------------------
    def get_time_bucket(dt):
        if pd.isna(dt): return None
        # Round to nearest 15m? Or just bucket 09:30-09:45
        # Convert to minutes from midnight
        mins = dt.hour * 60 + dt.minute
        
        # NY Session Start = 09:30 = 570 mins
        if mins < 570: return "Pre-Market" # Before 9:30
        
        # Bucket every 15 mins
        bucket_start = (mins // 15) * 15
        h = bucket_start // 60
        m = bucket_start % 60
        
        # Format "HH:MM"
        return f"{h:02d}:{m:02d}"

    # ----------------------------------------------------
    # 3. Analyze Each Level
    # ----------------------------------------------------
    print(f"\n{'LEVEL':<20} | {'MEDIAN':<10} | {'MODE (Most Frequent)':<20} | {'% HIT NY'}")
    print("-" * 75)

    
    for name, col in levels.items():
        if col not in df.columns:
            continue
            
        # Convert to datetime
        # Assuming times are in UTC or consistent format, we need to extract time component
        # The CSV string is likely full datetime.
        # We need to filter for hits specifically in the NY Session (09:30 - 16:00 ET)
        
        # Parse
        times = pd.to_datetime(df[col], errors='coerce')
        
        # Filter: Only valid times
        valid = times.dropna()
        
        if valid.empty:
            print(f"{name:<20} | No Data")
            continue

        # Convert to Eastern Time/Local if needed - assuming data might be UTC?
        # Let's check a sample. If 13:00-20:00 range, it's UTC. If 09:30-16:00, it's ET.
        # Based on previous step, it seems mixed or needs checking.
        # Let's assume we need to normalize to session start.
        
        # Actually, let's just look at the hours.
        hours = valid.dt.hour
        if hours.mean() > 12: # Likely UTC or late day
             # Adjust to ET (UTC-5/4). Let's use simple shift if needed, or tz_convert
             # The previous script used tz_convert('America/New_York')
             try:
                 valid = valid.dt.tz_convert('America/New_York')
             except:
                 # Start is likely naive. Assume UTC if mean > 12?
                 if hours.mean() > 14: # 14:00 UTC is 9:00/10:00 ET
                     valid = valid.dt.tz_localize('UTC').dt.tz_convert('America/New_York')
        
        # Filter for NY Session (09:30 - 16:00)
        # We only care when the level is hit during the trading day outcome
        ny_mask = (valid.dt.time >= pd.Timestamp("09:30").time()) & \
                  (valid.dt.time <= pd.Timestamp("16:00").time())
        
        ny_hits = valid[ny_mask]
        
        if ny_hits.empty:
            print(f"{name:<20} | No NY Hits")
            continue
            
        # 1. Buckets
        buckets = ny_hits.apply(get_time_bucket)
        
        # 2. Mode (Most Frequent 15m Bucket)
        mode = buckets.mode().iloc[0] if not buckets.empty else "N/A"
        mode_count = buckets.value_counts().iloc[0]
        mode_pct = (mode_count / len(buckets)) * 100
        
        # 3. Median Time
        # Convert to minutes from midnight for median calc
        mins = ny_hits.dt.hour * 60 + ny_hits.dt.minute
        median_min = mins.median()
        med_h = int(median_min // 60)
        med_m = int(median_min % 60)
        median_str = f"{med_h:02d}:{med_m:02d}"
        
        # 4. Hit Rate in Session (vs Total Days)
        hit_rate = (len(ny_hits) / len(df)) * 100
        
        print(f"{name:<20} | {median_str:<10} | {mode:<5} ({mode_pct:.0f}%)    | {hit_rate:.1f}%")

    print("\n--- Detailed Distribution for London High ---")
    # Show top 5 buckets
    ts = pd.to_datetime(df['hit_london_high_time'], errors='coerce')
    # smart conversion
    try:
        ts = ts.dt.tz_localize('UTC').dt.tz_convert('America/New_York')
    except:
        pass
        
    ny_ts = ts[(ts.dt.time >= pd.Timestamp("09:30").time()) & (ts.dt.time <= pd.Timestamp("16:00").time())]
    buckets = ny_ts.apply(get_time_bucket)
    print(buckets.value_counts().head(8))

if __name__ == "__main__":
    analyze_time_distribution()
