import pandas as pd

def analyze_pattern_distribution(df_days: pd.DataFrame):
    if df_days.empty:
        return None
        
    print("--- Pattern Distribution ---")
    counts = df_days['pattern'].value_counts()
    pcts = df_days['pattern'].value_counts(normalize=True) * 100
    res = pd.DataFrame({'Count': counts, 'Percent': pcts})
    print(res)
    return res
