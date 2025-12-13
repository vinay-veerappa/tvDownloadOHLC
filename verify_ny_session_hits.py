import pandas as pd
import numpy as np
import sys
import os
from datetime import timedelta, time

# Add parent directory to path to import services
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from api.services.data_loader import DATA_DIR
from api.services.session_service import SessionService

def verify_ny_hits():
    ticker = "NQ1"
    print(f"Loading data for {ticker}...")
    file_path = DATA_DIR / f"{ticker}_1m.parquet"
    if not file_path.exists():
        print("Data file not found")
        return

    df = pd.read_parquet(file_path)
    if df.index.tz is None:
        df = df.tz_localize('UTC').tz_convert('US/Eastern')
    else:
        df = df.tz_convert('US/Eastern')
        
    print(f"Calculating sessions for {len(df)} rows...")
    # Shift for Trading Day grouping (same as main script)
    df_shifted = df.copy()
    df_shifted.index = df.index + pd.Timedelta(hours=6)
    
    # Calculate sessions to get Midnight Open price
    all_sessions = SessionService.calculate_sessions(df)
    
    levels_by_date = {}
    for entry in all_sessions:
        if entry['session'] == 'MidnightOpen':
            levels_by_date[entry['date']] = entry['price']

    grouped = df.groupby(df_shifted.index.date)
    
    hits_distribution = {} # Minute -> Count
    
    total_days = 0
    hit_days = 0
    
    print("Scanning NY Session (09:30 - 16:00) for Midnight Open hits...")
    
    for date_obj, day_data in grouped:
        date_str = date_obj.strftime('%Y-%m-%d')
        if date_str not in levels_by_date: continue
        
        mid_open = levels_by_date[date_str]
        
        # STRICT NY SESSION WINDOW
        # Start: 09:30 ET
        # End: 16:00 ET
        ny_start = pd.Timestamp.combine(date_obj, time(9, 30)).tz_localize('US/Eastern')
        ny_end = pd.Timestamp.combine(date_obj, time(16, 0)).tz_localize('US/Eastern')
        
        # Slicing day_data for this window
        ny_slice = day_data[(day_data.index >= ny_start) & (day_data.index < ny_end)]
        
        if ny_slice.empty: continue
        
        total_days += 1
        
        # Check for touches
        # Vectorized check
        touches = ny_slice[(ny_slice['low'] <= mid_open) & (ny_slice['high'] >= mid_open)]
        
        if not touches.empty:
            hit_days += 1
            first_hit_time = touches.index[0]
            
            # Record Minute of Day (HH:MM)
            # We want to align with the CSV buckets (e.g. 09:30, 09:35)
            # Round to nearest 5 min or just keep minute?
            # Reference comparison uses 5-min buckets.
            
            # Simple string key for now
            hm = first_hit_time.strftime('%H:%M')
            
            hits_distribution[hm] = hits_distribution.get(hm, 0) + 1

    # Print Results focusing on 09:30 - 10:00 range
    print(f"\nTotal Days Scanned: {total_days}")
    print(f"Days with NY Hit: {hit_days} ({hit_days/total_days*100:.1f}%)")
    
    print("\nHit Distribution (09:30 - 10:00):")
    print(f"{'Time':<8} | {'My Count':<10}")
    print("-" * 25)
    
    keys = sorted([k for k in hits_distribution.keys() if "09:30" <= k <= "10:00"])
    
    # Aggregate into 5-min buckets to match Reference roughly
    buckets = {}
    for k in hits_distribution:
        # 09:32 -> 09:30
        h, m = map(int, k.split(':'))
        m_bucket = (m // 5) * 5
        bucket_key = f"{h:02d}:{m_bucket:02d}"
        buckets[bucket_key] = buckets.get(bucket_key, 0) + hits_distribution[k]
        
    sorted_buckets = sorted([k for k in buckets.keys() if "09:30" <= k <= "10:00"])
    
    for k in sorted_buckets:
        print(f"{k:<8} | {buckets[k]:<10}")

if __name__ == "__main__":
    verify_ny_hits()
