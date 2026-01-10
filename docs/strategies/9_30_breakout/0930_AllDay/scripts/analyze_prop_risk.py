
"""
Prop Firm Risk Analyzer
=======================
Analyzes Strategy Performance against typical Prop Firm Rules.
Input: List of Excel Export files.
Metrics:
- Max Daily Loss (Hard Limit check)
- Max Trailing Drawdown
- Profit Factor
- Win Rate (Daily)
- Consistency (Top Day % of Total Profit)

Assumptions:
- Fixed Contract Size (1 Contract) inferred from P&L/Price if not explicit.
"""

import pandas as pd
import numpy as np
import os
import glob

# The 5 new Doji files
FILES = glob.glob(r"ORB_V3_Doji*.xlsx")

def analyze_file(path):
    print(f"\nAnalyzing: {os.path.basename(path)}")
    try:
        # Load Trades
        df = pd.read_excel(path, sheet_name="List of trades")
        df.columns = df.columns.str.strip()
        
        # Load Properties (to check config if needed, but not strictly required for P&L)
        # Calculate Daily P&L
        df['dt'] = pd.to_datetime(df['Date and time'])
        df['date'] = df['dt'].dt.date
        
        # Group by Date to get Daily P&L
        # Note: 'Net P&L USD' is usually on the Exit row.
        # Check if we need to sum by Trade or just sum the column.
        # TradingView export usually puts P&L on the *closing* trade row.
        # Summing the column per day is safe.
        daily_pnl = df.groupby('date')['Net P&L USD'].sum()
        
        # 1. Total Net Profit
        total_profit = daily_pnl.sum()
        
        # 2. Max Daily Drawdown
        max_daily_loss = daily_pnl.min()
        worst_day = daily_pnl.idxmin()
        
        # 3. Win Rate (Daily)
        win_days = (daily_pnl > 0).sum()
        loss_days = (daily_pnl < 0).sum()
        total_days = len(daily_pnl)
        win_rate = (win_days / total_days * 100) if total_days > 0 else 0
        
        # 4. Profit Factor
        gross_profit = daily_pnl[daily_pnl > 0].sum()
        gross_loss = abs(daily_pnl[daily_pnl < 0].sum())
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 999.0
        
        # 5. Trailing Drawdown (Equity Curve)
        daily_pnl_sorted = daily_pnl.sort_index()
        cumulative = daily_pnl_sorted.cumsum()
        running_max = cumulative.cummax()
        drawdown = cumulative - running_max
        max_trailing_dd = drawdown.min()
        
        # 6. Consistency Rule (Top Day Profit / Total Profit)
        # Prop firms often cap this at 30% or 50%
        best_day_profit = daily_pnl.max()
        consistency_score = (best_day_profit / total_profit * 100) if total_profit > 0 else 0
        
        # 7. "Blowout Limit" Checks
        # Assuming $50k Account -> $2000 Daily Loss Limit
        # Assuming MNQ? Or NQ? 
        # User said "1 contract fixed".
        # Let's verify scaling.
        # We report the raw $ value.
        days_breaching_500 = (daily_pnl < -500).sum()
        days_breaching_1000 = (daily_pnl < -1000).sum()
        
        print(f"  Total Profit:   ${total_profit:,.2f}")
        print(f"  Profit Factor:  {profit_factor:.2f}")
        print(f"  Win Rate (Day): {win_rate:.1f}% ({win_days}W / {loss_days}L)")
        print(f"  Max Daily Loss: ${max_daily_loss:,.2f} on {worst_day}")
        print(f"  Max Trailing DD:${max_trailing_dd:,.2f}")
        print(f"  Consistency:    {consistency_score:.1f}% (Top Day vs Total)")
        print(f"  Risk Checks:")
        print(f"    Days < -$500:  {days_breaching_500}")
        print(f"    Days < -$1000: {days_breaching_1000}")
        
        return {
            "File": os.path.basename(path),
            "Total": total_profit,
            "PF": profit_factor,
            "MaxDD": max_daily_loss,
            "Days<-500": days_breaching_500
        }

    except Exception as e:
        print(f"Error: {e}")
        return None

def main():
    print("Finding Files...")
    if not FILES:
        print("No files found!")
        return

    results = []
    for f in FILES:
        res = analyze_file(f)
        if res: results.append(res)
        
    # Summary Table
    print("\n=== SUMMARY COMPARISON ===")
    r_df = pd.DataFrame(results)
    if not r_df.empty:
        print(r_df.to_string(index=False))

if __name__ == "__main__":
    main()
