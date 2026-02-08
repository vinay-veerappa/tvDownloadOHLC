import json
import pandas as pd
import numpy as np
import os
import sys

def analyze_high_frequency():
    profiler_path = r"c:\Users\vinay\tvDownloadOHLC\data\NQ1_profiler.json"
    
    if not os.path.exists(profiler_path):
        print("Profiler JSON not found.")
        return

    print("1. Loading Profiler Data...")
    with open(profiler_path, 'r') as f:
        p_data = json.load(f)
    
    df_p = pd.DataFrame(p_data)
    df_p['date_str'] = pd.to_datetime(df_p['date']).dt.strftime('%Y-%m-%d')
    
    # Pivot Data
    daily_records = {}
    for _, row in df_p.iterrows():
        d = row['date_str']
        s = row['session']
        if d not in daily_records: daily_records[d] = {}
        
        prefix = ""
        if s == "Asia": prefix = "Asia"
        elif s == "London": prefix = "London"
        elif s == "NY AM" or s == "NY1": prefix = "NY"
        else: continue
        
        daily_records[d][f"{prefix}_Status"] = row['status']
        daily_records[d][f"{prefix}_High"] = row['range_high']
        daily_records[d][f"{prefix}_Low"] = row['range_low']
        daily_records[d][f"{prefix}_Broken"] = row['broken'] # Original boolean field

    df = pd.DataFrame.from_dict(daily_records, orient='index')
    # Use full data, but filter only complete sessions for comparative analysis
    df = df.dropna(subset=['Asia_Status', 'London_Status', 'NY_Status'])
    
    # Define Directions
    def get_dir(status):
        if status in ['Long True', 'Short False']: return "UP"
        if status in ['Short True', 'Long False']: return "DOWN"
        return "NEUTRAL"
        
    df['Asia_Dir'] = df['Asia_Status'].apply(get_dir)
    df['Lon_Dir'] = df['London_Status'].apply(get_dir)
    df['NY_Dir'] = df['NY_Status'].apply(get_dir)
    
    # --- INFER LEVEL BREAKS ---
    # Did London break Asia High? Low?
    df['Lon_Broke_AsiaHigh'] = df['London_High'] > df['Asia_High']
    df['Lon_Broke_AsiaLow'] = df['London_Low'] < df['Asia_Low']
    
    total = len(df)
    print(f"Total Days: {total}")
    
    # --- ANALYSIS 3: THE "BROKEN" SIGNAL REVISITED ---
    
    print("\n--- LONDON BROKE ASIA HIGH (BULLISH SIGNAL?) ---")
    brk_high = df[df['Lon_Broke_AsiaHigh']]
    print(f"Count: {len(brk_high)} ({len(brk_high)/total*100:.1f}%)")
    # Continuation Probability
    res_high = brk_high['NY_Dir'].value_counts(normalize=True) * 100
    print(f"  -> NY UP: {res_high.get('UP', 0):.1f}%")
    print(f"  -> NY DOWN: {res_high.get('DOWN', 0):.1f}%")
    
    print("\n--- LONDON BROKE ASIA LOW (BEARISH SIGNAL?) ---")
    brk_low = df[df['Lon_Broke_AsiaLow']]
    print(f"Count: {len(brk_low)} ({len(brk_low)/total*100:.1f}%)")
    # Continuation Probability
    res_low = brk_low['NY_Dir'].value_counts(normalize=True) * 100
    print(f"  -> NY DOWN: {res_low.get('DOWN', 0):.1f}%")
    print(f"  -> NY UP: {res_low.get('UP', 0):.1f}%")
    
    # --- ANALYSIS 4: BROKEN + DIRECTION ALIGNMENT ---
    # Only if London Broke High AND London Closed Bullish (Long True)
    # Filter out fakeouts where it broke high but closed bearish
    
    print("\n--- QUALIFIED BREAKOUT: BROKE HIGH + CLOSED BULLISH ---")
    qual_high = df[(df['Lon_Broke_AsiaHigh']) & (df['Lon_Dir'] == "UP")]
    print(f"Count: {len(qual_high)} ({len(qual_high)/total*100:.1f}%)")
    q_res_high = qual_high['NY_Dir'].value_counts(normalize=True) * 100
    print(f"  -> NY UP: {q_res_high.get('UP', 0):.1f}%")
    
    print("\n--- QUALIFIED BREAKOUT: BROKE LOW + CLOSED BEARISH ---")
    qual_low = df[(df['Lon_Broke_AsiaLow']) & (df['Lon_Dir'] == "DOWN")]
    print(f"Count: {len(qual_low)} ({len(qual_low)/total*100:.1f}%)")
    q_res_low = qual_low['NY_Dir'].value_counts(normalize=True) * 100
    print(f"  -> NY DOWN: {q_res_low.get('DOWN', 0):.1f}%")

if __name__ == "__main__":
    analyze_high_frequency()
