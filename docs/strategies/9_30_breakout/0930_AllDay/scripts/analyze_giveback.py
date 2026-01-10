
import pandas as pd
import numpy as np
import os

# Configuration
TRADE_FILE = r'c:\Users\vinay\tvDownloadOHLC\docs\strategies\9_30_breakout\0930_AllDay\ORB_All-Day_V2_CME_MINI_MNQ1!_2026-01-07_06a7f.xlsx' # Run 6 V2
POINT_VALUE = 2 # MNQ

def load_trades(filepath):
    print(f"Loading trades from {filepath}...")
    xl = pd.ExcelFile(filepath)
    df = pd.read_excel(xl, sheet_name='List of trades')
    
    if 'Trade #' in df.columns:
        trades = []
        grouped = df.groupby('Trade #')
        for trade_id, group in grouped:
            # We want to compare Max Run-up (MFE) vs Realized P&L
            # TV Export 'Run-up' column usually exists in 'List of trades' or 'Summary'?
            # 'List of trades' has 'Run-up' (Absolute value? in USD? or Points/Ticks?)
            # Usually 'Run-up' in list of trades is in Money (Currency).
            # Let's verify columns.
            
            # We assume 'Run-up' exists and is per-trade max potential profit.
            # 'Net P&L USD' is realized.
            
            # Sum for the trade
            realized_pnl = group['Net P&L USD'].sum()
            
            # Run-up is usually per row? Or same for all rows in trade?
            # It's usually non-zero on the Entry row or Exit row?
            # We'll take the max 'Run-up' value found in the group.
            # Note: Run-up in TV export might be "Run-up USD" or just "Run-up".
            # We need to check column names.
            
            # Conservative: Calculate based on Entry/Exit vs High/Low if needed?
            # But we don't have OHLC loaded here (fast check).
            # Let's rely on TV 'Run-up' if available.
            
            # Column is 'MFE USD'
            run_up_col = 'MFE USD'
            if run_up_col not in group.columns:
                 # Try finding logical equivalent
                 cols = [c for c in group.columns if 'mfe' in c.lower() and 'usd' in c.lower()]
                 if cols:
                     run_up_col = cols[0]
                 else:
                     continue
            
            run_up = group[run_up_col].max() # Max run-up recorded
            
            # If Run-up is string (e.g. "100 USD"), parse it.
            if isinstance(run_up, str):
                 # extract numbers
                 import re
                 match = re.search(r'[\d\.]+', run_up)
                 if match:
                     run_up = float(match.group())
            
            # Giveback = Run-up - Realized
            giveback = run_up - realized_pnl
            
            trades.append({
                'Trade #': trade_id,
                'Realized P&L': realized_pnl,
                'Run-up': run_up,
                'Giveback': giveback,
                'Giveback %': (giveback / run_up) * 100 if run_up > 0 else 0
            })
            
        return pd.DataFrame(trades)
    else:
        print("Error: 'Trade #' column not found.")
        return pd.DataFrame()

if __name__ == "__main__":
    df = load_trades(TRADE_FILE)
    if len(df) > 0:
        print(f"Analyzed {len(df)} V2 Trades.")
        print(f"Total Run-up Potential: ${df['Run-up'].sum():,.2f}")
        print(f"Total Realized: ${df['Realized P&L'].sum():,.2f}")
        print(f"Total Giveback: ${df['Giveback'].sum():,.2f}")
        print(f"Avg Run-up: ${df['Run-up'].mean():.2f}")
        print(f"Avg Realized: ${df['Realized P&L'].mean():.2f}")
        print(f"Avg Giveback: ${df['Giveback'].mean():.2f} ({df['Giveback %'].mean():.1f}%)")
        
        print("\nTop 10 Givebacks:")
        print(df.sort_values('Giveback', ascending=False).head(10).to_string())
        
        # Determine "Optimal Trail"?
        # Hard without tick data simulation.
        # But stats show the magnitude of the problem.
    else:
        print("No trades found or Run-up column missing.")
