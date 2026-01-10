
"""
Daily P&L Checker
=================
Calculates the Net P&L for specific dates to see if the day ended positive despite losses.

Target: 2025-05-28
"""

import pandas as pd
import os

EXCEL_PATH = r"c:\Users\vinay\tvDownloadOHLC\docs\strategies\9_30_breakout\0930_AllDay\ORB_V3_CME_MINI_MNQ1!_2026-01-07_6f55a.xlsx"

DATES = ["2025-05-28"]

def check_daily():
    print("Checking Daily P&L...")
    try:
        df = pd.read_excel(EXCEL_PATH, sheet_name="List of trades")
        df.columns = df.columns.str.strip()
        df['dt'] = pd.to_datetime(df['Date and time'])
        df['date_str'] = df['dt'].dt.date.astype(str)
        
        for d in DATES:
            day_trades = df[df['date_str'] == d]
            if day_trades.empty:
                print(f"{d}: No trades found.")
                continue
                
            # Sum 'Net P&L USD' for all rows
            # Note: Excel list might list P&L on both Entry and Exit? 
            # Usually only on Exit rows or distinct trade rows.
            # Let's inspect quickly.
            # Previous unique trade Logic: Group by Trade #, take sum.
            
            daily_pnl = 0
            count = 0
            for t_id, t_group in day_trades.groupby('Trade #'):
                t_pnl = t_group['Net P&L USD'].sum()
                daily_pnl += t_pnl
                count += 1
            
            print(f"Date: {d}")
            print(f"Total Trades: {count}")
            print(f"Net P&L: ${daily_pnl:.2f}")
            print("-" * 20)

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_daily()
