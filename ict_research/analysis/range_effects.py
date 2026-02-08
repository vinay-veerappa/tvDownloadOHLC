import pandas as pd
import numpy as np

def analyze_range_effects(df):
    """How do session range sizes affect all key probabilities?"""
    
    print("=" * 60)
    print("RANGE SIZE EFFECTS ON PROBABILITIES")
    print("=" * 60)
    
    req_cols = ['asia_range', 'london_range', 'manipulation_reversed']
    if not all(c in df.columns for c in req_cols):
        print("Range data missing.")
        return
        
    # Create quartiles if not exist
    try:
        df['asia_q'] = pd.qcut(df['asia_range'], 4, labels=['Small', 'Med', 'Large', 'XL'])
        df['london_q'] = pd.qcut(df['london_range'], 4, labels=['Small', 'Med', 'Large', 'XL'])
        
        # 1. Asia Range Quartile
        print("\n--- 1. Asia Range Effect on Reversal ---")
        print(df.groupby('asia_q', observed=False)['manipulation_reversed'].agg(['count', 'mean']).rename(columns={'mean': 'Rev Rate'}))
        
        # 2. London Range Quartile
        print("\n--- 2. London Range Effect on Reversal ---")
        print(df.groupby('london_q', observed=False)['manipulation_reversed'].agg(['count', 'mean']).rename(columns={'mean': 'Rev Rate'}))
        
        # 3. Combined Range Effect
        print("\n--- 3. Combined Range Effect (Asia + London) ---")
        combined = df.groupby(['asia_q', 'london_q'], observed=False)['manipulation_reversed'].mean().unstack()
        print(combined)
        
        # 4. CBDR Range x Sigma Reach
        if 'cbdr_asia_range' in df.columns and 'cbdr_upside_sigmas' in df.columns:
            df['cbdr_q'] = pd.qcut(df['cbdr_asia_range'], 4, labels=['Small', 'Med', 'Large', 'XL'])
            print("\n--- 4. CBDR Range Effect on Sigma Reach ---")
            print("Average Upside Sigmas:")
            print(df.groupby('cbdr_q', observed=False)['cbdr_upside_sigmas'].mean())
            
    except Exception as e:
        print(f"Error calculating quartiles: {e}")
