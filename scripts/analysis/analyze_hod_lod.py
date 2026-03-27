
import pandas as pd
import numpy as np
import json
import os
from datetime import datetime, time

def analyze_hod_lod(ticker="NQ1"):
    print(f"--- Starting Master Trader HOD/LOD Analysis for {ticker} ---")
    
    # 1. Load Data
    # Path configuration
    base_dir = "c:/Users/vinay/tvDownloadOHLC/data"
    hod_path = f"{base_dir}/{ticker}_daily_hod_lod.json"
    sessions_path = f"{base_dir}/sessions/{ticker}_sessions.json"
    class_path = f"{base_dir}/derived/{ticker}_daily_classification.parquet"
    
    # Load Daily Classification (for context)
    if os.path.exists(class_path):
        df_class = pd.read_parquet(class_path)
        df_class['date'] = pd.to_datetime(df_class['date'])
        # Ensure date string for merging
        df_class['date_str'] = df_class['date'].dt.strftime('%Y-%m-%d')
    else:
        print(f"Error: {class_path} not found.")
        return

    # ---------------------------------------------------------
    # PART 1: TIMING THE HIGH & LOW (The "Reversal Clock")
    # ---------------------------------------------------------
    if os.path.exists(hod_path):
        print("\n## 1. Timing the High & Low (The 'Fakeout Clock')")
        with open(hod_path, 'r') as f:
            data_hod = json.load(f)
        df_hod = pd.DataFrame.from_dict(data_hod, orient='index')
        
        # Ensure times are parsed (HM format, e.g. "10:35")
        # Filter out bad data
        df_hod = df_hod.dropna(subset=['hod_time', 'lod_time'])
        
        # Convert to datetime objects for binning
        # Using arbitrary date to extract time
        df_hod['ht'] = pd.to_datetime(df_hod['hod_time'], format='%H:%M').dt.time
        df_hod['lt'] = pd.to_datetime(df_hod['lod_time'], format='%H:%M').dt.time
        
        # Define 30-min Buckets for Binning
        bins_vals = [time(9,30), time(10,0), time(10,30), time(11,30), time(13,30), time(15,0), time(16,0), time(23,59)]
        labels = ["09:30-10:00 (Open)", "10:00-10:30 (Reversal)", "10:30-11:30 (Morning)", 
                  "11:30-13:30 (Lunch)", "13:30-15:00 (Afternoon)", "15:00-16:00 (Power Hour)", "16:00+ (Close)"]
        
        # Vectorized time binning using pd.cut
        # Need to convert time objects to minutes from midnight or similar for pd.cut to work easily
        def time_to_min(t): return t.hour * 60 + t.minute
        bins_mins = [time_to_min(t) for t in bins_vals]
        
        df_hod['ht_min'] = df_hod['ht'].apply(time_to_min)
        df_hod['lt_min'] = df_hod['lt'].apply(time_to_min)
        
        df_hod['high_bin'] = pd.cut(df_hod['ht_min'], bins=bins_mins, labels=labels, right=False)
        df_hod['low_bin'] = pd.cut(df_hod['lt_min'], bins=bins_mins, labels=labels, right=False)
        
        # Calculate Distributions
        n = len(df_hod)
        h_dist = df_hod['high_bin'].value_counts(normalize=True).sort_index() * 100
        l_dist = df_hod['low_bin'].value_counts(normalize=True).sort_index() * 100
        
        print(f"\n### HOD/LOD Heatmap (n={n} days)")
        print("| Time Window | High Set % | Low Set % | Insight |")
        print("| :--- | :--- | :--- | :--- |")
        
        for label in labels:
            h = h_dist.get(label, 0)
            l = l_dist.get(label, 0)
            
            insight = ""
            if h + l > 35: insight = "HIGH ACTIVITY"
            if h < 5 and l < 5: insight = "Dead Zone"
            if "09:30" in label: insight = "Fakeout Zone"
            if "10:00" in label: insight = "Reversal Zone"
            if "16:00" in label: insight = "Trend Extension"
            
            print(f"| **{label.split(' ')[0]}** | {h:.1f}% | {l:.1f}% | {insight} |")

        # Master Trader Insight: Last Hour Extension
        prob_late_high = (df_hod['ht'] >= time(15,0)).mean() * 100
        print(f"\n> **Power Hour Stat**: {prob_late_high:.1f}% of Daily Highs are set AFTER 3:00 PM.")
    
    # ---------------------------------------------------------
    # PART 2: OVERNIGHT RANGE EDGE
    # ---------------------------------------------------------
    if os.path.exists(sessions_path):
        print("\n## 2. Overnight Range Edge (Compression Play)")
        with open(sessions_path, 'r') as f:
            sess_data = json.load(f)
        df_sess = pd.DataFrame(sess_data)
        
        # Filter for Asia and London
        on_sessions = df_sess[df_sess['session'].isin(['Asia', 'London'])]
        
        # Group by 'date' (Trade Date)
        on_stats = on_sessions.groupby('date').agg({
            'high': 'max',
            'low': 'min'
        }).reset_index()
        
        on_stats['on_range'] = on_stats['high'] - on_stats['low']
        on_stats = on_stats[on_stats['on_range'] > 0].sort_values('date')
        on_stats['avg_range'] = on_stats['on_range'].rolling(20).mean()
        
        # Vectorized Regime Calculation using np.select
        ratio = on_stats['on_range'] / on_stats['avg_range']
        conditions = [
            (ratio < 0.75),
            (ratio > 1.25),
            (ratio.notna())
        ]
        choices = ["Compressed (<75%)", "Expanded (>125%)", "Normal"]
        on_stats['regime'] = np.select(conditions, choices, default=None)
        
        # Merge with Daily Classification
        df_merged = pd.merge(df_class, on_stats, left_on='date_str', right_on='date', how='inner')
        
        print("\n### Correlation: ON Range vs Day Type")
        print("| ON Condition | R1 (Chop) | R2 (Reversal) | DWP (Pullback) | DNP (Trend) | n | Signal |")
        print("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
        
        regimes = ["Compressed (<75%)", "Normal", "Expanded (>125%)"]

        
        for r in regimes:
            subset = df_merged[df_merged['regime'] == r]
            if len(subset) < 10: continue
            
            cnts = subset['type'].value_counts(normalize=True) * 100
            n_samples = len(subset)
            
            dnp = cnts.get('DNP', 0)
            dwp = cnts.get('DWP', 0)
            directional = dnp + dwp
            
            sig = "Neutral"
            if dnp > 20: sig = "TREND LOADING"
            if directional > 50: sig = "HIGH CONVICTION"
            
            print(f"| **{r}** | {cnts.get('R1',0):.1f}% | {cnts.get('R2',0):.1f}% | {dwp:.1f}% | {dnp:.1f}% | {n_samples} | {sig} |")

if __name__ == "__main__":
    analyze_hod_lod("NQ1")
