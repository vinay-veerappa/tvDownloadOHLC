
import pandas as pd
import numpy as np
import os

def analyze():
    csv_path = r"c:\Users\vinay\tvDownloadOHLC\scripts\backtest\9_30_breakout\results\930_backtest_all_trades.csv"
    if not os.path.exists(csv_path):
        print("CSV not found")
        return
        
    df = pd.read_csv(csv_path)
    
    # Filter to only Base trades to find natural excursion potential
    base_df = df[df['Variant'] == 'Base_1Att'].copy()
    
    print(f"Analyzing {len(base_df)} Base Trades for MFE Sensitivity...")
    
    # --- 1. MFE Target Sensitivity ---
    targets = np.arange(0.1, 1.05, 0.05) # 0.1% to 1.0%
    results = []
    
    for tp in targets:
        # For each trade, if MFE_Pct >= tp, it's a WIN at that TP level.
        # Otherwise, if it was already a winner at 10:00 AM, keep its PnL? 
        # No, let's be strict: if it doesn't hit TP, it exits at 10:00 AM or SL.
        
        tp_pnl = []
        for idx, row in base_df.iterrows():
            if row['MFE_Pct'] >= tp:
                tp_pnl.append(tp)
            else:
                tp_pnl.append(row['PnL_Pct']) # Exit at 10:00 AM or SL
        
        sum_pnl = sum(tp_pnl)
        win_rate = len([x for x in tp_pnl if x > 0]) / len(tp_pnl)
        results.append({'Target_Pct': tp, 'Total_PnL': sum_pnl, 'WinRate': win_rate})
        
    sens_df = pd.DataFrame(results)
    print("\nMFE Sensitivity Results:")
    print(sens_df.to_string(index=False))
    
    # --- 2. MAE (Heat) Analysis ---
    winners = base_df[base_df['PnL_Pct'] > 0]
    losers = base_df[base_df['PnL_Pct'] <= 0]
    
    print(f"\nHeat Analysis (MAE):")
    print(f"Median MAE (Winners): {winners['MAE_Pct'].median():.4f}%")
    print(f"Median MAE (Losers): {losers['MAE_Pct'].median():.4f}%")
    print(f"90th Percentile MAE (Winners): {winners['MAE_Pct'].quantile(0.9):.4f}%")
    
    # --- 3. Profit Leakage ---
    # Trades that hit >0.5% MFE but ended in a loss
    leakage = base_df[(base_df['MFE_Pct'] > 0.5) & (base_df['PnL_Pct'] <= 0)]
    print(f"\nProfit Leakage (>0.5% MFE but Loss): {len(leakage)} trades")
    if len(leakage) > 0:
        print(f"Avg Leakage MFE: {leakage['MFE_Pct'].mean():.4f}%")

if __name__ == "__main__":
    analyze()
