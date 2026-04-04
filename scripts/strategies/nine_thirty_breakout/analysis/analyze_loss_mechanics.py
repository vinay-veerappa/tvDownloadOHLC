
"""
Loss Mechanics Forensics
========================
Deep dive into WHY and WHEN trades fail.

Inputs:
- local_backtest_results.csv (Trades)
- data/NQ1_opening_range.json (OR High/Low)
- data/NQ1_profiler.json (Context)

Outputs:
- Stop Location Analysis (Inside OR vs Outside)
- Time of Day Histogram (When do we stop out?)
- Context Correlations
"""

import pandas as pd
import numpy as np
import json
import os
import sys

def analyze():
    print("Loading Data for Forensics...")
    

    # 1. TRADES
    try:
        trades_df = pd.read_csv("local_backtest_results.csv")
        
        # FIX: Entry Time is Full ISO with TZ. Exit Time is Time-Only string.
        # Parse Entry (Aware)
        trades_df['entry_dt'] = pd.to_datetime(trades_df['Entry Time'], utc=True).dt.tz_convert('America/New_York')
        trades_df['date'] = trades_df['entry_dt'].dt.date
        
        # Reconstruct Exit Datetime: Combine Date + Exit Time String
        trades_df['exit_dt_str'] = trades_df['date'].astype(str) + ' ' + trades_df['Exit Time']
        trades_df['exit_dt'] = pd.to_datetime(trades_df['exit_dt_str']).dt.tz_localize('America/New_York')
        
    except Exception as e:
        print(f"Error loading local_backtest_results.csv: {e}")
        return

    # 2. OPENING RANGE
    try:
        with open(r"c:\Users\vinay\tvDownloadOHLC\data\NQ1_opening_range.json", "r") as f:
            or_data = json.load(f)
        or_df = pd.DataFrame(or_data)
        or_df['date_obj'] = pd.to_datetime(or_df['date']).dt.date
        or_dict = or_df.set_index('date_obj')[['high', 'low', 'range_pts']].to_dict('index')
    except:
        print("Error loading NQ1_opening_range.json")
        or_dict = {}

    # 3. PROFILER
    try:
        with open(r"c:\Users\vinay\tvDownloadOHLC\data\NQ1_profiler.json", "r") as f:
            prof_data = json.load(f)
        prof_df = pd.DataFrame(prof_data)
        prof_df['date_obj'] = pd.to_datetime(prof_df['date']).dt.date
        prof_dict = prof_df.set_index('date_obj').to_dict('index') 
        # Note: Profiler has multiple rows per date (NY1, NY2). 
        # Dictionary lookup by date might just get last one.
        # Better: Groupby date
        prof_grouped = prof_df.groupby('date_obj')
    except:
        print("Error loading NQ1_profiler.json")
        prof_grouped = None

    # FILTER FOR LOSERS
    losers = trades_df[trades_df['Gross P&L %'] < 0].copy()
    print(f"Analyzing {len(losers)} Losers (out of {len(trades_df)} total trades)...")
    
    # METRICS
    loc_inside_or = 0
    loc_full_reversal = 0
    loc_mae = 0
    
    time_bins = {}
    
    for idx, row in losers.iterrows():
        d = row['date']
        direction = row['Direction'] # Long/Short
        entry_px = row['Entry Price']
        exit_px = row['Exit Price']
        exit_type = row['Type'] # 'SL Hit', 'MAE Exit', 'Hard Exit'
        
        # 1. STOP LOCATION
        if exit_type == 'MAE Exit':
            loc_mae += 1
        elif d in or_dict:
            or_info = or_dict[d]
            or_h = or_info['high']
            or_l = or_info['low']
            
            # Logic: Strictly Inside vs Boundary (Reversal)
            is_reversal = False
            is_chop = False
            
            if direction == 'Long':
                if exit_px <= or_l + 1.0: # Buffer
                    is_reversal = True
                elif exit_px < or_h:
                    is_chop = True
                    
            elif direction == 'Short':
                if exit_px >= or_h - 1.0: # Buffer
                    is_reversal = True
                elif exit_px > or_l:
                    is_chop = True
            
            if is_reversal: loc_full_reversal += 1
            elif is_chop: loc_inside_or += 1 
        
        # 2. TIME DENSITY
        # Bin by 30m of Exit Time
        # Exit Time is a datetime object
        exit_h = row['exit_dt'].hour
        exit_m = row['exit_dt'].minute
        
        # Round to nearest 30m?
        # Bucket: 09:30, 10:00, 10:30...
        bucket_m = 0 if exit_m < 30 else 30
        time_key = f"{exit_h:02d}:{bucket_m:02d}"
        time_bins[time_key] = time_bins.get(time_key, 0) + 1

    print("\n--- STOP LOCATION ANALYSIS ---")
    print(f"MAE Exits (Immediate Fail)    : {loc_mae} ({loc_mae/len(losers)*100:.1f}%)")
    print(f"Stops INSIDE Opening Range    : {loc_inside_or} ({loc_inside_or/len(losers)*100:.1f}%) -> 'Chop / Fakeout'")
    # Full Reversal + Pullback Stop = Remainder
    others = len(losers) - loc_mae - loc_inside_or
    print(f"Stops OUTSIDE OR (Reversals)  : {others} ({others/len(losers)*100:.1f}%) -> 'Full Reversal / Trend Change'")

    print("\n--- TIME OF DEATH (Exit Time) ---")
    sorted_times = sorted(time_bins.items())
    for k, v in sorted_times:
        print(f"{k} : {v} ({v/len(losers)*100:.1f}%)")
        
    # 3. CONTEXT (Profiler)
    # Are "Full Reversals" correlated with "False" Logic?
    # We already know Profiler Trap correlation is ~30%.
    # Let's check Correlation of 'Inside OR' stops with OR Size.
    
    print("\n--- CONTEXT: OR SIZE vs CHOP ---")
    # Hypothesis: Inside OR stops happen when OR is LARGE? (Room to move inside)
    # Or SMALL? (Easy to fall back in)
    
    small_or_stops = 0
    large_or_stops = 0
    
    for idx, row in losers.iterrows():
        d = row['date']
        exit_px = row['Exit Price']
        if d in or_dict:
            or_info = or_dict[d]
            or_h = or_info['high']
            or_l = or_info['low']
            r_pts = or_info['range_pts']
            
            # Check if Inside
            if or_l <= exit_px <= or_h:
                if r_pts < 20: small_or_stops += 1
                if r_pts > 50: large_or_stops += 1
                
    print(f"Chop Stops (Inside OR) when OR < 20pts: {small_or_stops}")
    print(f"Chop Stops (Inside OR) when OR > 50pts: {large_or_stops}")

if __name__ == "__main__":
    analyze()
