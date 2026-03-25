import pandas as pd
import numpy as np

def analyze_day_of_week(df):
    """Day of week effects on all key metrics."""
    
    print("=" * 60)
    print("DAY OF WEEK ANALYSIS")
    print("=" * 60)
    
    # Add DOW column
    df['dow'] = pd.to_datetime(df['date']).dt.day_name()
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    df['dow'] = pd.Categorical(df['dow'], categories=days, ordered=True)
    
    # 1. Manipulation Rate by DOW
    print("\n--- 1. Manipulation Breakdown by DOW ---")
    if 'manipulation' in df.columns:
        print(df.groupby('dow', observed=False)['manipulation'].value_counts(normalize=True).unstack().fillna(0)*100)
    
    # 2. Reversal Rate by DOW
    print("\n--- 2. Reversal Rate by DOW ---")
    if 'manipulation_reversed' in df.columns:
        print(df.groupby('dow', observed=False)['manipulation_reversed'].agg(['count', 'mean']).rename(columns={'mean': 'Rev Rate'}))
    
    # 3. Aligned Setup Reversal by DOW
    print("\n--- 3. Aligned Setup Reversal by DOW ---")
    if 'pattern' in df.columns and 'ny_position' in df.columns:
        aligned = df[
            ((df['pattern'] == 'PARTIAL_DOWN') & (df['ny_position'] == 'ABOVE_LONDON_MID')) |
            ((df['pattern'] == 'PARTIAL_UP') & (df['ny_position'] == 'BELOW_LONDON_MID'))
        ]
        if not aligned.empty:
            print("Aligned Setup Reversal Rate:")
            print(aligned.groupby('dow', observed=False)['manipulation_reversed'].mean() * 100)
    
    # 4. Hit-First by DOW (NY)
    print("\n--- 4. London High First Rate by DOW ---")
    if 'hit_london_high_first' in df.columns:
        print(df.groupby('dow', observed=False)['hit_london_high_first'].mean()*100)
    
    # 5. CBDR Sigma Reach by DOW
    print("\n--- 5. CBDR Sigma First Rate by DOW ---")
    if 'cbdr_upside_sigmas' in df.columns:
        print("Upside Sigma (Mean):")
        print(df.groupby('dow', observed=False)['cbdr_upside_sigmas'].mean())
        print("Downside Sigma (Mean):")
        print(df.groupby('dow', observed=False)['cbdr_downside_sigmas'].mean())
