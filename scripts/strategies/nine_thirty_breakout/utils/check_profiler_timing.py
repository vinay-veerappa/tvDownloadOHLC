
import pandas as pd
import json
import os
from datetime import datetime


def check_timing():
    # 1. Load Trades
    # try:
    trades_df = pd.read_csv("local_backtest_results.csv")
    # Force UTC=True to handle mixed offsets, then convert
    trades_df['dt'] = pd.to_datetime(trades_df['Entry Time'], utc=True).dt.tz_convert('America/New_York')
    trades_df['date'] = trades_df['dt'].dt.date
    print(f"Loaded {len(trades_df)} trades.")
    # except Exception as e:
    #     print(f"Could not load trades: {e}")
    #     return

    # 2. Load Profiler
    try:
        with open(r"c:\Users\vinay\tvDownloadOHLC\data\NQ1_profiler.json", "r") as f:
            prof_data = json.load(f)
        
        # Flatten simple list
        # data is list of dicts
        prof_df = pd.DataFrame(prof_data)
        # Parse Dates
        prof_df['date_obj'] = pd.to_datetime(prof_df['date']).dt.date
        
        # Parse status_time (format: "2008-01-02T09:13:00-05:00")
        prof_df['status_dt'] = pd.to_datetime(prof_df['status_time'], utc=True).dt.tz_convert('America/New_York')
        
        # Key: (date, session) -> status info
        # But wait, which session matters? 
        # Strategy trades all day (09:30 - 15:00).
        # NY1 ends 08:30?! Wait, JSON says start 07:30 end 08:30 (Pre-market logic?)
        # Let's check NY2. Start 11:30 End 12:30?
        # User said "NY AM" vs "NY PM".
        # Let's rely on date match for now and see timestamps.
        
        print(f"Loaded {len(prof_df)} profiler records.")
        # print sample
        # print(prof_df[['date', 'session', 'status', 'status_time']].head())
    except Exception as e:
        print(f"Error loading profiler: {e}")
        return

    # 3. Merge
    # We enter trades mostly 09:30 - 15:00.
    # Profiler NY1 might be pre-market or early. NY2 might be lunch.
    
    # Let's iterate trades and look up sessions for that date
    losers = trades_df[trades_df['Gross P&L %'] < 0].copy()
    print(f"Analyzing {len(losers)} Losers...")
    
    traps_identified = 0
    actionable_traps = 0
    
    for idx, trade in losers.iterrows():
        t_date = trade['date']
        t_time = trade['dt'] # Timestamp
        direction = trade['Direction'] # Long/Short
        
        # Find sessions for this date
        sessions = prof_df[prof_df['date_obj'] == t_date]
        
        if sessions.empty: continue
        
        for _, sess in sessions.iterrows():
            status = sess['status'] # e.g. "Short True", "Short False"
            s_time = sess['status_dt']
            
            if pd.isna(s_time): continue
            
            # Trap Definition:
            # We went Long, but Session said "Long False" (Reversal)
            # We went Short, but Session said "Short False" (Reversal)
            
            is_trap = False
            if direction == "Long" and status == "Long False": is_trap = True
            elif direction == "Short" and status == "Short False": is_trap = True
            
            if is_trap:
                traps_identified += 1
                # Is it actionable? (Did we know BEFORE entry?)
                if s_time < t_time:
                    actionable_traps += 1
                    # print(f"Actionable Trap! Trade: {t_time}, Status Confirmed: {s_time} ({status})")
    
    print("\n--- PROFILER TRAP RESULTS ---")
    print(f"Total Traps Found (Correlation): {traps_identified}")
    print(f"Actionable Traps (Known Before Entry): {actionable_traps}")
    print(f"Actionable %: {actionable_traps/traps_identified*100 if traps_identified else 0:.1f}%")

if __name__ == "__main__":
    check_timing()
