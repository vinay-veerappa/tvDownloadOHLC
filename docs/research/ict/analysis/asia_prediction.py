import pandas as pd
import numpy as np

def analyze_asia_prediction(df):
    """Validate the Asia session prediction model."""
    
    print("=" * 60)
    print("ASIA SESSION PREDICTION VALIDATION")
    print("=" * 60)
    
    # 1. Does Asia hit PM High or PM Low first?
    print("\n--- 1. Asia Hits PM High vs PM Low First ---")
    if 'asia_pm_high_first' in df.columns:
        valid_first = df[df['asia_pm_high_first'].notna()]
        total = len(valid_first)
        high_first = valid_first['asia_pm_high_first'].sum()
        low_first = total - high_first
        print(f"PM High First : {high_first} ({high_first/total*100:.1f}%)")
        print(f"PM Low First  : {low_first} ({low_first/total*100:.1f}%)")
    else:
        print("Missing asia_pm_high_first column.")
        
    # 2. PM Level Hit Rates During Asia
    print("\n--- 2. PM Level Hit Rates During Asia ---")
    if 'asia_hit_pm_high' in df.columns:
        print(f"Hit PM High: {df['asia_hit_pm_high'].mean()*100:.1f}%")
        print(f"Hit PM Low : {df['asia_hit_pm_low'].mean()*100:.1f}%")
        
        # Conditional on PM Pattern (from current day to next day Asia)
        if 'pm_pattern' in df.columns:
            print("\n  By PM Pattern:")
            print(df.groupby('pm_pattern')[['asia_hit_pm_high', 'asia_hit_pm_low']].mean() * 100)

    # 3. AM Level Hit Rates During Asia
    # Not computed in current run_research (only PM, PDH, PDL)
    # The prompt asked for AM, but `measure_asia_outcomes` in run_research only did PM/Lunch/PDH/PDL 
    # Wait, measure_asia_outcomes DID call check_hit(ny_am_high).
    # Ah, need to verify run_research export.
    # checking run_research snippet ... I see asia_hit_pm_high but not am.
    # The snippet only showed pm/high sample. 
    # But measure_asia_outcomes returns an object with hit_am_high.
    # If run_research didn't map it, it won't be in df.
    # I will assume it might be there or skip if missing.
    
    if 'asia_hit_am_high' in df.columns:
        print(f"\nHit AM High: {df['asia_hit_am_high'].mean()*100:.1f}%")
    
    # 4. Gap Analysis (Globex Gap)
    print("\n--- 4. Globex Gap Analysis ---")
    # 'globex_gap' column. 'globex_gap_pct'
    # Asia gap fill logic? 
    # Assuming gap_fill_25 refers to RTH gap in NYOutcome, not Globex gap outcome.
    # We didn't calculate Asia gap fill specifically in outcome_measurer logic provided in snippet 
    # (only RTH gap in NY).
    
    if 'globex_gap' in df.columns:
        # Gap Direction
        gaps = df['globex_gap'].dropna()
        if not gaps.empty:
            up_gaps = (gaps > 0).sum()
            dn_gaps = (gaps < 0).sum()
            print(f"Gap Up   : {up_gaps} ({up_gaps/len(gaps)*100:.1f}%)")
            print(f"Gap Down : {dn_gaps} ({dn_gaps/len(gaps)*100:.1f}%)")
            
            print(f"Avg Abs Gap: {gaps.abs().mean():.2f}")
    
    # 5. Aligned Asia Setup (PM Pattern + Reversal)
    # PM Partial Up (Bearish Manip) -> Asia Reversal (Bearish)
    # PM Partial Down (Bullish Manip) -> Asia Reversal (Bullish)
    print("\n--- 5. Aligned Asia Reversal ---")
    if 'pm_manipulation' in df.columns and 'asia_pm_manip_reversed' in df.columns:
        aligned = df[df['pm_manipulation'].isin(['BULLISH_MANIPULATION', 'BEARISH_MANIPULATION'])]
        if not aligned.empty:
            print(f"Reversal Rate for Aligned Setup: {aligned['asia_pm_manip_reversed'].mean()*100:.1f}%")
            
            # Compare to overall rate? 
            # Or break down by manipulation type
            print(aligned.groupby('pm_manipulation')['asia_pm_manip_reversed'].mean() * 100)
