import pandas as pd
import numpy as np
import pytz
from datetime import time, timedelta

DATA_PATH = r"c:\Users\vinay\tvDownloadOHLC\data\NQ1_1m.parquet"

def analyze_ny_am_probs():
    print("Loading Data...")
    df = pd.read_parquet(DATA_PATH)
    if df.index.tz is None:
        df.index = df.index.tz_localize(pytz.utc).tz_convert("America/New_York")
    else:
        df.index = df.index.tz_convert("America/New_York")

    # Group by Date
    # London (02:00-05:00) | Pre-NY (05:00-08:00) | NY AM (08:00-12:00)
    # We filter for days where we have full data.
    
    dates = pd.unique(df.index.date)
    results = []
    
    print(f"Analyzing {len(dates)} days...")
    
    count = 0
    for d in dates:
        count += 1
        if count == 500: print(f"Here Day 500: {d}")
        if count % 1000 == 0: print(f"Processed {count} days...")
        try:
            t02 = pd.Timestamp.combine(d, time(2,0)).tz_localize("America/New_York", ambiguous='NaT', nonexistent='shift_forward')
            t05 = pd.Timestamp.combine(d, time(5,0)).tz_localize("America/New_York", ambiguous='NaT', nonexistent='shift_forward')
            t08 = pd.Timestamp.combine(d, time(8,0)).tz_localize("America/New_York", ambiguous='NaT', nonexistent='shift_forward')
            t12 = pd.Timestamp.combine(d, time(12,0)).tz_localize("America/New_York", ambiguous='NaT', nonexistent='shift_forward')
            
            if pd.isna(t02) or pd.isna(t05) or pd.isna(t08) or pd.isna(t12):
                continue
        except Exception as e:
            if count == 500: print(f"Error Day 500: {e}")
            continue
        
        # Slices
        lon_df = df[t02:t05]
        ny_df  = df[t08:t12]
        pre_df = df[t05:t08]
        
        if count == 500:
            print(f"DEBUG Day 500: {d}")
            print(f"T02: {t02}")
            print(f"DF Index Sample: {df.index[0]}")
            slice_check = df[t02:t05]
            print(f"Slice Len: {len(slice_check)}")
        
        if lon_df.empty and ny_df.empty:
            # If both empty, obviously skip. But if one exists?
            pass
            
        if lon_df.empty or ny_df.empty:
            continue
            
        # 1. London Stats
        l_high = lon_df['high'].max()
        l_low = lon_df['low'].min()
        l_range = l_high - l_low
        
        # 2. Pre-NY Context (05-08)
        # Did Pre-NY ALREADY sweep London?
        if not pre_df.empty:
            p_high = pre_df['high'].max()
            p_low = pre_df['low'].min()
            
            p_sweeps_h = p_high > l_high
            p_sweeps_l = p_low < l_low
        else:
            p_sweeps_h = False
            p_sweeps_l = False
            
        # 3. NY AM Outcome (08:00-12:00)
        # Does NY sweep London High or Low FIRST? (If not already swept? Or even if swept?)
        # Let's look at "First Sweep AFTER 08:00".
        # Note: If Pre-NY swept High, the High is already broken. 
        # Does NY push it FURTHER (New High) or break the Low?
        # Herman's Logic: "Did Pre-London sweep Asia?" -> "What does OR/London do?"
        # Mapping:
        # Asia Range -> London Range
        # Pre-London -> Pre-NY (05-08)
        # London Session -> NY AM (08-12)
        
        # We want to know: during 08:00-12:00, does price break L_High or L_Low?
        # And which one first?
        
        ny_breaks_h = ny_df[ny_df['high'] > l_high]
        ny_breaks_l = ny_df[ny_df['low'] < l_low]
        
        safe_max = pd.Timestamp("2200-01-01").tz_localize("America/New_York")
        first_h = ny_breaks_h.index[0] if not ny_breaks_h.empty else safe_max
        first_l = ny_breaks_l.index[0] if not ny_breaks_l.empty else safe_max
        
        outcome = "Inside"
        if first_h < first_l:
            outcome = "High"
        elif first_l < first_h:
            outcome = "Low"
            
        results.append({
            'date': d,
            'london_range': l_range,
            'pre_sweeps_h': p_sweeps_h,
            'pre_sweeps_l': p_sweeps_l,
            'ny_outcome': outcome
        })
        
    res_df = pd.DataFrame(results)
    
    # --- ANALYSIS ---
    # 1. Determine "Large" London
    avg_lon = res_df['london_range'].mean()
    median_lon = res_df['london_range'].median()
    print(f"\nAverage London Range: {avg_lon:.2f} pts")
    print(f"Median London Range:  {median_lon:.2f} pts")
    
    # Let's use Median as cutoff for Robustness? Or Mean? Herman uses Avg (70.9).
    cutoff = avg_lon
    res_df['is_large'] = res_df['london_range'] > cutoff
    
    def print_bucket(name, subset):
        if len(subset) == 0: return
        print(f"\n--- {name} (n={len(subset)}) ---")
        counts = subset['ny_outcome'].value_counts()
        total = len(subset)
        for k, v in counts.items():
            print(f"  {k}: {v} ({v/total*100:.1f}%)")
            
    # Bucket 1: Large vs Small London
    print("\n[FACTOR 1: London Range Size]")
    print_bucket("Small London (< Avg)", res_df[~res_df['is_large']])
    print_bucket("Large London (> Avg)", res_df[res_df['is_large']])
    
    # Bucket 2: Pre-NY Context (Herman's "Setup")
    print("\n[FACTOR 2: Pre-NY (05-08) Context]")
    
    # Case A: Pre-NY stayed INSIDE London (No Sweeps)
    inside_pre = res_df[ (~res_df['pre_sweeps_h']) & (~res_df['pre_sweeps_l']) ]
    print_bucket("Pre-NY Inside London", inside_pre)
    
    # Case B: Pre-NY Swept High
    swept_h_pre = res_df[ res_df['pre_sweeps_h'] ]
    print_bucket("Pre-NY Swept London High", swept_h_pre)
    
    # Case C: Pre-NY Swept Low
    swept_l_pre = res_df[ res_df['pre_sweeps_l'] ]
    print_bucket("Pre-NY Swept London Low", swept_l_pre)
    
    # Combined Drill-Down (The "Money" Stats)
    print("\n[COMBINED DRILL-DOWN: Size + Context]")
    
    # Example: Small London + Pre-NY Inside (The "Expansion" Setup?)
    s_in = res_df[ (~res_df['is_large']) & (~res_df['pre_sweeps_h']) & (~res_df['pre_sweeps_l']) ]
    print_bucket("Small London + Pre-NY Inside", s_in)
    
    # Example: Large London + Pre-NY Sweep High (The "Reversal" Setup?)
    l_sh = res_df[ (res_df['is_large']) & (res_df['pre_sweeps_h']) ]
    print_bucket("Large London + Pre-NY Swept High", l_sh)

if __name__ == "__main__":
    analyze_ny_am_probs()
