import pandas as pd

def analyze_all_levels(df):
    """Comprehensive hit rate table for ALL reference levels."""
    
    print("=" * 60)
    print("COMPREHENSIVE LEVEL HIT RATES")
    print("=" * 60)
    
    # Identify hit columns
    hit_cols = [c for c in df.columns if c.startswith('hit_') or c.startswith('pm_hit_') or c.startswith('asia_hit_') or c.startswith('cbdr_hit_')]
    
    results = []
    
    for col in hit_cols:
        # Calculate overall hit rate
        overall = df[col].mean() * 100
        
        # Bullish Manip
        bull_manip = df[df['manipulation'] == 'BULLISH_MANIPULATION'][col].mean() * 100 if 'manipulation' in df.columns else 0
        bear_manip = df[df['manipulation'] == 'BEARISH_MANIPULATION'][col].mean() * 100 if 'manipulation' in df.columns else 0
        
        # Aligned Setup (Assuming "Aligned Long" = Bullish Manip + Above?)
        # Need correct definitions.
        # Let's stick to simple breakdown.
        
        results.append({
            'Level': col,
            'Overall %': f"{overall:.1f}%",
            'Bull Manip %': f"{bull_manip:.1f}%",
            'Bear Manip %': f"{bear_manip:.1f}%"
        })
        
    res_df = pd.DataFrame(results).sort_values('Level')
    
    # Print table
    print(res_df.to_string(index=False))
    
    # Also show hit-first pair
    # Check for columns like 'on_high_first', 'p12_high_first'
    first_cols = [c for c in df.columns if c.endswith('_first') and not c.startswith('hit_')] # hit_london_high_first is exception
    # Actually most are bool
    
    print("\n--- Hit First Analysis ---")
    first_stats = []
    # Identify relevant columns
    cols_to_check = ['on_high_first', 'p12_high_first', 'pm_am_high_first', 'asia_pm_high_first', 'hit_london_high_first']
    
    for c in cols_to_check:
        if c in df.columns:
            high_pct = df[c].mean() * 100
            low_pct = 100 - high_pct
            first_stats.append({
                'Pair': c,
                'High First %': f"{high_pct:.1f}%",
                'Low First %': f"{low_pct:.1f}%"
            })
            
    if first_stats:
        print(pd.DataFrame(first_stats).to_string(index=False))
