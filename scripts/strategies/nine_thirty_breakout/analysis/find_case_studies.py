
"""
Case Study Finder
=================
Finds 3 specific "Instant Reversal" losses in 2025 for manual review.

Criteria:
- Year: 2025
- Time: 09:30 - 09:45 ET (Judas Zone)
- Outcome: Loss
- Characteristic: "Instant Death" (Low MFE, Fast Duration)
"""

import pandas as pd
import os

EXCEL_PATH = r"c:\Users\vinay\tvDownloadOHLC\docs\strategies\9_30_breakout\0930_AllDay\ORB_V3_CME_MINI_MNQ1!_2026-01-07_6f55a.xlsx"

def find_trades():
    print(f"Loading Excel...")
    try:
        df = pd.read_excel(EXCEL_PATH, sheet_name="List of trades")
        df.columns = df.columns.str.strip()
        
        trades = []
        for t_id, t_group in df.groupby('Trade #'):
            t_group = t_group.sort_values('Date and time')
            if len(t_group) < 2: continue
            
            entry_row = t_group.iloc[0]
            exit_row = t_group.iloc[-1]
            
            entry_time = entry_row['Date and time']
            profit = t_group['Net P&L USD'].sum()
            mfe = t_group['MFE %'].max() if 'MFE %' in t_group.columns else 0
            
            trades.append({
                'TradeNum': t_id,
                'Direction': "Long" if "Long" in entry_row['Type'] else "Short",
                'Entry Time': entry_time,
                'Entry Price': entry_row['Price USD'],
                'Exit Time': exit_row['Date and time'],
                'Exit Price': exit_row['Price USD'],
                'P&L': profit,
                'MFE %': mfe
            })
            
        t_df = pd.DataFrame(trades)
        
        # Filter for 2025
        t_df['entry_dt'] = pd.to_datetime(t_df['Entry Time']).dt.tz_localize(None).dt.tz_localize('America/New_York')
        t_df['year'] = t_df['entry_dt'].dt.year
        t_2025 = t_df[t_df['year'] == 2025].copy()
        
        # Filter for Losers
        losers = t_2025[t_2025['P&L'] < 0].copy()
        
        # Filter for Judas Zone (09:30 - 09:45)
        losers['time'] = losers['entry_dt'].dt.time
        from datetime import time
        judas_losers = losers[(losers['time'] >= time(9,30)) & (losers['time'] <= time(9,45))].copy()
        
        # Sort by MFE (Lowest MFE = Worst Trap) and Duration
        judas_losers = judas_losers.sort_values('MFE %', ascending=True)
        
        print(f"\nFound {len(judas_losers)} Judas Losers in 2025.")
        print("Top 3 Candidates for Review (Lowest MFE = Greatest Trap):")
        
        for i, row in judas_losers.head(3).iterrows():
            print("-" * 40)
            print(f"Date: {row['entry_dt'].date()}")
            print(f"Time: {row['entry_dt'].time()} ET")
            print(f"Direction: {row['Direction']}")
            print(f"Entry: {row['Entry Price']} -> Exit: {row['Exit Price']}")
            print(f"P&L: ${row['P&L']:.2f}")
            print(f"MFE: {row['MFE %']:.4f}% (Max profit before death)")
            print("-" * 40)

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    find_trades()
