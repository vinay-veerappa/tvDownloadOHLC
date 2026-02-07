import pandas as pd
import numpy as np

def analyze_hit_first_stats(df_days: pd.DataFrame):
    if df_days.empty:
        return
        
    print("\n--- Hit-First Statistics ---")
    
    # Required columns
    cols = ['pattern', 'ny_position', 'hit_london_high_first']
    if not all(c in df_days.columns for c in cols):
        print("Missing columns for hit-first analysis")
        return

    # Create a cleaner status column
    def get_status(x):
        if pd.isna(x): return "Neither"
        return "High First" if x else "Low First"
        
    df_days['first_touch_stat'] = df_days['hit_london_high_first'].apply(get_status)
    
    # Group by Pattern + NY Position
    grouped = df_days.groupby(['pattern', 'ny_position'])['first_touch_stat'].value_counts(normalize=True).unstack(fill_value=0) * 100
    grouped['Count'] = df_days.groupby(['pattern', 'ny_position'])['first_touch_stat'].count()
    
    print("Probability of NY hitting London High/Low First:")
    pd.set_option('display.max_rows', None)
    print(grouped.round(1))
    pd.reset_option('display.max_rows')
    
    return grouped
