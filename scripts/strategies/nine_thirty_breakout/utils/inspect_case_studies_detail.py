
"""
Detailed Case Study Inspector
=============================
Re-pulls the 3 Case Studies with strict Entry/Exit identification.
Resolves "Same Minute" sorting issues using 'Type' column.

Dates:
1. 2025-05-28 (May 28)
2. 2025-06-25 (Jun 25)
3. 2025-09-12 (Sep 12)
"""

import pandas as pd
import os

EXCEL_PATH = r"c:\Users\vinay\tvDownloadOHLC\docs\strategies\9_30_breakout\0930_AllDay\ORB_V3_CME_MINI_MNQ1!_2026-01-07_6f55a.xlsx"

DATES = ["2025-05-28", "2025-06-25", "2025-09-12"]

def inspect():
    print("Loading Excel for Detailed Inspection...")
    try:
        df = pd.read_excel(EXCEL_PATH, sheet_name="List of trades")
        df.columns = df.columns.str.strip()
        df['dt'] = pd.to_datetime(df['Date and time'])
        df['date_str'] = df['dt'].dt.date.astype(str)
        
        for d in DATES:
            print(f"\n=== {d} TRADES ===")
            day_trades = df[df['date_str'] == d].copy()
            
            if day_trades.empty:
                print("No trades found.")
                continue
                
            # Group by Trade #
            for t_id, t_group in day_trades.groupby('Trade #'):
                # Correct Logic: Find Entry and Exit by String
                entry_rows = t_group[t_group['Type'].str.contains("Entry", case=False)]
                exit_rows = t_group[t_group['Type'].str.contains("Exit", case=False)]
                
                if entry_rows.empty: continue
                
                # Usually 1 entry row
                entry_row = entry_rows.iloc[0]
                
                # Exits can be multiple (TP1, TP2, SL)
                # Let's list all events
                
                entry_time = entry_row['Date and time']
                entry_px = entry_row['Price USD']
                direction = "Long" if "Long" in entry_row['Type'] else "Short"
                signal = entry_row['Signal']
                
                print(f"Trade #{t_id} ({direction} {signal})")
                print(f"  Entry: {entry_time} @ {entry_px}")
                
                # Exits
                total_pnl = 0
                for _, x_row in exit_rows.iterrows():
                    x_time = x_row['Date and time']
                    x_px = x_row['Price USD']
                    x_type = x_row['Type'] # Exit long/Exit short
                    x_signal = x_row['Signal'] # TP1, SL, MAE Exit
                    pnl = x_row['Net P&L USD']
                    total_pnl += pnl
                    print(f"  Exit : {x_time} @ {x_px} ({x_signal}) P&L: {pnl}")
                    
                print(f"  Net P&L: {total_pnl}")
                print("-" * 20)

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect()
