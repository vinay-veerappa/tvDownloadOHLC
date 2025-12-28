
import pandas as pd
import numpy as np
import os

def analyze():
    csv_path = r"c:\Users\vinay\tvDownloadOHLC\scripts\backtest\9_30_breakout\results\930_backtest_all_trades.csv"
    vvix_path = r"c:\Users\vinay\tvDownloadOHLC\data\VVIX_1d.parquet"
    
    if not os.path.exists(csv_path) or not os.path.exists(vvix_path):
        print("Required data missing")
        return
        
    trades = pd.read_csv(csv_path)
    trades['Date'] = pd.to_datetime(trades['Date']).dt.date
    
    vvix = pd.read_parquet(vvix_path)
    vvix.index = pd.to_datetime(vvix.index).date
    vvix = vvix.rename(columns={'close': 'VVIX_Close', 'open': 'VVIX_Open'})
    
    # Merge trades with VVIX
    df = pd.merge(trades, vvix[['VVIX_Open', 'VVIX_Close']], left_on='Date', right_index=True, how='inner')
    
    # Filter to Base trades for cleaner statistical sample
    base_df = df[df['Variant'] == 'Base_1Att'].copy()
    
    print(f"Total Trades with VVIX Data: {len(base_df)}")
    
    if len(base_df) == 0:
        print("No trades merged. Check date overlap.")
        return

    # --- 1. VVIX Bucket Analysis ---
    bins = [0, 85, 100, 115, 999]
    labels = ['Low (<85)', 'Normal (85-100)', 'Elevated (100-115)', 'High (>115)']
    base_df['VVIX_Bucket'] = pd.cut(base_df['VVIX_Open'], bins=bins, labels=labels)
    
    vvix_stats = base_df.groupby('VVIX_Bucket', observed=False).agg({
        'Win': 'mean',
        'PnL_Pct': ['mean', 'sum'],
        'Date': 'count'
    }).round(4)
    
    print("\nWin Rate and PnL by VVIX Level (At Open):")
    print(vvix_stats.to_string())
    
    # --- 2. VVIX Change Analysis ---
    # VVIX Change (1-day)
    vvix_df = pd.read_parquet(vvix_path)
    vvix_df.index = pd.to_datetime(vvix_df.index).date
    vvix_df['VVIX_Prev_Close'] = vvix_df['close'].shift(1)
    vvix_df['VVIX_Gap'] = vvix_df['open'] - vvix_df['VVIX_Prev_Close']
    
    df_gap = pd.merge(base_df, vvix_df[['VVIX_Gap']], left_on='Date', right_index=True, how='inner')
    
    df_gap['VVIX_Trend'] = np.where(df_gap['VVIX_Gap'] > 0, 'Spiking', 'Stable/Falling')
    trend_stats = df_gap.groupby('VVIX_Trend', observed=False).agg({
        'Win': 'mean',
        'PnL_Pct': 'mean',
        'Date': 'count'
    }).round(4)
    
    print("\nImpact of VVIX Overnight Spike:")
    print(trend_stats.to_string())

if __name__ == "__main__":
    analyze()
