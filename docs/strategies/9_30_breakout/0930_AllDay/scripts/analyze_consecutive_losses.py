"""
Analyze Excel Backtest Data - Find Consecutive MAE Stop-outs
=============================================================
Looking for days with 2-3+ consecutive losses to identify chop patterns
"""

import pandas as pd
from pathlib import Path
import sys

ROOT = Path(r"c:\Users\vinay\tvDownloadOHLC\docs\strategies\9_30_breakout\0930_AllDay")

def analyze_consecutive_losses(excel_path):
    """Find days with multiple consecutive MAE stop-outs"""
    print(f"\nAnalyzing: {excel_path.name}")
    
    # Load Excel
    try:
        df = pd.read_excel(excel_path)
    except Exception as e:
        print(f"Error loading: {e}")
        return None
    
    print(f"Columns: {df.columns.tolist()[:15]}...")
    print(f"Total rows: {len(df)}")
    
    # Find relevant columns
    trade_cols = [c for c in df.columns if 'trade' in c.lower() or 'pnl' in c.lower() or 'profit' in c.lower()]
    date_cols = [c for c in df.columns if 'date' in c.lower() or 'time' in c.lower()]
    
    print(f"Trade-related columns: {trade_cols}")
    print(f"Date-related columns: {date_cols}")
    
    # Sample first rows
    print("\nFirst 5 rows (relevant columns):")
    show_cols = date_cols[:2] + trade_cols[:5]
    if show_cols:
        print(df[show_cols].head().to_string())
    else:
        print(df.head().to_string())
    
    return df


def find_multi_loss_days(df):
    """Group by day and find days with 2+ consecutive losses"""
    # Look for Date column
    date_col = None
    for c in df.columns:
        if 'date' in c.lower():
            date_col = c
            break
    
    if date_col is None:
        print("No date column found")
        return
    
    # Look for PnL/profit column
    pnl_col = None
    for c in df.columns:
        if 'profit' in c.lower() or 'pnl' in c.lower() or 'net' in c.lower():
            pnl_col = c
            break
    
    if pnl_col is None:
        print("No PnL column found")
        return
    
    print(f"\nUsing date column: {date_col}")
    print(f"Using PnL column: {pnl_col}")
    
    # Parse dates
    df[date_col] = pd.to_datetime(df[date_col])
    df['date_only'] = df[date_col].dt.date
    
    # Group by day
    daily_groups = df.groupby('date_only')
    
    multi_loss_days = []
    
    for date, group in daily_groups:
        trades = group[pnl_col].tolist()
        
        # Count consecutive losses
        consecutive = 0
        max_consecutive = 0
        
        for pnl in trades:
            if pd.notna(pnl) and pnl < 0:
                consecutive += 1
                max_consecutive = max(max_consecutive, consecutive)
            else:
                consecutive = 0
        
        if max_consecutive >= 2:
            total_trades = len(trades)
            losses = sum(1 for p in trades if pd.notna(p) and p < 0)
            multi_loss_days.append({
                'date': date,
                'total_trades': total_trades,
                'losses': losses,
                'max_consecutive': max_consecutive,
                'trades': trades
            })
    
    print(f"\n{'='*60}")
    print(f"Days with 2+ Consecutive Losses: {len(multi_loss_days)}")
    print(f"{'='*60}")
    
    for day in sorted(multi_loss_days, key=lambda x: x['max_consecutive'], reverse=True)[:15]:
        print(f"\n{day['date']} | Trades: {day['total_trades']} | Losses: {day['losses']} | Max Consec: {day['max_consecutive']}")
        # Show trade sequence
        trade_seq = ['L' if p < 0 else 'W' if p > 0 else '-' for p in day['trades'] if pd.notna(p)]
        print(f"  Sequence: {' '.join(trade_seq)}")
    
    return multi_loss_days


if __name__ == "__main__":
    # Find most recent Excel files
    excel_files = list(ROOT.glob("*.xlsx"))
    print(f"Found {len(excel_files)} Excel files")
    
    # Use the most recent MNQ file
    mnq_files = [f for f in excel_files if 'MNQ' in f.name]
    if mnq_files:
        latest = sorted(mnq_files)[-1]
        df = analyze_consecutive_losses(latest)
        if df is not None:
            find_multi_loss_days(df)
