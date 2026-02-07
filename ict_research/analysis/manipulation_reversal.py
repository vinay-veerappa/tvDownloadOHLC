import pandas as pd

def analyze_reversal_structure(df_days: pd.DataFrame):
    if df_days.empty:
        return None
        
    print("\n--- Manipulation Reversal Rates ---")
    # By manipulation type
    if 'manipulation' not in df_days.columns or 'manipulation_reversed' not in df_days.columns:
        print("Required columns missing for reversal analysis")
        return None
        
    grouped = df_days.groupby('manipulation')['manipulation_reversed'].agg(['count', 'sum', 'mean'])
    grouped = grouped.rename(columns={'count': 'Total', 'sum': 'Reversed', 'mean': 'WinRate'})
    grouped['WinRate'] = grouped['WinRate'] * 100
    print(grouped)
    return grouped
