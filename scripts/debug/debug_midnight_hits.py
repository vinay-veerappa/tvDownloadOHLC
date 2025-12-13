import pandas as pd
import sys
import os
from datetime import timedelta, time

# Add parent directory to path to import services
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from api.services.session_service import SessionService
from api.services.data_loader import DATA_DIR

def debug_midnight_hits():
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

    # Filter for last 60 days of data for manual verification
    last_date = df.index[-1]
    start_date = last_date - timedelta(days=60)
    df_recent = df[df.index >= start_date]
    
    print(f"Analyzing data from {start_date.date()} to {last_date.date()}")

    # Use SessionService to get levels
    all_sessions = SessionService.calculate_sessions(df_recent)
    
    # Organize levels by date
    levels_by_date = {}
    for entry in all_sessions:
        if entry['session'] == 'MidnightOpen':
            levels_by_date[entry['date']] = entry['price']

    # Check for hits between 09:30 and 10:00
    hits_found = []
    
    # Iterate by day
    days = df_recent.groupby(df_recent.index.date)
    
    print("\nScanning for hits between 09:30 and 10:00 ET...")
    print(f"{'Date':<12} | {'Time':<8} | {'MidOpen':<10} | {'Low':<10} | {'High':<10} | {'Hit?'}")
    print("-" * 70)
    
    for date_obj, day_data in days:
        date_str = date_obj.strftime('%Y-%m-%d')
        if date_str not in levels_by_date:
            continue
            
        mid_open = levels_by_date[date_str]
        
        # Define 09:30 - 10:00 window for THIS day
        # Note: date_obj is the calender date. 09:30 is on this date.
        
        # Check specific minutes
        # We need to ensure we are looking at the correct day's 9:30
        
        start_check = pd.Timestamp.combine(date_obj, time(9, 30)).tz_localize('US/Eastern')
        end_check = pd.Timestamp.combine(date_obj, time(10, 0)).tz_localize('US/Eastern')
        
        window_data = day_data[(day_data.index >= start_check) & (day_data.index < end_check)]
        
        for ts, row in window_data.iterrows():
            # Check touch
            if row['low'] <= mid_open <= row['high']:
                # BEFORE printing, check if it was hit earlier in the day!
                start_day = pd.Timestamp.combine(date_obj, time(0, 15)).tz_localize('US/Eastern')
                earlier_data = day_data[(day_data.index >= start_day) & (day_data.index < start_check)]
                
                was_hit_earlier = False
                first_hit_time = None
                
                # Vectorized check for earlier hits
                if not earlier_data.empty:
                    # Check if any row touches
                    touches = earlier_data[(earlier_data['low'] <= mid_open) & (earlier_data['high'] >= mid_open)]
                    if not touches.empty:
                        was_hit_earlier = True
                        first_hit_time = touches.index[0].strftime('%H:%M')
                
                hit_status = f"YES (First Hit: {first_hit_time})" if was_hit_earlier else "YES (First Hit: THIS ONE)"
                
                hits_found.append({
                    'date': date_str,
                    'time': ts.strftime('%H:%M'),
                    'price': mid_open,
                    'hit_earlier': was_hit_earlier,
                    'first_hit': first_hit_time
                })
                print(f"{date_str:<12} | {ts.strftime('%H:%M'):<8} | {mid_open:<10.2f} | {row['low']:<10.2f} | {row['high']:<10.2f} | {hit_status}")
                break # Only need one per day for this debug

    print(f"\nTotal Hits Found in last 60 days (09:30-10:00): {len(hits_found)}")

if __name__ == "__main__":
    debug_midnight_hits()
