import pandas as pd
import numpy as np
import os
import sys

# Add parent dir
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def analyze_time_distribution_v2():
    data_path = "c:\\Users\\vinay\\tvDownloadOHLC\\ict_research\\data\\trading_days_enhanced_NQ.csv"
    if not os.path.exists(data_path):
        print(f"Data file not found: {data_path}")
        return

    print(f"Loading data from {data_path}...")
    df = pd.read_csv(data_path, low_memory=False)
    
    # ----------------------------------------------------
    # 1. Select Key Levels & Targets
    # ----------------------------------------------------
    levels = {
        "London High": "hit_london_high_time",
        "London Low": "hit_london_low_time",
        "7-8 Mid": "hit_7_8_mid_time",
        "Midnight Open": "hit_midnight_open_time",
        "PDC (Settlement)": "hit_prev_day_close_time",
        "07:30 Open": "hit_open_0730_time"
    }
    
    # ----------------------------------------------------
    # 2. Timing Helper
    # ----------------------------------------------------
    def get_time_bucket(hour, minute):
        # Convert to 15m bucket string
        if pd.isna(hour) or pd.isna(minute): return "N/A"
        
        mins = hour * 60 + minute
        bucket_start = (mins // 15) * 15
        h = int(bucket_start // 60)
        m = int(bucket_start % 60)
        return f"{h:02d}:{m:02d}"

    print(f"\n{'LEVEL':<20} | {'MEDIAN':<10} | {'MODE (Most Frequent)':<20} | {'% HIT NY'}")
    print("-" * 75)
    
    for name, col in levels.items():
        if col not in df.columns:
            continue
            
        # Parse Dates safely
        try:
            # First coerce to datetime
            times = pd.to_datetime(df[col], errors='coerce', utc=True) 
            # Drop NaT immediately
            valid = times.dropna()
            
            if valid.empty:
                print(f"{name:<20} | No Data")
                continue
                
            # Convert to Eastern Time
            valid = valid.dt.tz_convert('America/New_York')
            
            # Extract Components needed for filtering
            # We want NY Session Only: 09:30 - 16:00
            # Filter by HOUR
            
            is_valid_time = ((valid.dt.hour > 9) | ((valid.dt.hour == 9) & (valid.dt.minute >= 30))) & \
                            (valid.dt.hour < 16)
                            
            ny_hits = valid[is_valid_time]
            
            if ny_hits.empty:
                print(f"{name:<20} | No NY Hits")
                continue
                
            # 1. Median Time
            # Convert to minutes from midnight
            mins = ny_hits.dt.hour * 60 + ny_hits.dt.minute
            median_min = mins.median()
            med_h = int(median_min // 60)
            med_m = int(median_min % 60)
            median_str = f"{med_h:02d}:{med_m:02d}"
            
            # 2. Mode Bucket
            # Create bucket series
            buckets = pd.Series([get_time_bucket(h, m) for h, m in zip(ny_hits.dt.hour, ny_hits.dt.minute)])
            mode = buckets.mode().iloc[0] if not buckets.empty else "N/A"
            
            # Frequency of Mode
            count = buckets.value_counts().iloc[0] if not buckets.empty else 0
            pct = (count / len(buckets) * 100) if not buckets.empty else 0
            
            # 3. Hit Rate (vs Total Days)
            hit_rate = (len(ny_hits) / len(df)) * 100
            
            print(f"{name:<20} | {median_str:<10} | {mode:<6} ({pct:.0f}%)   | {hit_rate:.1f}%")
            
        except Exception as e:
            print(f"Error processing {name}: {e}")

if __name__ == "__main__":
    analyze_time_distribution_v2()
