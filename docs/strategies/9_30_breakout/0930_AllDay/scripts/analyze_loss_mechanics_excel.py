
"""
Loss Mechanics Forensics (EXCEL EDITION)
========================================
Validating findings using the Official TradingView Export.
Source: ORB_V3_CME_MINI_MNQ1!_2026-01-07_6f55a.xlsx

Inputs:
- docs/strategies/.../ORB_V3...xlsx (List of trades)
- data/NQ1_opening_range.json
- data/NQ1_profiler.json

Outputs:
- Stop Location Analysis (Inside OR vs Outside)
- Time of Day Histogram (When do we stop out?)
"""

import pandas as pd
import numpy as np
import json
import os
import sys

EXCEL_PATH = r"c:\Users\vinay\tvDownloadOHLC\docs\strategies\9_30_breakout\0930_AllDay\ORB_V3_CME_MINI_MNQ1!_2026-01-07_6f55a.xlsx"

def analyze():
    print(f"Loading Excel: {os.path.basename(EXCEL_PATH)}...")
    
    # 1. TRADES

    try:
        # Load 'List of trades'
        df = pd.read_excel(EXCEL_PATH, sheet_name="List of trades")
        
        # Debug: Print Columns
        print(f"Columns Found: {df.columns.tolist()}")
        
        # Normalize columns (strip spaces)
        df.columns = df.columns.str.strip()
        

        # Correct Columns from Log
        # ['Trade #', 'Type', 'Date and time', 'Signal', 'Price USD', 'Position size (qty)', 'Position size (value)', 'Net P&L USD', ...]
        
        trades = []
        for t_id, t_group in df.groupby('Trade #'):
            t_group = t_group.sort_values('Date and time')
            
            if len(t_group) < 2: continue
            
            entry_row = t_group.iloc[0]
            exit_row = t_group.iloc[-1]
            
            direction = "Long" if "Long" in entry_row['Type'] else "Short"
            
            # Map Columns
            entry_time = entry_row['Date and time']
            exit_time = exit_row['Date and time']
            entry_px = entry_row['Price USD']
            exit_px = exit_row['Price USD']
            
            # Profit
            profit = t_group['Net P&L USD'].sum()
            
            pnl_pct = (exit_px - entry_px) / entry_px * (1 if direction == "Long" else -1)
            
            trades.append({
                'TradeNum': t_id,
                'Direction': direction,
                'Entry Time': entry_time,
                'Exit Time': exit_time, # Full datetime
                'Entry Price': entry_px,
                'Exit Price': exit_px,
                'P&L': profit,
                'Gross P&L %': pnl_pct
            })
            
        trades_df = pd.DataFrame(trades)
        
        # Normalize Timestamps
        # The 'Exit Time' is already a datetime object from Excel
        # Just ensure TZ aware
        trades_df['entry_dt'] = pd.to_datetime(trades_df['Entry Time']).dt.tz_localize(None).dt.tz_localize('America/New_York')
        trades_df['exit_dt'] = pd.to_datetime(trades_df['Exit Time']).dt.tz_localize(None).dt.tz_localize('America/New_York')
        trades_df['date'] = trades_df['entry_dt'].dt.date
        
        print(f"Parsed {len(trades_df)} Trades from Excel.") 
        
    except Exception as e:
        print(f"Error loading Excel: {e}")
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

    # FILTER FOR LOSERS
    # Profit < 0
    losers = trades_df[trades_df['P&L'] < 0].copy()
    print(f"Analyzing {len(losers)} Losers (out of {len(trades_df)} total trades)...")
    
    # METRICS
    loc_inside_or = 0
    loc_full_reversal = 0
    loc_mae = 0
    
    time_bins = {}
    
    for idx, row in losers.iterrows():
        d = row['date']
        direction = row['Direction'] 
        entry_px = row['Entry Price']
        exit_px = row['Exit Price']
        
        # 1. STOP LOCATION
        # In Excel we don't know "MAE Exit" tag vs "SL Hit" tag easily unless we parse Signal name?
        # Signal name often has "Exit" or "SL".
        # But we can infer location logic same as before.
        
        if d in or_dict:
            or_info = or_dict[d]
            or_h = or_info['high']
            or_l = or_info['low']
            
            is_reversal = False
            is_chop = False
            
            if direction == 'Long':
                if exit_px <= or_l + 1.25: # Buffer 5 ticks
                    is_reversal = True
                elif exit_px < or_h:
                    is_chop = True
                    
            elif direction == 'Short':
                if exit_px >= or_h - 1.25: # Buffer
                    is_reversal = True
                elif exit_px > or_l:
                    is_chop = True
            
            if is_reversal: loc_full_reversal += 1
            elif is_chop: loc_inside_or += 1
        
        # 2. TIME DENSITY
        exit_h = row['exit_dt'].hour
        exit_m = row['exit_dt'].minute
        
        bucket_m = 0 if exit_m < 30 else 30
        time_key = f"{exit_h:02d}:{bucket_m:02d}"
        time_bins[time_key] = time_bins.get(time_key, 0) + 1

    print("\n--- STOP LOCATION ANALYSIS (EXCEL DATA) ---")
    print(f"Chop Stops (Strictly Inside)  : {loc_inside_or} ({loc_inside_or/len(losers)*100:.1f}%) -> Stuck in noise")
    print(f"Full Reversals (Hit Opp. Bound): {loc_full_reversal} ({loc_full_reversal/len(losers)*100:.1f}%) -> Failed Breakout")

    print("\n--- TIME OF DEATH (Exit Time ET) ---")
    sorted_times = sorted(time_bins.items())
    for k, v in sorted_times:
        print(f"{k} : {v} ({v/len(losers)*100:.1f}%)")

if __name__ == "__main__":
    analyze()
