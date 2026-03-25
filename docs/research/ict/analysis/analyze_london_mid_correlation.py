import json
import pandas as pd
import numpy as np
import os
import sys
from datetime import datetime, timedelta
import pytz

# Add parent dir
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def analyze_london_mid_correlation():
    # Paths
    parquet_path = r"c:\Users\vinay\tvDownloadOHLC\data\NQ1_1m.parquet"
    profiler_path = r"c:\Users\vinay\tvDownloadOHLC\data\NQ1_profiler.json"
    
    if not os.path.exists(parquet_path) or not os.path.exists(profiler_path):
        print("Data files not found.")
        return

    print("1. Loading Data...")
    
    # --- LOAD PROFILER (Outcomes & London Mid) ---
    with open(profiler_path, 'r') as f:
        p_data = json.load(f)
    
    df_p = pd.DataFrame(p_data)
    df_p['date_str'] = pd.to_datetime(df_p['date']).dt.strftime('%Y-%m-%d')
    
    daily_data = {}
    
    # Pass 1: Get London Mid
    london_sessions = df_p[df_p['session'] == 'London']
    for _, row in london_sessions.iterrows():
        d = row['date_str']
        if d not in daily_data: daily_data[d] = {}
        daily_data[d]['London_Mid'] = row['mid']
        
    # Pass 2: Get NY1 Outcome
    ny1_sessions = df_p[df_p['session'].isin(['NY AM', 'NY1'])]
    
    def get_ny1_dir(status):
        if status in ['Long True', 'Short False']: return "UP"
        if status in ['Short True', 'Long False']: return "DOWN"
        return "NEUTRAL"

    for _, row in ny1_sessions.iterrows():
        d = row['date_str']
        if d not in daily_data: continue
        daily_data[d]['NY1_Outcome'] = get_ny1_dir(row['status'])
        
    print(f"Profiler Dates Loaded: {len(daily_data)} days")

    # --- LOAD 1M DATA (Price) ---
    print(f"Loading {parquet_path}...")
    df_1m = pd.read_parquet(parquet_path)
    
    # Robust Time Handling
    # Use 'time' column if available (Unix Timestamp usually)
    if 'time' in df_1m.columns:
        print("Using 'time' column (Unix Epoch) for index...")
        df_1m['datetime'] = pd.to_datetime(df_1m['time'], unit='s', utc=True)
    elif 'datetime' in df_1m.index.names:
         print("Using index 'datetime'...")
         df_1m['datetime'] = df_1m.index
         # check if tz aware
         if df_1m['datetime'].dt.tz is None:
             df_1m['datetime'] = df_1m['datetime'].dt.tz_localize('UTC')
    else:
        print("Using index (assuming datetime)...")
        df_1m['datetime'] = df_1m.index
        if df_1m['datetime'].dt.tz is None:
             df_1m['datetime'] = df_1m['datetime'].dt.tz_localize('UTC')
             
    # Convert to US/Eastern
    print("Converting to US/Eastern...")
    df_1m['datetime'] = df_1m['datetime'].dt.tz_convert('US/Eastern')
    df_1m.set_index('datetime', inplace=True)
    df_1m.sort_index(inplace=True)
    
    print(f"Data Range: {df_1m.index.min()} to {df_1m.index.max()}")
    
    # Group by Date (in ET)
    results = []
    
    # Times to check (ET)
    check_times = [
        (8, 0), (8, 30), (9, 0), (9, 15), (9, 30), (9, 45), (10, 0)
    ]
    
    print("2. Analyzing Daily Correlations...")
    
    # Iterate by grouping by date component of the index
    grouped = df_1m.groupby(df_1m.index.date)
    
    for date_obj, day_data in grouped:
        date_str = date_obj.strftime('%Y-%m-%d')
        
        # Match with Profiler Data
        if date_str not in daily_data: continue
        rec = daily_data[date_str]
        
        lon_mid = rec.get('London_Mid')
        ny1_out = rec.get('NY1_Outcome')
        
        if not lon_mid or not ny1_out or ny1_out == "NEUTRAL": continue
        
        day_res = {'date': date_str, 'NY1_Outcome': ny1_out}
        
        for h, m in check_times:
            # Find candle at exact time or slightly after (within 5 mins)
            # We want the OPEN PRICE of the checking time? 
            # Usually "Price at 8:30" means 8:30 Open or Close. 
            # 1m data: 08:30 candle open.
            
            # Filter for specific time
            mask = (day_data.index.hour == h) & (day_data.index.minute == m)
            candles = day_data[mask]
            
            price = None
            if len(candles) > 0:
                price = candles.iloc[0]['open'] # Use Open of that minute
            else:
                # Fallback: nearest matching time within 5 mins?
                # Let's skip fallback for now for speed/precision
                pass
                
            if price is not None:
                if price > lon_mid:
                    pos = "ABOVE"
                else:
                    pos = "BELOW"
                day_res[f"{h:02d}:{m:02d}_Pos"] = pos
            else:
                day_res[f"{h:02d}:{m:02d}_Pos"] = None
        
        results.append(day_res)

    res_df = pd.DataFrame(results)
    print(f"Total Days Analyzed: {len(res_df)}")
    
    # --- 3. CALCULATE PROBABILITIES ---
    print("\n--- IMPACT OF PRICE VS LONDON MID (EST TIMES) ---")
    
    time_cols = sorted([c for c in res_df.columns if "_Pos" in c])
    
    for col in time_cols:
        time_label = col.replace("_Pos", "")
        
        # ABOVE Analysis
        above_df = res_df[res_df[col] == "ABOVE"]
        count_above = len(above_df)
        if count_above > 0:
            # Expected Direction: UP (Trend)
            up_wins = above_df['NY1_Outcome'].value_counts().get('UP', 0)
            trend_rate_above = (up_wins / count_above) * 100
        else:
            trend_rate_above = 0
            
        # BELOW Analysis
        below_df = res_df[res_df[col] == "BELOW"]
        count_below = len(below_df)
        if count_below > 0:
            # Expected Direction: DOWN (Trend)
            dn_wins = below_df['NY1_Outcome'].value_counts().get('DOWN', 0)
            trend_rate_below = (dn_wins / count_below) * 100
        else:
            trend_rate_below = 0
            
        # Weighted Average Trend Probability
        total_valid = count_above + count_below
        if total_valid > 0:
            total_wins = (trend_rate_above/100 * count_above) + (trend_rate_below/100 * count_below)
            avg_trend_rate = (total_wins / total_valid) * 100
        else:
            avg_trend_rate = 0
            
        rev_rate = 100 - avg_trend_rate
        
        print(f"\nTime {time_label} ET (n={total_valid})")
        print(f"  Pos ABOVE -> NY1 UP: {trend_rate_above:.1f}%")
        print(f"  Pos BELOW -> NY1 DOWN: {trend_rate_below:.1f}%")
        print(f"  -> AVG TREND: {avg_trend_rate:.1f}% | AVG REVERSAL: {rev_rate:.1f}%")

if __name__ == "__main__":
    analyze_london_mid_correlation()
