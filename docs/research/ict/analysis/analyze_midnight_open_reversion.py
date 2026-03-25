import json
import pandas as pd
import numpy as np
import os
import sys
from datetime import timedelta

# Add parent dir
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def analyze_midnight_open_reversion():
    # Paths
    parquet_path = r"c:\Users\vinay\tvDownloadOHLC\data\NQ1_1m.parquet"
    
    if not os.path.exists(parquet_path):
        print("Data files not found.")
        return

    print("1. Loading 1M Data...")
    df_1m = pd.read_parquet(parquet_path)
    
    # Timezone Handling
    if 'time' in df_1m.columns:
        df_1m['datetime'] = pd.to_datetime(df_1m['time'], unit='s', utc=True)
    elif 'datetime' in df_1m.index.names:
         df_1m['datetime'] = df_1m.index
         if df_1m['datetime'].dt.tz is None:
             df_1m['datetime'] = df_1m['datetime'].dt.tz_localize('UTC')
    else:
        df_1m['datetime'] = df_1m.index
        if df_1m['datetime'].dt.tz is None:
             df_1m['datetime'] = df_1m['datetime'].dt.tz_localize('UTC')

    print("Converting to US/Eastern...")
    df_1m['datetime'] = df_1m['datetime'].dt.tz_convert('US/Eastern')
    df_1m.set_index('datetime', inplace=True)
    df_1m.sort_index(inplace=True)
    
    # Extract Helper Columns
    df_1m['date'] = df_1m.index.date
    df_1m['hour'] = df_1m.index.hour
    
    print("2. Extracting Midnight Opens...")
    # Get 00:00 Open for each day
    midnight_opens = df_1m[df_1m['hour'] == 0].groupby('date')['open'].first()
    
    results = []
    
    # We iterate through each trading day
    dates = sorted(midnight_opens.index)
    
    print(f"Analyzing {len(dates)} days...")
    
    for i, date_obj in enumerate(dates):
        # Current Day's Open
        open_price = midnight_opens[date_obj]
        
        # 1. Did we hit it TODAY? (Same Trading Day)
        # Filter data for this date
        day_data = df_1m[df_1m['date'] == date_obj]
        
        # Check Low <= Price <= High
        # Actually simplest is: did any candle low <= price <= high?
        # But since price IS the open of 00:00, it is guaranteed to be hit at 00:00.
        # So we need to distinct: *Does it return to Open after deviating?*
        # Or does the user mean: "If we drift away, do we come back?"
        # User said: "probability of a midnight open *which was not hit on the same day* being hit..."
        # This implies the price moved away and never came back.
        # But technically 00:00 open IS hit at 00:00.
        # Use simple definition: Did price trade at Open Price *after* 00:05?
        # Or did it stay away?
        
        # Let's assume "Not Hit" means: After the initial formation (say 00:30 or 09:30), did it return?
        # A clearer definition for "Naked Open" is typically: Price closes away from Open, and maybe never touched it during NY session?
        # Let's define "Hit" as: Price touches level during NY Session (09:30 - 16:00)?
        # Or just "Anytime during the trading day"?
        # Usually "Midnight Open" is a magnet. "Not hit" implies a Trend Day where we opened and ran.
        
        # Let's check if it was hit during NY Session (09:30-16:00). 
        # If not, it's a "Missed Open".
        
        # Get NY Data for this date
        mask_ny = (day_data.index.hour >= 9) & (day_data.index.hour < 16)
        # Precise: 09:30 to 16:00
        mask_ny_precise = (
            (day_data.index.hour == 9) & (day_data.index.minute >= 30) |
            (day_data.index.hour >= 10) & (day_data.index.hour < 16)
        )
        ny_data = day_data[mask_ny_precise]
        
        if len(ny_data) == 0: continue
        
        ny_low = ny_data['low'].min()
        ny_high = ny_data['high'].max()
        
        hit_same_day = (ny_low <= open_price <= ny_high)
        
        if not hit_same_day:
            # It's a "Naked Open"
            # Track when it gets hit
            days_to_hit = None
            
            # Search subsequent days
            for j in range(i + 1, len(dates)):
                next_date = dates[j]
                next_day_data = df_1m[df_1m['date'] == next_date]
                
                if len(next_day_data) == 0: continue
                
                nd_low = next_day_data['low'].min()
                nd_high = next_day_data['high'].max()
                
                if nd_low <= open_price <= nd_high:
                    days_to_hit = j - i  # 1 = Next Day
                    break
            
            results.append({
                'Date': date_obj,
                'Open_Price': open_price,
                'DOW': date_obj.strftime('%A'),
                'Days_To_Hit': days_to_hit
            })
            
    df_res = pd.DataFrame(results)
    
    if len(df_res) == 0:
        print("No missed opens found (Data error or extremely rare).")
        return

    print(f"\nTotal Missed Opens (Naked Levels): {len(df_res)}")
    
    # --- 3. ANALYSIS ---
    
    # Overall Reversion Stats
    print("\n--- REVERSION STATS (Unvisited Midnight Opens) ---")
    
    # Hit Rates
    hit_counts = df_res['Days_To_Hit'].value_counts().sort_index()
    total = len(df_res)
    
    cum_prob = 0
    print(f"Total Events: {total}")
    print("\nProbability of Hit By Day:")
    
    for d in range(1, 11): # Check up to 10 days
        count = hit_counts.get(d, 0)
        prob = (count / total) * 100
        cum_prob += prob
        print(f"  Day +{d}: {prob:.1f}% (Cumulative: {cum_prob:.1f}%)")
        
    # Unhit?
    missed_forever = df_res['Days_To_Hit'].isna().sum()
    print(f"  Never Hit (in dataset): {(missed_forever/total)*100:.1f}%")

    # DOW Analysis
    print("\n--- DAY OF WEEK BREAKDOWN ---")
    # If missed on Monday, when is it hit?
    
    dows = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    
    for dow in dows:
        sub = df_res[df_res['DOW'] == dow]
        if len(sub) == 0: continue
        
        print(f"\n[{dow}] Missed Opens (n={len(sub)}):")
        
        # Next Day Hit Rate
        hit_next = sub[sub['Days_To_Hit'] == 1]
        p_next = (len(hit_next) / len(sub)) * 100
        
        # Hit within 3 Days
        hit_3 = sub[(sub['Days_To_Hit'] <= 3)]
        p_3 = (len(hit_3) / len(sub)) * 100
        
        print(f"  -> Hit Next Day: {p_next:.1f}%")
        print(f"  -> Hit within 3 Days: {p_3:.1f}%")
        
    # Streak Analysis
    # Max consecutive days with missed opens?
    # We can infer streaks from dates in df_res
    # If Date[i+1] == Date[i] + 1 day (trading day sense)
    
    print("\n--- STREAK ANALYSIS ---")
    # Sort by date
    df_res = df_res.sort_values('Date')
    
    streak_counts = []
    current_streak = 1
    
    # We need to act on the INDEX of the dates list to be precise about 'consecutive trading days'
    # Map dates to indices in original 'dates' list
    date_to_idx = {d: i for i, d in enumerate(dates)}
    df_res['idx'] = df_res['Date'].map(date_to_idx)
    
    indices = df_res['idx'].tolist()
    
    if len(indices) > 0:
        for k in range(1, len(indices)):
            if indices[k] == indices[k-1] + 1:
                current_streak += 1
            else:
                streak_counts.append(current_streak)
                current_streak = 1
        streak_counts.append(current_streak)
        
        max_streak = max(streak_counts)
        avg_streak = np.mean(streak_counts)
        
        print(f"Max Consecutive Days with Unvisited Open: {max_streak}")
        print(f"Average Streak Length: {avg_streak:.1f} days")
        
        # Probability of ending streak?
        # If simple streak, p = 1/avg?
        
    # What is the probability of a "Naked Open" occurring?
    # Count of missed / Total Days
    naked_prob = (len(df_res) / len(dates)) * 100
    print(f"\nBase Probability of a Naked Midnight Open: {naked_prob:.1f}%") # i.e. How often do we NOT retest open?

if __name__ == "__main__":
    analyze_midnight_open_reversion()
