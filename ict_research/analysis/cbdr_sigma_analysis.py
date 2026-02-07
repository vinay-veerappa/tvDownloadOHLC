import pandas as pd
import numpy as np

def analyze_cbdr_sigma(df):
    """CBDR standard deviation reach analysis."""
    
    print("=" * 60)
    print("CBDR STANDARD DEVIATION ANALYSIS")
    print("=" * 60)
    
    # Check for CBDR columns
    if 'cbdr_asia_range' not in df.columns:
        print("CBDR Asia range columns missing.")
        return

    # Filter invalid
    valid_df = df[df['cbdr_asia_range'] > 0]
    total = len(valid_df)
    
    # 1. Sigma Reach Distribution
    print("\n--- 1. Sigma Reach Distribution (Asia CBDR) ---")
    sigmas = [0.5, 1, 1.5, 2, 2.5, 3, 4]
    
    # We expect columns like cbdr_hit_up_0_5, cbdr_hit_dn_1_5 (dots replaced by _)
    # run output has . converted to _
    
    # Store aggregated stats
    hit_stats = []
    
    for s in sigmas:
        s_str = str(s).replace('.', '_')
        up_col = f'cbdr_hit_up_{s_str}'
        dn_col = f'cbdr_hit_dn_{s_str}'
        
        up_pct = 0
        dn_pct = 0
        either_pct = 0
        
        cols_exist = up_col in valid_df.columns and dn_col in valid_df.columns
        if cols_exist:
            up_pct = valid_df[up_col].mean()
            dn_pct = valid_df[dn_col].mean()
            either_pct = (valid_df[[up_col, dn_col]].any(axis=1)).mean()
            
        hit_stats.append({
            'Sigma': s,
            'Up %': up_pct,
            'Dn %': dn_pct,
            'Either %': either_pct
        })
        
    res_df = pd.DataFrame(hit_stats)
    # Format percentages
    for col in ['Up %', 'Dn %', 'Either %']:
        res_df[col] = (res_df[col] * 100).map('{:.1f}%'.format)
        
    print(res_df.to_string(index=False))
    
    # 2. Actual Sigma Reach Statistics
    print("\n--- 2. Actual Sigma Reach Statistics ---")
    if 'cbdr_upside_sigmas' in valid_df.columns:
        print("Upside Sigmas (Max Reached):")
        print(valid_df['cbdr_upside_sigmas'].describe(percentiles=[0.25, 0.5, 0.75, 0.9]))
    if 'cbdr_downside_sigmas' in valid_df.columns:
        print("\nDownside Sigmas (Max Reached):")
        print(valid_df['cbdr_downside_sigmas'].describe(percentiles=[0.25, 0.5, 0.75, 0.9]))
        
    # 3. Conditional on Manipulation Type
    print("\n--- 3. Conditional on Manipulation Type ---")
    if 'pm_manipulation' in valid_df.columns:
        # Bullish -> expect more upside? Bearish -> downside?
        # Actually checking NY manipulation or PM manipulation?
        # "cbdr_asia" is usually analyzed for the NY session.
        # So check 'manipulation' column (NY manipulation based on London).
        if 'manipulation' in valid_df.columns:
            for m_type in ['BULLISH_MANIPULATION', 'BEARISH_MANIPULATION']:
                print(f"\n{m_type}:")
                sub = valid_df[valid_df['manipulation'] == m_type]
                if not sub.empty:
                    # quick check for 2.0 sigma
                    up_2 = sub['cbdr_hit_up_2'].mean() if 'cbdr_hit_up_2' in sub.columns else 0
                    dn_2 = sub['cbdr_hit_dn_2'].mean() if 'cbdr_hit_dn_2' in sub.columns else 0
                    print(f"  Hit Up 2.0 Sigma: {up_2*100:.1f}%")
                    print(f"  Hit Dn 2.0 Sigma: {dn_2*100:.1f}%")

    # 4. Conditional on CBDR Range Size
    print("\n--- 4. Conditional on CBDR Range Size ---")
    # Quartiles
    try:
        valid_df['rng_quartile'] = pd.qcut(valid_df['cbdr_asia_range'], 4, labels=['Small', 'Med', 'Large', 'XL'])
        if 'cbdr_upside_sigmas' in valid_df.columns:
             print("\nAverage Upside Sigmas by Range Size:")
             print(valid_df.groupby('rng_quartile')['cbdr_upside_sigmas'].mean())
             
        if 'cbdr_downside_sigmas' in valid_df.columns:
             print("\nAverage Downside Sigmas by Range Size:")
             print(valid_df.groupby('rng_quartile')['cbdr_downside_sigmas'].mean())
    except Exception as e:
        print(f"Could not calculate quartiles: {e}")
