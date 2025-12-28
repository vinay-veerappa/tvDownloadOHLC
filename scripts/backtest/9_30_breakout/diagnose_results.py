
import pandas as pd
import os

def diagnose():
    csv_path = r"c:\Users\vinay\tvDownloadOHLC\scripts\backtest\9_30_breakout\results\930_backtest_all_trades.csv"
    if not os.path.exists(csv_path):
        print("CSV not found")
        return
        
    df = pd.read_csv(csv_path)
    print(f"Total Rows: {len(df)}")
    print("\nColumns:")
    print(df.columns.tolist())
    
    print("\nValue Overviews:")
    print(f"Avg Range Pct: {df['Range_Pct'].mean():.4f}%")
    
    # Calculate Range Pts if we have High/Low
    if 'Range_High' in df.columns and 'Range_Low' in df.columns:
        df['Range_Pts'] = df['Range_High'] - df['Range_Low']
        print(f"Avg Range Pts: {df['Range_Pts'].mean():.2f}")
    
    print("\nSample Trades (First 5):")
    cols = ['Date', 'Range_High', 'Range_Low', 'Variant', 'Direction', 'Result', 'PnL_Pct', 'Exit_Reason']
    print(df[cols].head(5).to_string())

if __name__ == "__main__":
    diagnose()
