import json
import pandas as pd
import numpy as np
import os

DATA_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'derived', 'rth_gaps.json')

def analyze_gaps():
    if not os.path.exists(DATA_FILE):
        print("Data file not found.")
        return

    with open(DATA_FILE, 'r') as f:
        data = json.load(f)

    summary = []

    for ticker, gaps in data.items():
        if not gaps:
            continue
            
        df = pd.DataFrame(gaps)
        
        # Absolute Gap Size
        df['abs_gap'] = df['gap_size'].abs()
        
        # Stats
        count = len(df)
        mean_gap = df['abs_gap'].mean()
        median_gap = df['abs_gap'].median()
        max_gap = df['abs_gap'].max()
        std_gap = df['abs_gap'].std()
        
        # Gap Up vs Down
        up_gaps = df[df['gap_direction'] == 'UP']
        down_gaps = df[df['gap_direction'] == 'DOWN']
        
        up_pct = len(up_gaps) / count * 100
        
        # Percentiles
        p90 = df['abs_gap'].quantile(0.90)
        p95 = df['abs_gap'].quantile(0.95)
        
        summary.append({
            "Ticker": ticker,
            "Count": count,
            "Avg Gap (Abs)": mean_gap,
            "Median Gap": median_gap,
            "Max Gap": max_gap,
            "Gap Up %": up_pct,
            "90th %ile": p90
        })

    # Display
    summ_df = pd.DataFrame(summary)
    # Format
    summ_df["Avg Gap (Abs)"] = summ_df["Avg Gap (Abs)"].map('{:.2f}'.format)
    summ_df["Median Gap"] = summ_df["Median Gap"].map('{:.2f}'.format)
    summ_df["Max Gap"] = summ_df["Max Gap"].map('{:.2f}'.format)
    summ_df["Gap Up %"] = summ_df["Gap Up %"].map('{:.1f}%'.format)
    summ_df["90th %ile"] = summ_df["90th %ile"].map('{:.2f}'.format)
    
    print(summ_df.to_string(index=False))

if __name__ == "__main__":
    analyze_gaps()
