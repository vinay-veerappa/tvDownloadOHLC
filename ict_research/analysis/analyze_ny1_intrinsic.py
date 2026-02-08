import json
import pandas as pd
import numpy as np
import os
import sys

def analyze_ny1_intrinsic():
    profiler_path = r"c:\Users\vinay\tvDownloadOHLC\data\NQ1_profiler.json"
    
    if not os.path.exists(profiler_path):
        print("Profiler JSON not found.")
        return

    print("1. Loading Profiler Data...")
    with open(profiler_path, 'r') as f:
        p_data = json.load(f)
    
    df_p = pd.DataFrame(p_data)
    df_p['date_dt'] = pd.to_datetime(df_p['date'])
    df_p['day_of_week'] = df_p['date_dt'].dt.day_name()
    
    # Filter for NY AM (NY1)
    # The JSON uses 'NY AM' or 'NY1'
    df_ny1 = df_p[df_p['session'].isin(['NY AM', 'NY1'])].copy()
    
    print(f"\nTotal NY1 Sessions: {len(df_ny1)}")
    
    # --- 1. BASE RATE PROBABILITIES ---
    print("\n--- BASE RATES (NY1 STATUS) ---")
    status_counts = df_ny1['status'].value_counts(normalize=True) * 100
    print(status_counts.round(1))
    
    # Define Higher Level Categories
    # Trend = Long True / Short True
    # Reversal = Long False / Short False
    # Inside = None
    
    def get_type(status):
        if status in ['Long True', 'Short True']: return "TREND"
        if status in ['Long False', 'Short False']: return "REVERSAL"
        return "INSIDE"
        
    df_ny1['Type'] = df_ny1['status'].apply(get_type)
    
    print("\n--- STRUCTURE TYPE ---")
    type_counts = df_ny1['Type'].value_counts(normalize=True) * 100
    print(type_counts.round(1))
    
    # --- 2. DAY OF WEEK ANALYSIS ---
    # Does Monday Trend more? Does Friday Reverse more?
    
    print("\n--- DAY OF WEEK EDGE ---")
    # Pivot Type by Day
    dow_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    df_ny1['day_of_week'] = pd.Categorical(df_ny1['day_of_week'], categories=dow_order, ordered=True)
    
    dow_stats = df_ny1.groupby('day_of_week', observed=False)['Type'].value_counts(normalize=True).unstack().fillna(0) * 100
    print(dow_stats.round(1))
    
    # --- 3. DIRECTIONAL BIAS PER DAY ---
    # Is Monday bullish?
    def get_dir(status):
        if status == 'Long True': return "UP"
        if status == 'Short True': return "DOWN"
        if status == 'Short False': return "UP" # Reversal Up
        if status == 'Long False': return "DOWN" # Reversal Down
        return "NEUTRAL"
        
    df_ny1['Dir'] = df_ny1['status'].apply(get_dir)
    dir_stats = df_ny1.groupby('day_of_week', observed=False)['Dir'].value_counts(normalize=True).unstack().fillna(0) * 100
    
    print("\n--- DIRECTIONAL BIAS PER DAY ---")
    print(dir_stats[['UP', 'DOWN']].round(1))
    
    # Any standout days? (>55%)
    print("\n--- SIGNIFICANT EDGES (>55%) ---")
    for day in dow_order:
        up = dir_stats.loc[day, 'UP']
        dn = dir_stats.loc[day, 'DOWN']
        if up > 55: print(f"{day}: BULLISH BIAS ({up:.1f}%)")
        if dn > 55: print(f"{day}: BEARISH BIAS ({dn:.1f}%)")
        
    # --- 4. CONTINUATION PROBABILITY ---
    # If NY1 Breaks High, does it STAY High? (Long True vs Long False)
    # This measures "Follow Through"
    
    print("\n--- BREAKOUT FOLLOW-THROUGH ---")
    long_attempts = df_ny1[df_ny1['status'].str.contains('Long')]
    long_success = long_attempts['status'].value_counts(normalize=True).get('Long True', 0) * 100
    print(f"Upside Breakout Success Rate: {long_success:.1f}%")
    
    short_attempts = df_ny1[df_ny1['status'].str.contains('Short')]
    short_success = short_attempts['status'].value_counts(normalize=True).get('Short True', 0) * 100
    print(f"Downside Breakout Success Rate: {short_success:.1f}%")

if __name__ == "__main__":
    analyze_ny1_intrinsic()
