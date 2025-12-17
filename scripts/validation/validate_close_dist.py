
import pandas as pd
import matplotlib.pyplot as plt
import sys
import os
from datetime import timedelta
from collections import Counter
import numpy as np

# Add project root to path
sys.path.append(os.getcwd())

def validate_close_dist(ticker="RTY1"):
    from api.services.data_loader import DATA_DIR
    
    print(f"Loading 1m data for {ticker}...")
    file_path = DATA_DIR / f"{ticker}_1m.parquet"
    
    if not file_path.exists():
        print(f"Error: {file_path} not found")
        return

    df = pd.read_parquet(file_path)
    df = df.sort_index()
    
    if df.index.tz is None:
        df = df.tz_localize('UTC').tz_convert('US/Eastern')
    else:
        df = df.tz_convert('US/Eastern')
        
    df['date'] = df.index.date
    dates = sorted(set(df['date']))
    
    close_pcts = []
    
    print(f"Processing {len(dates)} days...")
    
    for date in dates:
        day_str = date.strftime('%Y-%m-%d')
        try:
            prev_day = date - timedelta(days=1)
            day_start = pd.Timestamp(f"{prev_day} 18:00", tz='US/Eastern')
            day_end = pd.Timestamp(f"{day_str} 16:00", tz='US/Eastern')
            
            day_data = df.loc[day_start:day_end]
            
            if not day_data.empty and len(day_data) > 10:
                day_open = day_data.iloc[0]['open']
                day_close = day_data.iloc[-1]['close'] # Close of the session
                
                if day_open > 0:
                    pct = ((day_close - day_open) / day_open) * 100
                    close_pcts.append(pct)
        except Exception:
            pass

    if not close_pcts:
        print("No data collected.")
        return

    # Calculate Stats
    bucket_size = 0.1
    bucketed = [np.floor(v / bucket_size) * bucket_size for v in close_pcts]
    counts = Counter([round(v, 1) for v in bucketed])
    
    sorted_vals = sorted(close_pcts)
    mid = len(sorted_vals) // 2
    median = sorted_vals[mid]
    mode = counts.most_common(1)[0][0] if counts else None
    
    print(f"\n=== {ticker} Daily Close Distribution Results ===")
    print(f"Count: {len(close_pcts)}")
    print(f"Median: {median:.4f}%")
    print(f"Mode (Bin): {mode:.1f}%")
    
    # Generate Plot
    plt.figure(figsize=(10, 6))
    plt.hist(close_pcts, bins=100, color='skyblue', edgecolor='black', alpha=0.7)
    plt.axvline(median, color='red', linestyle='dashed', linewidth=1, label=f'Median: {median:.2f}%')
    plt.axvline(mode, color='green', linestyle='dashed', linewidth=1, label=f'Mode: {mode:.1f}%')
    plt.title(f'{ticker} Daily Close % Distribution (from Open)')
    plt.xlabel('Change %')
    plt.ylabel('Frequency')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    chart_path = DATA_DIR / f"{ticker}_close_dist_chart.png"
    plt.savefig(chart_path)
    print(f"Chart saved to: {chart_path}")

if __name__ == "__main__":
    import sys
    
    tickers = ["RTY1", "ES1", "NQ1", "YM1", "CL1", "GC1", "SPX", "VIX", "QQQ"]
    if len(sys.argv) > 1 and sys.argv[1] != "ALL":
        tickers = [sys.argv[1]]
        
    for t in tickers:
        print(f"\n--- Processing {t} ---")
        validate_close_dist(t)
