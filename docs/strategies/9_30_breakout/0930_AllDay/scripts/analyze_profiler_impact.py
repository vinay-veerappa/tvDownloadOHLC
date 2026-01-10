
"""
Profiler Filter Impact Analysis
===============================
Analyzes 'local_backtest_results.csv' to determine:
1. How many Losers would be avoided? (Benefit)
2. How many Winners would be skipped? (Cost)
3. Net P&L Impact.

Hypothesis: Profiler Trap (Fighting a 'False' Session) is a bad trade.
Filter Logic:
- Long Entry AND Session Status == 'Long False' (Known Before Entry) -> SKIP
- Short Entry AND Session Status == 'Short False' (Known Before Entry) -> SKIP
"""

import pandas as pd
import json
import os
import sys

def analyze():
    print("Loading Trades and Profiler Data...")
    
    # 1. Load Trades
    try:
        trades_df = pd.read_csv("local_backtest_results.csv")
        # UTC -> ET
        trades_df['dt'] = pd.to_datetime(trades_df['Entry Time'], utc=True).dt.tz_convert('America/New_York')
        trades_df['date'] = trades_df['dt'].dt.date
    except:
        print("Error loading local_backtest_results.csv")
        return

    # 2. Load Profiler
    try:
        with open(r"c:\Users\vinay\tvDownloadOHLC\data\NQ1_profiler.json", "r") as f:
            prof_data = json.load(f)
        prof_df = pd.DataFrame(prof_data)
        prof_df['date_obj'] = pd.to_datetime(prof_df['date']).dt.date
        prof_df['status_dt'] = pd.to_datetime(prof_df['status_time'], utc=True).dt.tz_convert('America/New_York')
    except:
        print("Error loading NQ1_profiler.json")
        return

    # Group Profiler for lookup
    prof_by_date = prof_df.groupby('date_obj')

    # Counters
    total_pnl_original = trades_df['Gross P&L %'].sum()
    
    avoided_losers = 0
    missed_winners = 0 
    
    pnl_saved_from_losers = 0.0
    pnl_lost_from_winners = 0.0
    
    filtered_count = 0
    
    print(f"Analyzing {len(trades_df)} Trades...")
    
    for idx, trade in trades_df.iterrows():
        t_date = trade['date']
        t_time = trade['dt']
        direction = trade['Direction']
        pnl = trade['Gross P&L %']
        
        would_filter = False
        
        if t_date in prof_by_date.groups:
            day_profs = prof_by_date.get_group(t_date)
            
            for p_row in day_profs.itertuples():
                # Check Time Condition: Status MUST be known before entry
                if p_row.status_dt < t_time:
                    status = p_row.status
                    
                    if direction == "Long" and status == "Long False":
                        would_filter = True
                    elif direction == "Short" and status == "Short False":
                        would_filter = True
                        
        if would_filter:
            filtered_count += 1
            if pnl > 0:
                missed_winners += 1
                pnl_lost_from_winners += pnl
            else:
                avoided_losers += 1
                pnl_saved_from_losers += abs(pnl) # Saved loss is positive impact
                
    # Results
    net_pnl_impact = pnl_saved_from_losers - pnl_lost_from_winners # (Gain from avoiding loss) - (Loss from missing win)
    new_total_pnl = total_pnl_original + net_pnl_impact
    
    print("\n=== PROFILER TRAP FILTER IMPACT ===")
    print(f"Original Trades: {len(trades_df)}")
    print(f"Filtered Trades: {filtered_count} ({(filtered_count/len(trades_df))*100:.1f}%)")
    print("-" * 30)
    print(f"Losers Avoided : {avoided_losers} (Saved {pnl_saved_from_losers:.4f} P&L)")
    print(f"Winners Missed : {missed_winners} (Lost  {pnl_lost_from_winners:.4f} P&L)")
    print("-" * 30)
    print(f"Original Total P&L: {total_pnl_original:.4f}")
    print(f"Net P&L Impact    : {net_pnl_impact:+.4f}")
    print(f"New Total P&L     : {new_total_pnl:.4f}")
    print(f"Change            : {((new_total_pnl - total_pnl_original)/total_pnl_original)*100:+.2f}%")
    
    if missed_winners > 0:
        ratio = pnl_saved_from_losers / pnl_lost_from_winners
        print(f"Benefit/Cost Ratio: {ratio:.2f} (Target > 1.0)")
    else:
        print("Benefit/Cost Ratio: Infinite")

if __name__ == "__main__":
    analyze()
