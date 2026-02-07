import pandas as pd
import numpy as np

def analyze_sweep_order(df):
    """London sweep order (high first vs low first) and Judas sequence."""
    
    print("=" * 60)
    print("SWEEP ORDER & JUDAS SEQUENCE ANALYSIS")
    print("=" * 60)
    
    # Check
    if 'hit_london_high_first' not in df.columns:
        print("Sweep order data missing.")
        return
        
    valid = df[df['hit_london_high_first'].notna()].copy()
    
    # 1. Sweep Order Distribution
    print("\n--- 1. Sweep Order Distribution (London) ---")
    high_first = valid['hit_london_high_first'].sum()
    total = len(valid)
    low_first = total - high_first
    
    print(f"High First : {high_first} ({high_first/total*100:.1f}%)")
    print(f"Low First  : {low_first} ({low_first/total*100:.1f}%)")
    
    # 2. Sweep Order x Manipulation -> Reversal Rate
    print("\n--- 2. Sweep Order x Manipulation -> Reversal Rate ---")
    if 'manipulation' in df.columns and 'manipulation_reversed' in df.columns:
        # Group by (High First, Manipulation)
        res = df.groupby(['hit_london_high_first', 'manipulation'])['manipulation_reversed'].agg(['count', 'mean']).rename(columns={'mean': 'Rev Rate'})
        print(res.unstack())
        
    # 3. Judas Detection
    print("\n--- 3. Judas Reversal Rate ---")
    # 'is_judas_london' might not be in export unless explicitly added to result dict in run_research.
    # It was not in the snippet shown before.
    # However we can calculate it:
    # Judas = Bullish Manip + Low First? No.
    # Judas = Bullish Manip but price went up first (faked long)? No.
    # Def: "Judas swing is a false move... before the real move."
    # If Bullish Manipulation (net move is up), Judas is a move DOWN first to sweep stops?
    # Or is Judas the fake move UP that traps?
    # The snippet in pattern_classifier said: 
    # if manipulation == "BULLISH_MANIPULATION": return not day.london_high_first (Low First -> False? Wait)
    # Let's check pattern_classifier logic if we can't find column.
    
    # Actually run_research calculate 'is_judas_pm' but maybe not is_judas_london?
    # Let's check if 'is_judas_london' is in df.
    if 'is_judas_london' in df.columns:
        judas = df[df['is_judas_london'] == True]
        non_judas = df[df['is_judas_london'] == False]
        
        print(f"Judas Days: {len(judas)} ({len(judas)/len(df)*100:.1f}%)")
        print(f"  Reversal Rate: {judas['manipulation_reversed'].mean()*100:.1f}%")
        print(f"Non-Judas Days: {len(non_judas)}")
        print(f"  Reversal Rate: {non_judas['manipulation_reversed'].mean()*100:.1f}%")
    else:
        # Calculate manually based on logic seen in classifier
        # Logic: Bullish Manip + Low First = Standard? Or Judas?
        # Usually: Bullish Day. Open -> Low (Judas) -> High -> Close.
        # But "Judas Swing" often refers to the specific fake out.
        # If we don't have the column, we skip.
        pass

    # 4. Same for PM (is_judas_pm)
    print("\n--- 4. PM Judas Analysis ---")
    if 'is_judas_pm' in df.columns:
        judas_pm = df[df['is_judas_pm'] == True]
        print(f"PM Judas Days: {len(judas_pm)}")
        # Check PM outcome? Reversal of AM range?
        if 'pm_hit_am_low' in df.columns:
             # Assume PM reversal logic
             pass
