import pandas as pd
import numpy as np
import os

def analyze_full_multimethod():
    in_path = 'data/analysis/em_master_dataset.csv'
    if not os.path.exists(in_path):
        print(f"Error: {in_path} not found.")
        return
        
    df = pd.read_csv(in_path)
    print(f"\n{'='*80}")
    print(f"=== COMPREHENSIVE MULTI-METHOD EM ANALYSIS (Sample: {len(df)} days) ===")
    print(f"{'='*80}")
    
    # ==========================================
    # PART 1: Define all EM Methods and Levels
    # ==========================================
    
    # EM Methods (Columns from CSV)
    methods = {
        'Straddle 0.85x (Close)': 'em_close_straddle_085',
        'Straddle 1.0x (Close)': 'em_close_straddle_100',
        'Straddle 0.85x (Open EOD)': 'em_open_straddle_085',
        'Straddle 1.0x (Open EOD)': 'em_open_straddle_100',
        'Synth VIX 0.85x (Open 9:30)': 'em_open_vix_synth_085',
        'Synth VIX 1.0x (Open 9:30)': 'em_open_vix_synth_100',
        'Scaled VIX 2.0x (Close)': 'em_close_vix_20'
    }
    
    # Level Multiples
    levels = [0.5, 0.618, 1.0, 1.272, 1.5, 1.618, 2.0]
    
    # ==========================================
    # PART 2: Calculate MAE/MFE for Each Combo
    # ==========================================
    
    results = []
    
    for method_name, col in methods.items():
        if col not in df.columns:
            print(f"  Warning: {col} not in dataset, skipping.")
            continue
            
        # Determine anchor (Open or Close)
        if 'open' in col.lower():
            anchor = df['open']
            mfe_col = 'high'
            mae_col = 'low'
        else:
            anchor = df['prev_close']
            mfe_col = 'high'
            mae_col = 'low'
        
        em_val = df[col]
        
        # MFE = (High - Anchor) / EM
        # MAE = (Anchor - Low) / EM
        mfe_mult = (df[mfe_col] - anchor) / em_val
        mae_mult = (anchor - df[mae_col]) / em_val
        
        for lvl in levels:
            # Containment at this level
            contained = (mfe_mult <= lvl) & (mae_mult <= lvl)
            containment_pct = contained.mean() * 100
            
            # Median MAE/MFE for days that breached this level
            breached = ~contained
            if breached.sum() > 0:
                med_mfe_breach = mfe_mult[breached].median()
                med_mae_breach = mae_mult[breached].median()
            else:
                med_mfe_breach = np.nan
                med_mae_breach = np.nan
            
            # Overall Median MAE/MFE
            med_mfe = mfe_mult.median()
            med_mae = mae_mult.median()
            
            results.append({
                'Method': method_name,
                'Level': f"{lvl*100:.1f}%",
                'Containment': f"{containment_pct:.1f}%",
                'Median MFE': f"{med_mfe:.3f}",
                'Median MAE': f"{med_mae:.3f}",
                'Med MFE (Breach)': f"{med_mfe_breach:.3f}" if not np.isnan(med_mfe_breach) else "N/A",
                'Med MAE (Breach)': f"{med_mae_breach:.3f}" if not np.isnan(med_mae_breach) else "N/A"
            })
    
    # ==========================================
    # PART 3: Output Results Table
    # ==========================================
    
    result_df = pd.DataFrame(results)
    
    print("\n--- Full Results Table ---")
    print(result_df.to_string(index=False))
    
    # ==========================================
    # PART 4: Summary: Best Method per Level
    # ==========================================
    
    print(f"\n{'='*80}")
    print("=== BEST METHOD PER LEVEL (Highest Containment) ===")
    print(f"{'='*80}")
    
    for lvl in levels:
        lvl_str = f"{lvl*100:.1f}%"
        sub = result_df[result_df['Level'] == lvl_str]
        if sub.empty: continue
        
        # Parse containment back to float for comparison
        sub = sub.copy()
        sub['Contain_Float'] = sub['Containment'].str.replace('%', '').astype(float)
        best_row = sub.loc[sub['Contain_Float'].idxmax()]
        
        print(f"Level {lvl_str}: {best_row['Method']:<35} -> Containment: {best_row['Containment']}")
    
    # ==========================================
    # PART 5: Save to CSV
    # ==========================================
    
    out_path = 'data/analysis/em_multimethod_results.csv'
    result_df.to_csv(out_path, index=False)
    print(f"\nFull results saved to: {out_path}")

if __name__ == "__main__":
    analyze_full_multimethod()
