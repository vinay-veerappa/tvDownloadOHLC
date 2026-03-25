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
        daily_records[d][f"{prefix}_Range"] = row['range_high'] - row['range_low']
        # Check if high/low was broken (from the 'broken' field or inference)
        # The 'broken' field in JSON might be a string like "High", "Low", "Both", "None"
        daily_records[d][f"{prefix}_Broken"] = row['broken']

    df = pd.DataFrame.from_dict(daily_records, orient='index')
    df = df.dropna(subset=['Asia_Status', 'London_Status', 'NY_Status'])
    
    # Define Directions
    def get_dir(status):
        if status in ['Long True', 'Short False']: return "UP"
        if status in ['Short True', 'Long False']: return "DOWN"
        return "NEUTRAL"
        
    df['Asia_Dir'] = df['Asia_Status'].apply(get_dir)
    df['Lon_Dir'] = df['London_Status'].apply(get_dir)
    df['NY_Dir'] = df['NY_Status'].apply(get_dir)
    
    total = len(df)
    print(f"Total Days: {total}")
    
    # --- ANALYSIS 1: LONDON CONTINUATION (The "Trend is Friend" Baseline) ---
    # If London is UP, how often is NY UP?
    # Frequency: Very High (happens almost every day London trends)
    
    lon_up = df[df['Lon_Dir'] == "UP"]
    lon_dn = df[df['Lon_Dir'] == "DOWN"]
    
    print("\n--- BASELINE: LONDON -> NY CONTINUATION ---")
    print(f"London UP Count: {len(lon_up)} ({len(lon_up)/total*100:.1f}%)")
    up_cont = lon_up['NY_Dir'].value_counts(normalize=True)['UP'] * 100
    print(f"  -> NY continues UP: {up_cont:.1f}%")
    
    print(f"London DOWN Count: {len(lon_dn)} ({len(lon_dn)/total*100:.1f}%)")
    dn_cont = lon_dn['NY_Dir'].value_counts(normalize=True)['DOWN'] * 100
    print(f"  -> NY continues DOWN: {dn_cont:.1f}%")
    
    # --- ANALYSIS 2: ALIGNED CONTINUATION (Asia + London match) ---
    # Frequency: Moderate
    
    aligned_up = df[(df['Asia_Dir'] == "UP") & (df['Lon_Dir'] == "UP")]
    aligned_dn = df[(df['Asia_Dir'] == "DOWN") & (df['Lon_Dir'] == "DOWN")]
    
    print("\n--- ALIGNED CONTINUATION (ASIA + LONDON MATCH) ---")
    print(f"Aligned UP Count: {len(aligned_up)} ({len(aligned_up)/total*100:.1f}%)")
    al_up_cont = aligned_up['NY_Dir'].value_counts(normalize=True).get('UP', 0) * 100
    print(f"  -> NY continues UP: {al_up_cont:.1f}%")
    
    print(f"Aligned DOWN Count: {len(aligned_dn)} ({len(aligned_dn)/total*100:.1f}%)")
    al_dn_cont = aligned_dn['NY_Dir'].value_counts(normalize=True).get('DOWN', 0) * 100
    print(f"  -> NY continues DOWN: {al_dn_cont:.1f}%")
    
    # --- ANALYSIS 3: THE "BROKEN" SIGNAL ---
    # Does breaking a prior session Mid/High/Low signal continuation?
    # We'll use 'London_Broken' field. 
    # Logic: If London broke "High", it implies strength.
    
    print("\n--- LONDON BREAKOUT SIGNALS ---")
    # Clean up broken field if needed (assuming 'High', 'Low', 'None', 'Both')
    # Filter where London specifically broke ONLY High (Bullish intent) or ONLY Low (Bearish intent)
    
    lon_brk_high = df[df['London_Broken'] == 'High']
    print(f"London Broke High (Count: {len(lon_brk_high)})")
    print(lon_brk_high['NY_Dir'].value_counts(normalize=True) * 100)
    
    lon_brk_low = df[df['London_Broken'] == 'Low']
    print(f"London Broke Low (Count: {len(lon_brk_low)})")
    print(lon_brk_low['NY_Dir'].value_counts(normalize=True) * 100)
    
    # --- ANALYSIS 4: ASIA "INSIDE" + LONDON TREND (The "Breakout" Setup) ---
    # How often does it work vs fail?
    
    asia_ins = df[df['Asia_Status'].isin(['None', 'Inside'])]
    asia_ins_lon_up = asia_ins[asia_ins['Lon_Dir'] == "UP"]
    
    print("\n--- ASIA INSIDE -> LONDON BREAKOUT ---")
    print(f"Asia Inside -> London UP (Count: {len(asia_ins_lon_up)})")
    # Outcome?
    print(asia_ins_lon_up['NY_Dir'].value_counts(normalize=True) * 100)

if __name__ == "__main__":
    analyze_high_frequency()
