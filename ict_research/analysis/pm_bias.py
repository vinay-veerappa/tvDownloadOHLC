import pandas as pd
import numpy as np

def analyze_pm_bias(df):
    """NY PM session bias — does PM reverse or continue AM?"""
    
    print("=" * 60)
    print("NY PM BIAS ANALYSIS")
    print("=" * 60)
    
    # 1. AM High vs AM Low hit-first during PM
    print("\n--- 1. PM Hits AM High vs AM Low First ---")
    if 'pm_am_high_first' in df.columns:
        valid = df[df['pm_am_high_first'].notna()]
        total = len(valid)
        if total > 0:
            high_first = valid['pm_am_high_first'].sum()
            low_first = total - high_first
            print(f"AM High First : {high_first} ({high_first/total*100:.1f}%)")
            print(f"AM Low First  : {low_first} ({low_first/total*100:.1f}%)")
            
            # Conditional on manipulation type (London manipulation)
            if 'manipulation' in df.columns:
                print("\n  By London Manipulation:")
                print(valid.groupby('manipulation')['pm_am_high_first'].agg(['count', 'mean']).rename(columns={'mean': 'High First Rate'}))
    
    # 2. Does PM reverse AM or continue?
    # Logic: If AM High > AM Open (Bullish AM candle), did PM go lower than AM Low?
    print("\n--- 2. PM Extension vs Reversal ---")
    req_cols = ['ny_am_high', 'ny_am_low', 'ny_am_open', 'pm_hit_am_low', 'pm_hit_am_high']
    if all(c in df.columns for c in req_cols):
        # Identify AM bias
        # Simple candle color: Close > Open? Or just relative to midnight? 
        # Usually "AM trend" is defined by expansion.
        # Let's use Open vs Close of AM.
        # 'ny_am_close' should be available from session stats.
        if 'ny_am_close' in df.columns:
            df['am_bullish'] = df['ny_am_close'] > df['ny_am_open']
            
            # If AM Bullish -> Reversal is hitting AM Low. Continuation is hitting AM High (making new high).
            # Note: PM typically manipulates or expands.
            
            bull_am = df[df['am_bullish'] == True]
            bear_am = df[df['am_bullish'] == False]
            
            p_rev_bull = bull_am['pm_hit_am_low'].mean()
            p_cont_bull = bull_am['pm_hit_am_high'].mean() # Continuation (break high)
            
            p_rev_bear = bear_am['pm_hit_am_high'].mean()
            p_cont_bear = bear_am['pm_hit_am_low'].mean() # Continuation (break low)
            
            print(f"AM Bullish: {len(bull_am)} days")
            print(f"  PM Reverses (Hits AM Low) : {p_rev_bull*100:.1f}%")
            print(f"  PM Continues (Hits AM High): {p_cont_bull*100:.1f}%")
            
            print(f"AM Bearish: {len(bear_am)} days")
            print(f"  PM Reverses (Hits AM High) : {p_rev_bear*100:.1f}%")
            print(f"  PM Continues (Hits AM Low) : {p_cont_bear*100:.1f}%")

    # 3. Lunch as transition
    # Does lunch high/low get hit during PM?
    # Not explicitly in run_research output (we did measure_pm_outcomes but need to check if we exported lunch hits)
    # The snippet only showed pm_hit_am_*.
    # So skipping.
    
    # 4. London levels during PM
    # P(PM hits London High), P(PM hits London Low)
    # Check export.
    # Logic in measure_pm_outcomes checked london_high.
    # But run_research snippet only exported 'pm_hit_am_high/low' and 'pm_am_high_first'.
    # I'd need to verify if full export. Assuming partial export in snippet, likely missing.
    pass
