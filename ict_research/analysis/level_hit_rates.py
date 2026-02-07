import pandas as pd

def analyze_level_hit_rates(df_days: pd.DataFrame):
    if df_days.empty:
        return
        
    print("\n--- Level Hit Rates ---")
    
    cols = [c for c in df_days.columns if c.startswith('hit_') and 'first' not in c]
    
    # Global hit rates
    print("Global Hit Rates:")
    print(df_days[cols].mean() * 100)
    
    # Conditional on Pattern
    print("\nHit Rates by Pattern:")
    grouped = df_days.groupby('pattern')[cols].mean() * 100
    print(grouped.round(1))
    
    return grouped
