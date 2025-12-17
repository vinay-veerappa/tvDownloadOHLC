
import pandas as pd
import numpy as np
import os

def analyze_advanced_filters(ticker="NQ1", days=200):
    print(f"Analyzing Advanced Filters for {ticker} (Last {days} Days)...")
    
    csv_path = "reports/930_backtest_all_trades.csv"
    if not os.path.exists(csv_path):
        print("CSV not found. High-level analysis required.")
        return
        
    df = pd.read_csv(csv_path)
    df['Date'] = pd.to_datetime(df['Date'])
    df['Day'] = df['Date'].dt.day_name()
    
    # 1. DAY OF WEEK ANALYSIS
    print("\n--- 1. PERFORMANCE BY DAY OF WEEK ---")
    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    day_stats = df.groupby('Day', observed=True).agg({
        'Result': lambda x: (x == 'WIN').mean() * 100,
        'PnL_Pct': 'sum',
        'Variant': 'count'
    }).reindex(day_order)
    day_stats = day_stats.rename(columns={'Result': 'Win%', 'Variant': 'Trades'})
    print(day_stats.to_string())

    # 2. CANDLE QUALITY (Body vs Range)
    # This requires raw data. We need to reload or have range info.
    # The CSV has 'Range_Pct'. Let's assume we can also get Body size if we re-analyze or if it was in CSV.
    # Wait, the CSV I generated for comparison might not have Body Size. 
    # Let's create a more surgical script that loads Parquet and analyzes metrics directly.

    # 3. RANGE SUCCESSIVE EXPANSION
    print("\n--- 2. RANGE SIZE VS SUCCESS ---")
    # Does a large 9:30 candle (High Vol) lead to more wins?
    df['Range_Bucket'] = pd.qcut(df['Range_Pct'], 4, labels=['Very Tight', 'Normal', 'Wide', 'Extremes'])
    range_stats = df.groupby('Range_Bucket', observed=True).agg({
        'Result': lambda x: (x == 'WIN').mean() * 100,
        'PnL_Pct': 'mean',
        'Variant': 'count'
    })
    print(range_stats.to_string())

    # 4. VOLATILITY SCALING (R/R)
    # Measure 'Profit_Capture_Ratio' = MFE_Pct / Range_Pct
    df['Capture_Ratio'] = df['MFE_Pct'] / df['Range_Pct']
    print(f"\nMedian Capture Ratio (MFE / 9:30 Range): {df['Capture_Ratio'].median():.2f}")
    # If ratio is > 1.0, the move expanded beyond the opening range.

if __name__ == "__main__":
    analyze_advanced_filters()
