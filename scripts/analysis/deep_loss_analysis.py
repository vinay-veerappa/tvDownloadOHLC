import pandas as pd
import numpy as np

def analyze_losses(csv_path, name):
    print(f"\n--- Analysis for {name} ---")
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"Error reading {csv_path}: {e}")
        return

    # Standardize columns
    if 'PnL_Pts' in df.columns: df['PnL'] = df['PnL_Pts']
    if 'Win' not in df.columns: df['Win'] = df['PnL'] > 0
    
    losses = df[df['PnL'] <= 0].copy()
    wins = df[df['PnL'] > 0].copy()
    
    total = len(df)
    n_losses = len(losses)
    wr = len(wins) / total
    
    print(f"Total Trades: {total}")
    print(f"Losses: {n_losses} ({n_losses/total*100:.2f}%)")
    print(f"Win Rate: {wr*100:.2f}%")
    
    # 1. Regime Analysis (if available)
    if 'Regime' in df.columns:
        print("\nLosses by Regime:")
        regime_stats = df.groupby('Regime')['Win'].mean().sort_values()
        print(regime_stats)
        
    # 2. Range Analysis (Volatility)
    range_col = 'RangeSize_Pts' if 'RangeSize_Pts' in df.columns else None
    if range_col:
        df['Range_Bin'] = pd.qcut(df[range_col], 4)
        print("\nWin Rate by Range Quartile:")
        print(df.groupby('Range_Bin')['Win'].mean())

    # 3. Time Analysis
    if 'ExitTime' in df.columns:
        print("\nWin Rate by Exit Time Plan:")
        print(df.groupby('ExitTime')['Win'].mean())

    # 4. MAE Distribution (if available - usually in raw backtest logs)
    # Since we might not have MAE in these CSVs, we check if they exist
    if 'MAE_Pts' in df.columns:
        print("\nAvg MAE of Losing Trades:", losses['MAE_Pts'].mean())

if __name__ == "__main__":
    analyze_losses('scripts/backtest/9_30_breakout/results/multi_year_backtest_2016_2025.csv', 'Base Strategy (V1)')
    analyze_losses('scripts/backtest/9_30_breakout/results/930_v2_all_trades.csv', 'Optimized Strategy (V2)')
