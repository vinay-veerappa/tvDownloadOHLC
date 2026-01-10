
"""
Judas Swing Analysis
====================
Focus: 09:30 - 09:45 ET Entries ("The Kill Zone")
Hypothesis: First move is a "Judas Swing" (False Breakout) that reverses by 09:44.
Question: Did we miss TP1 (0.15%)? Or did we never reach it?

Comparisons:
- V3 (Current)
- V2 (Old)
- V7G (Hybrid)
"""

import pandas as pd
import numpy as np
import os
import sys

# FILES
V3_FILE = r"c:\Users\vinay\tvDownloadOHLC\docs\strategies\9_30_breakout\0930_AllDay\ORB_V3_CME_MINI_MNQ1!_2026-01-07_6f55a.xlsx"
V2_FILE = r"c:\Users\vinay\tvDownloadOHLC\docs\strategies\9_30_breakout\0930_AllDay\old\ORB_All-Day_V2_CME_MINI_MNQ1!_2026-01-07_06a7f.xlsx"
V7G_FILE = r"c:\Users\vinay\tvDownloadOHLC\docs\strategies\9_30_breakout\0930_AllDay\old\ORB_V7G_-_Hybrid_CME_MINI_MNQ1!_2026-01-07_2a886.xlsx"

FILES = {
    "V3 (Current)": V3_FILE,
    # "V2 (Old)": V2_FILE,  # Comment out if file not found or structure differs significantly
    # "V7G (Hybrid)": V7G_FILE
}

# TP1 Threshold
TP1_PCT = 0.15 # 0.15%

def analyze_file(name, path):
    print(f"\n--- Analyzing {name} ---")
    if not os.path.exists(path):
        print(f"File not found: {path}")
        return

    try:
        df = pd.read_excel(path, sheet_name="List of trades")
        df.columns = df.columns.str.strip()
        
        # Columns: 'Trade #', 'Date and time', 'Net P&L USD', 'MFE %'
        # Group by Trade #
        trades = []
        for t_id, t_group in df.groupby('Trade #'):
            t_group = t_group.sort_values('Date and time')
            entry_row = t_group.iloc[0]
            exit_row = t_group.iloc[-1]
            
            entry_time = entry_row['Date and time'] # Datetime object
            exit_time = exit_row['Date and time']
            
            net_pnl = t_group['Net P&L USD'].sum()
            
            # MFE is usually max of the group?
            # Or is it populated on a specific row?
            # Usually on Exit row or distinct. Let's take MAX of MFE % col
            if 'MFE %' in t_group.columns:
                mfe = t_group['MFE %'].max()
            else:
                mfe = 0.0
                
            trades.append({
                'Entry Time': entry_time,
                'Exit Time': exit_time,
                'P&L': net_pnl,
                'MFE %': mfe
            })
            
        t_df = pd.DataFrame(trades)
        
        # TZ Awareness
        t_df['entry_dt'] = pd.to_datetime(t_df['Entry Time']).dt.tz_localize(None).dt.tz_localize('America/New_York')
        t_df['time'] = t_df['entry_dt'].dt.time
        
        # FILTER: 09:30 - 09:45
        # Start: 09:30:00
        # End: 09:45:00
        from datetime import time
        start_t = time(9, 30)
        end_t = time(9, 45)
        
        # Pandas time comparison
        judas_trades = t_df[(t_df['time'] >= start_t) & (t_df['time'] <= end_t)].copy()
        
        count = len(judas_trades)
        losers = judas_trades[judas_trades['P&L'] < 0].copy()
        loss_count = len(losers)
        
        win_rate = (count - loss_count) / count * 100 if count > 0 else 0
        
        # DEATH BY 09:44?
        # Check exit time of losers
        losers['exit_dt'] = pd.to_datetime(losers['Exit Time']).dt.tz_localize(None).dt.tz_localize('America/New_York')
        losers['exit_time'] = losers['exit_dt'].dt.time
        died_by_944 = losers[losers['exit_time'] <= time(9, 44)]
        
        # MFE ANALYSIS (Why did we lose?)
        # Did we hit TP1 (0.15%)?
        # Note: MFE % in Excel is usually a whole number (e.g. 0.15) OR decimal (0.0015)?
        # Let's inspect ONE value. 
        # Heuristic: If mean MFE is > 1.0, it's %, else decimal.
        # But indices MFE is small.
        # Let's assume user input 0.15% = 0.15 in 'MFE %' column if formatted as %.
        # Actually TV 'MFE %' column is raw number. 
        # If it says "0.15%", the value is 0.15. 
        # If the strategy uses 0.0015 (decimal).
        # We need to check scale. 
        # Let's print sample MFE.
        if not losers.empty:
            sample_mfe = losers['MFE %'].iloc[0]
            print(f"Sample MFE Value: {sample_mfe}")
        
        # Assuming MFE % column is literally percentage points (e.g. 0.15 = 0.15%).
        # If it's pure decimal, 0.15% = 0.0015.
        # Usually TV exports "0.15" for 0.15%.
        
        # Threshold Check
        # If sample is > 0.01 (1%), then likely whole numbers. 
        # If sample < 0.01, likely decimal. 
        # Typical move 20pts on 15000 is 0.13%. 
        # If format is 0.13, threshold is 0.15.
        # If format is 0.0013, threshold is 0.0015.
        
        # We'll adapt in logic or verify manually. 
        # V3 TP1 is 0.15%.
        
        target_hit_but_lost = 0
        never_reached_target = 0
        
        for idx, row in losers.iterrows():
            mfe = row['MFE %']
            # Heuristic scale check
            threshold = 0.15
            if mfe < 0.01 and mfe > 0: # Likely decimal scale?
                 # If max MFE is 0.005, then it's clearly decimal.
                 pass
            
            # Let's just create buckets for now
            if mfe >= 0.15: # 0.15%
                target_hit_but_lost += 1
            else:
                never_reached_target += 1
                
        print(f"Trades in Kill Zone (09:30-09:45): {count}")
        print(f"Win Rate: {win_rate:.1f}%")
        print(f"Losers: {loss_count}")
        print(f"  - Died by 09:44: {len(died_by_944)} ({len(died_by_944)/loss_count*100:.1f}%)")
        print(f"  - Missed Payout (MFE >= 0.15%): {target_hit_but_lost} ('Greed')")
        print(f"  - Pure Judas    (MFE < 0.15%) : {never_reached_target} ('Trap')")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    for name, path in FILES.items():
        analyze_file(name, path)
    
    # Also comparison files
    analyze_file("V2 (Old)", V2_FILE)
    analyze_file("V7G (Benchmark)", V7G_FILE)
