import pandas as pd

def analyze_gap_confluence(df_days: pd.DataFrame):
    if df_days.empty:
        return
        
    print("\n--- RTH Gap Confluence ---")
    
    # Gap Fill Rates
    print("Gap Fill Rates:")
    print(f"25% Fill: {df_days['gap_fill_25'].mean()*100:.1f}%")
    print(f"50% Fill: {df_days['gap_fill_50'].mean()*100:.1f}%")
    if 'gap_fill_100' in df_days.columns:
        print(f"100% Fill: {df_days['gap_fill_100'].mean()*100:.1f}%")
    else:
        print("100% Fill: Data missing")
    
    # Win Rate by Gap Alignment
    # Determine alignment
    # Bearish Manipulation + Gap Up = Confirming (Short at premium) ? 
    #   User prompt: "BEARISH_MANIPULATION + gap up -> short setup: what % reversed?"
    #   Yes, Gap Up into resistance is confirming for a short logic if we expect reversal.
    #   Wait, normally Gap Up is bullish. But for "Manipulation Reversal" (London swept High), 
    #   we expect price to drop. A Gap Up means we open HIGHER (nearer the stop/sweep level),
    #   which is better pricing for a short. 
    #   Assume "Confirming" means favorable for the setup.
    
    def get_gap_alignment(row):
        cols = row.index
        if 'rth_gap' not in cols or pd.isna(row['rth_gap']): 
             return "No Gap / Missing Data"
        
        manip = row.get('manipulation')
        gap = row['rth_gap']
        
        if pd.isna(gap): return "No Gap"
        
        if manip == "BEARISH_MANIPULATION":
            if gap > 0: return "Gap Up (Better Price)"
            elif gap < 0: return "Gap Down (Chasing)"
            else: return "Flat"
        elif manip == "BULLISH_MANIPULATION":
            if gap < 0: return "Gap Down (Better Price)"
            elif gap > 0: return "Gap Up (Chasing)"
            else: return "Flat"
        return "Neutral"

    if 'rth_gap' in df_days.columns:
        df_days['gap_align'] = df_days.apply(get_gap_alignment, axis=1)
        
        print("\nReversal Rate by Gap Alignment:")
        grouped = df_days[df_days['manipulation'] != "NO_MANIPULATION"].groupby(['manipulation', 'gap_align'])['manipulation_reversed'].agg(['count', 'mean'])
        grouped['mean'] = grouped['mean'] * 100
        print(grouped.round(1))
    else:
        print("\nRTH Gap Analysis Skipped (Missing Data)")
    
    return grouped
