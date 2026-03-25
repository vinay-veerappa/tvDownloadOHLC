import pandas as pd
import numpy as np

def classify_london_sweep_type(row):
    """Classify London sweep type based on pattern and high/low first."""
    # Pattern logic derived from what happened relative to Asia
    # If london_high > asia_high -> swept high
    # If london_low < asia_low -> swept low
    # But we have `london_sweep_up_pct` and `london_sweep_dn_pct` if we want magnitude.
    # We can also use 'pattern' if it refers to London vs Asia (but pattern usually refers to Overnight vs Prev Day or PM vs AM).
    # Wait, 'pattern' in df is classify_overnight_pattern (Overnight vs Prev Day).
    # We need London vs Asia pattern.
    # Let's verify if we have London vs Asia explicit columns.
    # 'london_high' and 'asia_high' exist.
    
    swept_high = False
    swept_low = False
    
    if pd.notna(row['london_high']) and pd.notna(row['asia_high']):
        if row['london_high'] > row['asia_high']: swept_high = True
        
    if pd.notna(row['london_low']) and pd.notna(row['asia_low']):
        if row['london_low'] < row['asia_low']: swept_low = True
        
    if swept_high and swept_low:
        if row.get('london_high_first') == True:
            return "SWEEP_HIGH_FIRST" # High then Low
        else:
            return "SWEEP_LOW_FIRST" # Low then High
    elif swept_high:
        return "SWEEP_HIGH"
    elif swept_low:
        return "SWEEP_LOW"
    else:
        return "NO_SWEEP"

def classify_ny_sweep_outcome(row):
    """Classify what NY swept relative to London."""
    # hit_london_high, hit_london_low, hit_london_high_first
    h = row.get('hit_london_high') == True
    l = row.get('hit_london_low') == True
    hf = row.get('hit_london_high_first') == True
    
    if h and l:
        return "SWEEP_BOTH_HIGH_FIRST" if hf else "SWEEP_BOTH_LOW_FIRST"
    elif h:
        return "SWEEP_HIGH"
    elif l:
        return "SWEEP_LOW"
    else:
        return "NO_SWEEP"

def analyze_decision_tree(df):
    """72-scenario decision tree with conditional probabilities at every branch."""
    
    print("=" * 60)
    print("DECISION TREE ANALYSIS (72 Scenarios)")
    print("=" * 60)
    
    # Check requirements
    req_cols = ['asia_range_pct', 'london_open_vs_asia_mid', 'ny_position', 'hit_london_high', 'manipulation_reversed']
    missing = [c for c in req_cols if c not in df.columns]
    if missing:
        print(f"Missing columns for decision tree: {missing}")
        return

    # 1. Enrich DF
    work_df = df.copy()
    
    # Factor 1: Asia Range Size
    median_asia = work_df['asia_range_pct'].median()
    print(f"Median Asia Range %: {median_asia:.3f}%")
    work_df['asia_size'] = work_df['asia_range_pct'].apply(
        lambda x: 'ABOVE_AVG' if x > median_asia else 'BELOW_AVG'
    )
    
    # Factor 2: London Open vs Asia Mid (Already computed if not null)
    # Ensure it maps to string
    work_df['london_pos'] = work_df['london_open_vs_asia_mid'].fillna('UNKNOWN')
    
    # Factor 3: London Sweep Type
    work_df['london_sweep'] = work_df.apply(classify_london_sweep_type, axis=1)
    
    # Factor 4: NY Position
    work_df['ny_pos'] = work_df['ny_position'].fillna('UNKNOWN')
    
    # Factor 5: NY Outcome (Target)
    work_df['ny_outcome'] = work_df.apply(classify_ny_sweep_outcome, axis=1)
    
    # Grouping
    group_cols = ['asia_size', 'london_pos', 'london_sweep', 'ny_pos']
    
    # Aggregation
    summary = work_df.groupby(group_cols).agg(
        count=('date', 'count'),
        rev_rate=('manipulation_reversed', 'mean'), # might not be perfect proxy for every node outcome
        hit_london_high=('hit_london_high', 'mean'),
        hit_london_low=('hit_london_low', 'mean'),
        hit_london_high_first=('hit_london_high_first', 'mean')
    ).reset_index()
    
    # Filter for significant scenarios
    summary['hit_london_high'] *= 100
    summary['hit_london_low'] *= 100
    summary['hit_london_high_first'] *= 100
    summary['rev_rate'] *= 100
    
    print("\n--- Top Scenarios by Count ---")
    top_scenarios = summary.sort_values('count', ascending=False).head(10)
    print(top_scenarios.to_string(index=False))
    
    print("\n--- High Probability High-First Scenarios (>75% High First, N>20) ---")
    high_prob = summary[(summary['hit_london_high_first'] > 75) & (summary['count'] > 20)]
    print(high_prob.sort_values('hit_london_high_first', ascending=False).to_string(index=False))
    
    print("\n--- High Probability Low-First Scenarios (<25% High First, N>20) ---")
    low_prob = summary[(summary['hit_london_high_first'] < 25) & (summary['count'] > 20)]
    print(low_prob.sort_values('hit_london_high_first', ascending=True).to_string(index=False))
    
    # Specific comparison requested
    # "Asia Above Avg + London Open Below Asia Mid + London Sweep Asia Low + NY Open Below London Mid"
    print("\n--- Flowchart Example Check ---")
    example = summary[
        (summary['asia_size'] == 'ABOVE_AVG') & 
        (summary['london_pos'] == 'BELOW_ASIA_MID') & 
        (summary['london_sweep'] == 'SWEEP_LOW') & 
        (summary['ny_pos'] == 'BELOW_LONDON_MID')
    ]
    if not example.empty:
        print(example.to_string(index=False))
    else:
        print("Example scenario not found in data.")
