import json
import pandas as pd
import numpy as np
import os
import sys
from datetime import timedelta

# Add parent dir
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def analyze_reversion_optimized():
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
    df_1m = df_1m.set_index('datetime')
    df_1m = df_1m.sort_index()
    
    # Extract Helper Columns
    df_1m['date'] = df_1m.index.date
    df_1m['hour'] = df_1m.index.hour
    df_1m['minute'] = df_1m.index.minute
    
    print("2. Pre-Aggregating Daily Data...")
    
    # Daily Open (Midnight)
    midnight_opens = df_1m[df_1m['hour'] == 0].groupby('date')['open'].first()
    
    # Daily High/Low (Overall)
    daily_highs = df_1m.groupby('date')['high'].max()
    daily_lows = df_1m.groupby('date')['low'].min()
    
    # Daily NY Session High/Low (09:30 - 16:00)
    # Filter for NY Session
    mask_ny = (
        (df_1m.index.hour == 9) & (df_1m.index.minute >= 30) |
        (df_1m.index.hour >= 10) & (df_1m.index.hour < 16)
    )
    df_ny = df_1m[mask_ny]
    ny_highs = df_ny.groupby('date')['high'].max()
    ny_lows = df_ny.groupby('date')['low'].min()
    
    # Create Daily DF
    df_daily = pd.DataFrame({
        'Open': midnight_opens,
        'High': daily_highs,
        'Low': daily_lows,
        'NY_High': ny_highs,
        'NY_Low': ny_lows 
    }).dropna() # Only keep days with full data
    
    result_list = []
    
    dates = df_daily.index.tolist()
    total_days = len(dates)
    print(f"Analyzing {total_days} days (Vectorized Check)...")
    
    # Convert index to native python dates for speed in loop
    # Or just use iloc
    
    opens = df_daily['Open'].values
    ny_highs_vals = df_daily['NY_High'].values
    ny_lows_vals = df_daily['NY_Low'].values
    day_highs_vals = df_daily['High'].values
    day_lows_vals = df_daily['Low'].values
    
    for i in range(total_days):
        open_price = opens[i]
        
        # Check if Hit in NY Session TODAY
        # We use NY High/Low for "Same Day Reversion" check
        # Because if it's hit in NY, it's not a "Naked Open"
        
        hit_today = (ny_lows_vals[i] <= open_price <= ny_highs_vals[i])
        
        if not hit_today:
            # Naked Open!
            days_to_hit = None
            
            # Look Forward
            for j in range(i + 1, total_days):
                # Check Next Day's Full Range
                next_low = day_lows_vals[j]
                next_high = day_highs_vals[j]
                
                if next_low <= open_price <= next_high:
                    days_to_hit = j - i
                    break
            
            result_list.append({
                'Date': dates[i],
                'Days_To_Hit': days_to_hit,
                'DOW': dates[i].strftime('%A')
            })
            
    df_res = pd.DataFrame(result_list)
    print(f"\nTotal Naked Opens: {len(df_res)}")
    print(f"Base Probability of Leaving a Naked Open: {(len(df_res)/total_days)*100:.1f}%")
    
    # --- ANALYSIS ---
    hit_counts = df_res['Days_To_Hit'].value_counts().sort_index()
    total_naked = len(df_res)
    
    print("\n--- REVERSION PROBABILITIES (Days to Fill) ---")
    cum = 0
    for d in range(1, 11):
        c = hit_counts.get(d, 0)
        p = (c / total_naked) * 100
        cum += p
        print(f"  Day +{d}: {p:.1f}% (Cum: {cum:.1f}%)")
        
    missed = df_res['Days_To_Hit'].isna().sum()
    print(f"  Never Filled: {(missed/total_naked)*100:.1f}%")
    
    # DOW Analysis
    print("\n--- DAY OF WEEK BREAKDOWN ---") 
    dows = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    for dow in dows:
        sub = df_res[df_res['DOW'] == dow]
        if len(sub) == 0: continue
        
        h1 = len(sub[sub['Days_To_Hit'] == 1])
        h3 = len(sub[sub['Days_To_Hit'] <= 3])
        
        print(f"[{dow}] (n={len(sub)}):")
        print(f"  -> Filled Next Day: {(h1/len(sub))*100:.1f}%")
        print(f"  -> Filled within 3 Days: {(h3/len(sub))*100:.1f}%")

    # Streak Analysis
    # Convert 'Date' to datetime to be sure
    df_res['Date'] = pd.to_datetime(df_res['Date'])
    df_res = df_res.sort_values('Date')
    
    # Identify gaps in dates. If gap = 1 day (trading), then consecutive.
    # Actually just check index mapping again.
    # Map dates to integer index from full list
    date_map = {pd.Timestamp(d): i for i, d in enumerate(dates)}
    df_res['idx'] = df_res['Date'].map(date_map)
    
    indices = sorted(df_res['idx'].dropna().tolist())
    
    streaks = []
    curr = 1
    for k in range(1, len(indices)):
        if indices[k] == indices[k-1] + 1:
            curr += 1
        else:
            streaks.append(curr)
            curr = 1
    streaks.append(curr)
    
    print("\n--- STREAK ANALYSIS ---")
    print(f"Max Consecutive Days leaving Naked Opens: {max(streaks)}")
    print(f"Average Streak: {np.mean(streaks):.2f} days")
    print(f"Streak Counts: {pd.Series(streaks).value_counts().sort_index().head(5)}")

if __name__ == "__main__":
    analyze_reversion_optimized()
