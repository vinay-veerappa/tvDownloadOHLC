
import pandas as pd
import numpy as np
from pathlib import Path

DATA_PATH = Path("data/derived/NQ1_herman_stats.parquet")

def load_data():
    if not DATA_PATH.exists(): return None
    return pd.read_parquet(DATA_PATH)

def calc_thresholds(df):
    # Calculate Range %
    # Use Asia Open as denominator
    df['asia_range_pct'] = (df['asia_range'] / df['asia_open']) * 100
    
    # Herman's Split: 
    # Small Asia (n=4488) vs Big Asia (n=523) -> Total 5011
    # Big Asia is Top 10.4% of days.
    # Small Asia is Bottom 89.6% of days.
    
    threshold_pct = df['asia_range_pct'].quantile(0.896)
    
    print("="*60)
    print("TIME-AGNOSTIC THRESHOLD CALCULATION")
    print("="*60)
    print(f"Total Days: {len(df)}")
    print(f"Herman's 'Big Asia' Frequency: ~10.4% (based on previous run)")
    print(f"Equivalent Percentile: 89.6th percentile")
    print(f"Calculated Asia Range Threshold: {threshold_pct:.4f}%")
    
    # Validation: How does 70.9 pts compare?
    # Let's see what 70.9 pts was as a % in 2024 vs 2010.
    
    recent = df[df['date'] > pd.to_datetime("2023-01-01").date()]
    old = df[df['date'] < pd.to_datetime("2015-01-01").date()]
    
    avg_price_recent = recent['asia_open'].mean()
    avg_price_old = old['asia_open'].mean()
    
    print(f"\nWhy Points Fail:")
    print(f"  2024 Avg NQ Price: {avg_price_recent:.0f} -> 70.9 pts is {70.9/avg_price_recent*100:.4f}%")
    print(f"  2010-2015 Avg NQ Price: {avg_price_old:.0f} -> 70.9 pts is {70.9/avg_price_old*100:.4f}%")
    print(f"  (This confirms 70.9 pts is likely a 'recent era' metric and totally wrong for history)")
    
    print(f"\nRECOMMENDATION:")
    print(f"  Use **{threshold_pct:.2f}%** as the 'Big/Small' Asia Threshold.")

def main():
    df = load_data()
    if df is not None:
        calc_thresholds(df)

if __name__ == "__main__":
    main()
