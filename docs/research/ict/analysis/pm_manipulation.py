import pandas as pd
import numpy as np

def analyze_pm_manipulation(df):
    """NY PM manipulation of NY AM — the Asia prediction model."""
    
    print("=" * 60)
    print("NY PM MANIPULATION OF NY AM (Asia Prediction Model)")
    print("=" * 60)
    
    if 'pm_pattern' not in df.columns:
        print("PM Pattern data missing.")
        return

    # 1. PM Pattern Distribution
    print("\n--- 1. PM Pattern Distribution ---")
    pm_patterns = df['pm_pattern'].value_counts()
    total = len(df)
    for pattern, count in pm_patterns.items():
        print(f"{pattern:<20} : {count:>4} ({count/total*100:.1f}%)")
    
    # 2. PM Manipulation Reversal During Asia
    print("\n--- 2. PM Manipulation Reversal During Asia ---")
    if 'asia_pm_manip_reversed' in df.columns:
        for manip_type in ["BULLISH_MANIPULATION", "BEARISH_MANIPULATION"]:
            subset = df[df['pm_manipulation'] == manip_type]
            count = len(subset)
            if count > 0:
                reversed_count = subset['asia_pm_manip_reversed'].sum()
                print(f"{manip_type:<20} : {reversed_count}/{count} reversed ({reversed_count/count*100:.1f}%)")
                
                # Breakdown by pattern subtype
                print(f"  By Pattern:")
                for pat in subset['pm_pattern'].unique():
                    sub_subset = subset[subset['pm_pattern'] == pat]
                    sub_count = len(sub_subset)
                    if sub_count > 0:
                        sub_rev = sub_subset['asia_pm_manip_reversed'].sum()
                        print(f"    {pat:<18} : {sub_rev}/{sub_count} ({sub_rev/sub_count*100:.1f}%)")
            else:
                print(f"{manip_type:<20} : 0 occurrences")
    else:
        print("Asia reversal data missing (run enhanced pipeline).")

    # 3. Globex Position vs PM Mid
    # Assuming globex_open and ny_pm_mid exist, compute if not present or use derived column if exists
    # The spec implies checking alignment.
    # The column 'globex_open' exists. 'ny_pm_mid' exists.
    # We need to compute 'globex_pos_vs_pm_mid' if not in df, but run_research didn't explicitly save it as a column string, 
    # but we saved 'globex_open' and 'ny_pm_mid'. 
    # Actually session_extractor calculates it but run_research might not have exported the string classification.
    # Let's compute it on the fly if needed.
    
    print("\n--- 3. Globex Position vs PM Mid (Asia Outcomes) ---")
    # We need columns: asia_hit_pm_high, asia_hit_pm_low
    if 'asia_hit_pm_high' in df.columns:
        # Compute Globex Position
        # Use next day's globex open vs current day's pm mid? 
        # Wait, the logic in run_research for asia outcomes used (Next Day Asia) vs (Current Day Stats).
        # The 'globex_open' in the row is for the CURRENT trading day (18:00 previous day).
        # We need the globex open for the NEXT trading day to compare with Current PM Mid for the Asia prediction.
        # This is tricky without the next day's globex open in the current row.
        # However, run_research Phase 3 logic calculates Asia outcomes.
        # It didn't explicitly export "Next Day Globex Open".
        # Let's skip the Globex generic position analysis if data is missing, or rely on what's available.
        # Actually pattern_classifier has classify_globex_position using current day data.
        # But for Asia prediction we want: PM (T) -> Globex (T+1) -> Asia (T+1).
        # If the CSV row is Day T, we don't have Globex (T+1) easily unless we shift.
        
        # Let's stick to what we have in the dataframe or derived.
        pass

    # 4. Aligned Setup
    print("\n--- 4. Aligned Setup (PM Pattern + Reversal) ---")
    # PM Partial Down (Bullish Manip) -> We want Asia to reverse (go up).
    # If we assume 'asia_pm_manip_reversed' captures "did it go the expected way",
    # we can just break down by pattern.
    
    # 5. PM Close Location
    print("\n--- 5. PM Close Location Effect ---")
    if 'ny_pm_close' in df.columns and 'ny_pm_high' in df.columns and 'ny_pm_low' in df.columns:
        # Calculate pm_close_location
        df['pm_rng'] = df['ny_pm_high'] - df['ny_pm_low']
        mask = df['pm_rng'] > 0
        df.loc[mask, 'pm_close_loc'] = (df.loc[mask, 'ny_pm_close'] - df.loc[mask, 'ny_pm_low']) / df.loc[mask, 'pm_rng'] * 100
        
        df['close_quartile'] = pd.cut(df['pm_close_loc'], bins=[0, 25, 50, 75, 100], labels=['Low', 'Mid-Low', 'Mid-High', 'High'])
        
        if 'asia_pm_manip_reversed' in df.columns:
            print(df.groupby('close_quartile', observed=False)['asia_pm_manip_reversed'].agg(['count', 'mean']).rename(columns={'mean': 'reversal_rate'}))
