import json
import pandas as pd
import numpy as np
import os
import sys

# Add parent dir
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def analyze_london_open_correlation():
    # Paths
    parquet_path = r"c:\Users\vinay\tvDownloadOHLC\data\NQ1_1m.parquet"
    profiler_path = r"c:\Users\vinay\tvDownloadOHLC\data\NQ1_profiler.json"
    
    if not os.path.exists(parquet_path) or not os.path.exists(profiler_path):
        print("Data files not found.")
        return

    print("1. Loading Data...")
    # Load Profiler to get NY1 Outcome
    with open(profiler_path, 'r') as f:
        p_data = json.load(f)
    
    df_p = pd.DataFrame(p_data)
    # Filter for NY1 sessions to get the GROUND TRUTH OUTCOME
    df_ny1 = df_p[df_p['session'].isin(['NY AM', 'NY1'])].copy()
    df_ny1['date_str'] = pd.to_datetime(df_ny1['date']).dt.strftime('%Y-%m-%d')
    
    # Define NY1 Direction Logic (Truth)
    def get_ny1_dir(status):
        if status in ['Long True', 'Short False']: return "UP"
        if status in ['Short True', 'Long False']: return "DOWN"
        return "NEUTRAL"
        
    df_ny1['NY1_Outcome'] = df_ny1['status'].apply(get_ny1_dir)
    outcome_map = df_ny1.set_index('date_str')['NY1_Outcome'].to_dict()
    
    # Load 1m Data for Price Check
    print(f"Loading {parquet_path}...")
    df_1m = pd.read_parquet(parquet_path)
    
    # Ensure Datetime
    if 'datetime' in df_1m.columns:
        df_1m['datetime'] = pd.to_datetime(df_1m['datetime'])
    else:
        # Assuming index is time if no column
        df_1m = df_1m.reset_index() 
        if 'time' in df_1m.columns:
           df_1m['datetime'] = pd.to_datetime(df_1m['time'])
        elif 'date' in df_1m.columns: 
           df_1m['datetime'] = pd.to_datetime(df_1m['date'])

    df_1m = df_1m.set_index('datetime')
    df_1m = df_1m.sort_index()
    
    # We need to process day by day
    # Times to check (ET): 03:00 (London Open), 08:00, 08:30, 09:00, 09:15, 09:30, 09:45, 10:00
    
    # UTC handling? Assuming data is in Local/ET or we need to handle timezone.
    # Usually these parquets are in exchange time (ET) or UTC.
    # Let's check a sample time to guess. 09:30 is open.
    # We will assume the index is already timezone aware or consistent.
    
    # Resample to daily to iterate?
    # Better: grouping by date
    
    results = []
    
    grouped = df_1m.groupby(df_1m.index.date)
    
    check_times = [
        (8, 0), (8, 30), (9, 0), (9, 15), (9, 30), (9, 45), (10, 0)
    ]
    
    print("2. Analyzing Daily Correlations...")
    
    for date_obj, day_data in grouped:
        date_str = date_obj.strftime('%Y-%m-%d')
        
        # 1. Get NY1 Outcome
        ny1_outcome = outcome_map.get(date_str)
        if not ny1_outcome or ny1_outcome == "NEUTRAL": continue
        
        # 2. Get London Open Price (03:00 ET)
        # We look for the 03:00 candle.
        try:
            # Create exact timestamp for lookup
            # Assuming day_data index matches the date
            london_open_time = day_data.index[day_data.index.hour == 3]
            if len(london_open_time) == 0: continue # No 3am data
            london_open_price = day_data.loc[london_open_time[0], 'open']
            
            # 3. Check Price at specific times
            day_res = {'date': date_str, 'NY1_Outcome': ny1_outcome}
            
            for h, m in check_times:
                # Find candle at or closest after h:m
                # Simple lookup
                target_mask = (day_data.index.hour == h) & (day_data.index.minute == m)
                target_candles = day_data[target_mask]
                
                if len(target_candles) > 0:
                    price = target_candles.iloc[0]['close']
                    
                    # Determine Position
                    if price > london_open_price:
                        pos = "ABOVE"
                        # Prediction: ABOVE implies UP bias? 
                        # Let's just store the state
                    else:
                        pos = "BELOW"
                        
                    day_res[f"{h:02d}:{m:02d}_Pos"] = pos
                else:
                    day_res[f"{h:02d}:{m:02d}_Pos"] = None
            
            results.append(day_res)
            
        except Exception as e:
            continue

    res_df = pd.DataFrame(results)
    print(f"Total Days Analyzed: {len(res_df)}")
    
    # --- 3. CALCULATE PROBABILITIES ---
    # For each time slot, if Price is ABOVE London Open, what % is NY1 UP?
    # If Price is BELOW London Open, what % is NY1 DOWN?
    
    print("\n--- PROBABILITY OF CONTINUATION (Price > LO -> NY UP) ---")
    
    time_cols = [c for c in res_df.columns if "_Pos" in c]
    
    for col in time_cols:
        time_label = col.replace("_Pos", "")
        
        # Above Logic
        above_df = res_df[res_df[col] == "ABOVE"]
        if len(above_df) > 0:
            up_prob = above_df['NY1_Outcome'].value_counts(normalize=True).get('UP', 0) * 100
        else:
            up_prob = 0
            
        # Below Logic
        below_df = res_df[res_df[col] == "BELOW"]
        if len(below_df) > 0:
            dn_prob = below_df['NY1_Outcome'].value_counts(normalize=True).get('DOWN', 0) * 100
        else:
            dn_prob = 0
            
        # Average "Trend Adherence"
        avg_prob = (up_prob + dn_prob) / 2
        
        print(f"Time {time_label}: {avg_prob:.1f}% Match (Above->Up: {up_prob:.1f}%, Below->Down: {dn_prob:.1f}%)")
        
        # Does it favor Reversal?
        # Reversal = Above -> Down OR Below -> Up
        rev_rate = 100 - avg_prob
        if rev_rate > 55:
            print(f"  --> REVERSAL EDGE: {rev_rate:.1f}% (Fade the position)")

if __name__ == "__main__":
    analyze_london_open_correlation()
