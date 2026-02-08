import json
import pandas as pd
import numpy as np
import os
import sys

def analyze_large_range_continuation():
    profiler_path = r"c:\Users\vinay\tvDownloadOHLC\data\NQ1_profiler.json"
    
    if not os.path.exists(profiler_path):
        print("Profiler JSON not found.")
        return

    print("1. Loading Profiler Data...")
    with open(profiler_path, 'r') as f:
        p_data = json.load(f)
    
    df_p = pd.DataFrame(p_data)
    df_p['date_str'] = pd.to_datetime(df_p['date']).dt.strftime('%Y-%m-%d')
    
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

    df = pd.DataFrame.from_dict(daily_records, orient='index')
    df = df.dropna(subset=['Asia_Status', 'London_Status', 'NY_Status'])
    
    # Define Directions
    def get_dir(status):
        if status in ['Long True', 'Short False']: return "UP"
        if status in ['Short True', 'Long False']: return "DOWN"
        return "NEUTRAL"
        
    df['Lon_Dir'] = df['London_Status'].apply(get_dir)
    df['NY_Dir'] = df['NY_Status'].apply(get_dir)
    
    # Quantile Cut London Range
    df['Lon_Range_Q'] = pd.qcut(df['London_Range'], 3, labels=["Small", "Med", "Large"])
    
    print(f"Total Days: {len(df)}")
    
    # --- ANALYSIS: MOMENTUM CONTINUATION BY RANGE SIZE ---
    # If London is UP, does a Large Range imply NY UP?
    
    for r_size in ['Small', 'Med', 'Large']:
        subset = df[(df['Lon_Dir'] == "UP") & (df['Lon_Range_Q'] == r_size)]
        if len(subset) == 0: continue
        
        cont_prob = subset['NY_Dir'].value_counts(normalize=True).get('UP', 0) * 100
        print(f"\nLondon UP + {r_size} Range (Count: {len(subset)})")
        print(f"  -> NY Continuation UP: {cont_prob:.1f}%")
        
        subset_dn = df[(df['Lon_Dir'] == "DOWN") & (df['Lon_Range_Q'] == r_size)]
        if len(subset_dn) == 0: continue
        
        cont_prob_dn = subset_dn['NY_Dir'].value_counts(normalize=True).get('DOWN', 0) * 100
        print(f"London DOWN + {r_size} Range (Count: {len(subset_dn)})")
        print(f"  -> NY Continuation DOWN: {cont_prob_dn:.1f}%")

if __name__ == "__main__":
    analyze_large_range_continuation()
