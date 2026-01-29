import pandas as pd
import numpy as np
import pytz
from datetime import time, timedelta

# Constants
DATA_PATH = r"c:\Users\vinay\tvDownloadOHLC\data\NQ1_1m.parquet"

# Output Container
STATS = {}

def load_data():
    print("Loading NQ data...")
    df = pd.read_parquet(DATA_PATH)
    if df.index.tz is None:
        df.index = df.index.tz_localize(pytz.utc).tz_convert("America/New_York")
    else:
        df.index = df.index.tz_convert("America/New_York")
    return df

def process_day(df, date):
    # Timestamps (Safe Handling)
    try:
        # Asia (Prev 20:00 - 00:00 usually, but let's treat Asia as "Overnight Context")
        # To simplify: We define sessions relative to current day 09:30.
        
        # Asia: 18:00 (Prev) to 02:00? No, Herman Manual says Asia 20:00-00:00.
        # But we need "Asia Trend".
        # Let's stick to Herman: Asia = 20:00-00:00. London = 02:00-05:00 (or 03-05).
        # We need to capture "Asia" correctly.
        
        # Construct timestamps
        # Asia Start: 20:00 Prev Day
        # 02:00 is "Today". 20:00 Prev is -6 hours? No, 20:00 is 18h before 14:00.
        # Let's assume 'date' is the NY AM date.
        
        t_asia_s = pd.Timestamp.combine(date - timedelta(days=1), time(20,0)).tz_localize("America/New_York", ambiguous='NaT', nonexistent='shift_forward')
        t_asia_e = pd.Timestamp.combine(date, time(0,0)).tz_localize("America/New_York", ambiguous='NaT', nonexistent='shift_forward')
        
        # London (Full range for context)
        t_lon_s = pd.Timestamp.combine(date, time(2,0)).tz_localize("America/New_York", ambiguous='NaT', nonexistent='shift_forward')
        t_lon_e = pd.Timestamp.combine(date, time(5,0)).tz_localize("America/New_York", ambiguous='NaT', nonexistent='shift_forward') # Playbook expanded to 05:00
        
        # Pre-NY (Gap)
        t_pre_s = pd.Timestamp.combine(date, time(5,0)).tz_localize("America/New_York", ambiguous='NaT', nonexistent='shift_forward')
        t_pre_e = pd.Timestamp.combine(date, time(8,0)).tz_localize("America/New_York", ambiguous='NaT', nonexistent='shift_forward')
        
        # NY AM (Full)
        t_ny_s = pd.Timestamp.combine(date, time(8,0)).tz_localize("America/New_York", ambiguous='NaT', nonexistent='shift_forward')
        t_ny_e = pd.Timestamp.combine(date, time(11,0)).tz_localize("America/New_York", ambiguous='NaT', nonexistent='shift_forward')
        
        # 9:30 Open
        t_open = pd.Timestamp.combine(date, time(9,30)).tz_localize("America/New_York", ambiguous='NaT', nonexistent='shift_forward')
        
        # Slice
        asia = df[t_asia_s:t_asia_e]
        lon = df[t_lon_s:t_lon_e]
        pre = df[t_pre_s:t_pre_e]
        ny_am = df[t_ny_s:t_ny_e]
        ny_open = df[t_open:t_ny_e] # 09:30 onwards
        
        if asia.empty or lon.empty or ny_am.empty:
            return None
            
        # --- 1. ASIA STATS ---
        a_high = asia['high'].max()
        a_low = asia['low'].min()
        a_range = a_high - a_low
        a_is_large = a_range > 70.9 # Using Herman's constant
        
        # --- 2. LONDON STATS ---
        l_high = lon['high'].max()
        l_low = lon['low'].min()
        l_range = l_high - l_low
        # London Trend relative to Asia?
        # Did London break Asia High or Low?
        l_swept_ah = l_high > a_high
        l_swept_al = l_low < a_low
        
        # Define "London Mode":
        # - "Herman Trend Up": London Swept Asia High (and held?)
        # - "Herman Trend Down": London Swept Asia Low
        # - "Inside": London inside Asia
        # - "Outside": London swept both
        
        l_mode = "Inside"
        if l_swept_ah and not l_swept_al: l_mode = "Trend Up"
        elif l_swept_al and not l_swept_ah: l_mode = "Trend Down"
        elif l_swept_ah and l_swept_al: l_mode = "Outside"
        
        # --- 3. PRE-NY STATS ---
        # Did Pre-NY (05-08) break London?
        # Note: London Range is the REFERENCE for NY.
        if not pre.empty:
            p_high = pre['high'].max()
            p_low = pre['low'].min()
            p_swept_lh = p_high > l_high
            p_swept_ll = p_low < l_low
        else:
            p_swept_lh = False
            p_swept_ll = False
            
        pre_mode = "Inside"
        if p_swept_lh: pre_mode = "Break High"
        if p_swept_ll: pre_mode = "Break Low" # Priority to low if both? or last? Keeping simple.
        
        # --- 4. NY AM OUTCOMES (08:00 Start) ---
        # Target: Does NY AM break London High or Low?
        # (If Pre-NY already broke it, we check if it breaks FURTHER? 
        # Actually Herman usually checks "Session High/Low" reference.
        # Let's stick to: Does NY AM break the [London High, London Low] boundaries?
        
        ny_breaks_lh = ny_am[ny_am['high'] > l_high]
        ny_breaks_ll = ny_am[ny_am['low'] < l_low]
        
        
        # Safe Future Date for comparison
        safe_max = pd.Timestamp("2200-01-01").tz_localize("America/New_York")

        f_h_time = ny_breaks_lh.index[0] if not ny_breaks_lh.empty else safe_max
        f_l_time = ny_breaks_ll.index[0] if not ny_breaks_ll.empty else safe_max

        res_8am = "Inside"
        if f_h_time < f_l_time: res_8am = "High"
        elif f_l_time < f_h_time: res_8am = "Low"
        
        # --- 5. NY OPEN OUTCOMES (09:30 Start) ---
        # Same Logic: Does 09:30+ break London High/Low first?
        # Note: By 09:30, 08:00 might have already broken it.
        # We want to know "What is the bias AFTER 09:30?"
        
        op_breaks_lh = ny_open[ny_open['high'] > l_high]
        op_breaks_ll = ny_open[ny_open['low'] < l_low]
        
        op_h_time = op_breaks_lh.index[0] if not op_breaks_lh.empty else safe_max
        op_l_time = op_breaks_ll.index[0] if not op_breaks_ll.empty else safe_max
        
        res_930 = "Inside"
        if op_h_time < op_l_time: res_930 = "High"
        elif op_l_time < op_h_time: res_930 = "Low"
        
        return {
            'asia_large': a_is_large,
            'london_mode': l_mode,
            'pre_mode': pre_mode,
            'res_8am': res_8am,
            'res_930': res_930
        }

    except Exception as e:
        print(f"Error processing {date}: {e}")
        return None

def analyze():
    df = load_data()
    dates = pd.unique(df.index.date)
    print(f"Processing {len(dates)} days...")
    
    data = []
    for d in dates:
        row = process_day(df, d)
        if row: data.append(row)
        
    df_res = pd.DataFrame(data)
    
    # --- GENERATE DECISION TREES ---
    
    # 1. ROOT: Overall
    print(f"\nROOT: All Days (n={len(df_res)})")
    print(df_res['res_8am'].value_counts(normalize=True))
    
    # 2. LEVEL 1: Asia Size
    # Does Asia Size affect NY AM?
    print("\n--- LEVEL 1: Asia Size ---")
    for sz in [True, False]:
        lbl = "Large Asia" if sz else "Small Asia"
        sub = df_res[df_res['asia_large'] == sz]
        print(f"\n{lbl} (n={len(sub)})")
        print(f"8am Open Bias: {sub['res_8am'].value_counts(normalize=True).to_dict()}")
        
    # 3. LEVEL 2: London Trend (The "Setup")
    print("\n--- LEVEL 2: London Interaction (Trend) ---")
    # Does London Up/Down dictate NY?
    for mode in ['Trend Up', 'Trend Down', 'Inside', 'Outside']:
        sub = df_res[df_res['london_mode'] == mode]
        print(f"\nLondon {mode} (n={len(sub)})")
        bias_8am = sub['res_8am'].value_counts(normalize=True)
        # Check strong signals (> 60%)
        print(f"8am Bias: {bias_8am.to_dict()}")
        
    # 4. LEVEL 3: Pre-NY Context (The "Immediate" Trigger)
    print("\n--- LEVEL 3: Pre-NY (05-08) Context ---")
    # This was our "Money" stat before. Let's see if London Trend filters it.
    
    # Hierarchy: London Trend -> Pre-NY -> NY
    # Example: London Trend Up + Pre-NY Break High -> ??
    
    grouped = df_res.groupby(['london_mode', 'pre_mode'])
    print("\n[Detailed Tree: London Mode + Pre-NY Action]")
    for name, group in grouped:
        if len(group) < 50: continue # Skip noise
        print(f"\nContext: {name} (n={len(group)})")
        probs_8am = group['res_8am'].value_counts(normalize=True)
        probs_930 = group['res_930'].value_counts(normalize=True)
        
        # Format nice string
        h8 = probs_8am.get('High', 0)*100
        l8 = probs_8am.get('Low', 0)*100
        print(f"  -> 08:00 Bias: High {h8:.1f}% | Low {l8:.1f}%")
        
        h9 = probs_930.get('High', 0)*100
        l9 = probs_930.get('Low', 0)*100
        print(f"  -> 09:30 Bias: High {h9:.1f}% | Low {l9:.1f}%")

if __name__ == "__main__":
    analyze()
