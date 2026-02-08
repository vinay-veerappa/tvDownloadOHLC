import json
import pandas as pd
import numpy as np
import os
import sys

def analyze_ny1_true_conditions():
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
    
    # Define "True" Outcome
    # True = Long True OR Short True (Trend Expansion)
    df['NY_True'] = df['NY_Status'].isin(['Long True', 'Short True'])
    
    print(f"Total Days: {len(df)}")
    
    # 1. Base Rate
    base_rate = df['NY_True'].mean() * 100
    print(f"\n--- BASE RATE: NY1 'True' (Trend) ---")
    print(f"Probability: {base_rate:.1f}%")
    
    # 2. Condition Scans
    print("\n--- CONDITIONAL PROBABILITIES (> Base Rate) ---")
    
    # A. Correlated Trend (Asia True + London True)
    cond_aligned_true = (df['Asia_Status'].isin(['Long True', 'Short True'])) & (df['London_Status'].isin(['Long True', 'Short True']))
    subset_aligned = df[cond_aligned_true]
    prob_aligned = subset_aligned['NY_True'].mean() * 100
    print(f"Both Asia & London 'True' (n={len(subset_aligned)}): {prob_aligned:.1f}%")
    
    # B. Expansion Reversal (Tree A context)
    # Actually, Tree A predicts Reversal (False). So we expect LOW True rate here.
    # Let's check anyway.
    
    # C. London Range Size
    # Does a Large London Range imply NY Trend?
    df['Lon_Range_Q'] = pd.qcut(df['London_Range'], 3, labels=["Small", "Med", "Large"])
    
    for r in ['Small', 'Med', 'Large']:
        sub = df[df['Lon_Range_Q'] == r]
        p = sub['NY_True'].mean() * 100
        print(f"London Range {r}: {p:.1f}%")
        
    # D. London 'True' Status (Momentum)
    cond_lon_true = df['London_Status'].isin(['Long True', 'Short True'])
    sub_lon_true = df[cond_lon_true]
    p_lon_true = sub_lon_true['NY_True'].mean() * 100
    print(f"London itself was 'True' (Trend): {p_lon_true:.1f}%")
    
    # E. London 'False' Status (Reversal/Chop)
    cond_lon_false = df['London_Status'].isin(['Long False', 'Short False'])
    sub_lon_false = df[cond_lon_false]
    p_lon_false = sub_lon_false['NY_True'].mean() * 100
    print(f"London itself was 'False' (Reversal): {p_lon_false:.1f}%")

    # F. Asia Inside
    cond_asia_inside = df['Asia_Status'].isin(['None', 'Inside'])
    sub_asia_in = df[cond_asia_inside]
    p_asia_in = sub_asia_in['NY_True'].mean() * 100
    print(f"Asia was Inside/Quiet: {p_asia_in:.1f}%")

if __name__ == "__main__":
    analyze_ny1_true_conditions()
