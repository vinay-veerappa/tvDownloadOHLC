
import pandas as pd
import os

EXCEL_PATH = r"c:\Users\vinay\tvDownloadOHLC\docs\strategies\9_30_breakout\0930_AllDay\ORB_V3_CME_MINI_MNQ1!_2026-01-07_6f55a.xlsx"

def inspect():
    print("Inspecting May 28, 2025 Trade...")
    try:
        df = pd.read_excel(EXCEL_PATH, sheet_name="List of trades")
        df.columns = df.columns.str.strip()
        
        # Filter for 2025-05-28
        # 'Date and time' column
        df['dt'] = pd.to_datetime(df['Date and time'])
        
        target_date = "2025-05-28"
        day_trades = df[df['dt'].dt.date.astype(str) == target_date]
        
        if day_trades.empty:
            print("No trades found on 2025-05-28.")
            return

        print(f"Found {len(day_trades)} event rows on {target_date}:")
        print(day_trades[['Trade #', 'Type', 'Signal', 'Date and time', 'Price USD', 'Net P&L USD', 'MFE %']].to_string())
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect()
