import pandas as pd
import numpy as np
import os

def analyze_ensembles():
    in_path = 'data/analysis/em_master_dataset.csv'
    if not os.path.exists(in_path):
        print(f"Error: {in_path} not found.")
        return
        
    df = pd.read_csv(in_path)
    print(f"\n=== EM Ensemble & Variant Analysis (Sample: {len(df)} days) ===")
    
    # 1. Close-Anchored vs Open-Anchored vs Synthetic Open (9:30 AM)
    # We want to see which anchor has the best containment.
    
    # Standard Open (using EOD Straddle Pct)
    df['contain_open'] = (df['mfe_open'] <= 1.0) & (df['mae_open'] <= 1.0)
    # Synthetic Open (using 9:30 AM VIX)
    df['contain_open_synth'] = (df['mfe_open_synth'] <= 1.0) & (df['mae_open_synth'] <= 1.0)
    # Close-Anchored (Original)
    df['contain_close_085'] = (df['mfe_close'] <= 1.0) & (df['mae_close'] <= 1.0)
    
    print("\n[1] Anchor Performance (0.85x EM)")
    print(f" - Close-Anchored:              {df['contain_close_085'].mean()*100:.1f}%")
    print(f" - Open-Anchored (EOD-derived): {df['contain_open'].mean()*100:.1f}%")
    print(f" - Open-Anchored (9:30 AM Synthetic Straddle): {df['contain_open_synth'].mean()*100:.1f}%")
    
    # 2. 0.85x vs 1.0x Straddle Comparison
    # We test it on the Synthetic Open Anchor as it's the most high-fidelity for intraday.
    df['contain_open_synth_100'] = (df['mfe_open_synth'] <= 1.0 / 0.85) & (df['mae_open_synth'] <= 1.0 / 0.85)
                               
    print("\n[2] Straddle Multiplier Performance (9:30 AM Synthetic Anchor)")
    print(f" - 0.85x Straddle Containment: {df['contain_open_synth'].mean()*100:.1f}%")
    print(f" - 1.00x Straddle Containment: {df['contain_open_synth_100'].mean()*100:.1f}%")
    
    # 3. Ensemble Confluence
    # When multiple models agree on a level, is it more reliable?
    # Variables: em_close_straddle_085, em_252_iv, em_close_vix_20
    
    def get_confluence_strength(row):
        # Check if the three primary models are within 0.1% of each other
        vals = [row['em_close_straddle_085'], row['em_252_iv'], row['em_close_vix_20']]
        if any(v is None or np.isnan(v) for v in vals): return 0
        spread = (max(vals) - min(vals)) / row['prev_close']
        if spread < 0.001: return 3 # Tight confluence (10 bps)
        if spread < 0.0025: return 2 # Moderate confluence (25 bps)
        return 1 # Disagreement
        
    df['conf_strength'] = df.apply(get_confluence_strength, axis=1)
    
    print("\n[3] Multi-Method Ensemble Confluence")
    for s in [1, 2, 3]:
        sub = df[df['conf_strength'] == s]
        if sub.empty: continue
        desc = {1: "Disagreement", 2: "Moderate Confluence", 3: "Tight Confluence"}[s]
        print(f" - {desc:<20} | Count: {len(sub):<4} | Containment: {sub['contain_close_085'].mean()*100:>5.1f}%")

    # 4. Outlier Analysis with Multi-Method Agreement
    # Does confluence prevent breaches?
    print("\n[4] Level Breach Probability vs Confluence")
    for s in [1, 2, 3]:
        sub = df[df['conf_strength'] == s]
        if sub.empty: continue
        breach_rate = (1 - sub['contain_close_085'].mean()) * 100
        print(f" - {s}-Method Agreement Breach Rate: {breach_rate:>5.1f}%")

if __name__ == "__main__":
    analyze_ensembles()
