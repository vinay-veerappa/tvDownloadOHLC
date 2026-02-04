
import pandas as pd
import numpy as np
from pathlib import Path

# --- CONFIG ---
DATA_PATH = Path("data/derived/NQ1_herman_stats.parquet")
ASIA_THRESHOLD = 70.9

def load_data():
    if not DATA_PATH.exists():
        print(f"Error: {DATA_PATH} not found.")
        return None
    return pd.read_parquet(DATA_PATH)

def calc_prob(df, condition_mask, target_mask):
    subset_mask = np.array(condition_mask)
    n = subset_mask.sum()
    if n == 0: return 0.0, 0
    k = (subset_mask & np.array(target_mask)).sum()
    return (k / n) * 100, n

def analyze_branch(df, parent_mask, branch_name):
    print(f"\n{branch_name}")
    
    # Node 2: OR Break Direction (02:00-03:00) 
    # Did OR break PL High or Low?
    # Logic: The image implies "OR outcomes distribution: No Sweep, Swept Low, Swept High..."
    # So we check if OR (02:00-03:00) exceeded PL (00:00-02:00) High or Low.
    
    # We need PL High/Low from the dataframe.
    # Note: PL High/Low might be NaN if PL was empty? Usually not in NQ.
    
    or_sweeps_pl_h = (df['or_high'] > df['pl_high']) & (~pd.isna(df['pl_high']))
    or_sweeps_pl_l = (df['or_low'] < df['pl_low']) & (~pd.isna(df['pl_low']))
    
    # --- SUB-BRANCHES ---
    scenarios = [
        ("OR Swept High (Bullish Impulse)", or_sweeps_pl_h & ~or_sweeps_pl_l),
        ("OR Swept Low (Bearish Impulse)", or_sweeps_pl_l & ~or_sweeps_pl_h),
        ("OR Swept Both (Expansion)", or_sweeps_pl_h & or_sweeps_pl_l),
        ("OR Inside (Consolidation)", ~or_sweeps_pl_h & ~or_sweeps_pl_l)
    ]
    
    for name, mask in scenarios:
        current_mask = parent_mask & mask
        n_current = current_mask.sum()
        if n_current < 5: continue # Skip noise
        
        # Leaf: London Continuation Direction
        # "London first: High 80% / Low 20%"
        # Did London (02:00-05:00) break the Session High or Session Low FIRST?
        # Or simply, did London Close > Open? Or did it sweep Asia High/Low?
        # The Decision Tree leaf metric says "London first: High XX%".
        # This usually refers to EXTENSION.
        # Let's use: Did London Sweep ASIA High vs Low?
        
        prob_h, _ = calc_prob(df, current_mask, df['lon_sweeps_asia_h'])
        prob_l, _ = calc_prob(df, current_mask, df['lon_sweeps_asia_l'])
        
        print(f"  ├─ {name:<30} (n={n_current})")
        print(f"  │  Result: High {prob_h:.1f}% | Low {prob_l:.1f}%")

def main():
    df = load_data()
    if df is None: return
    
    print("="*60)
    print("HERMAN PLAYBOOK: GRANULAR DECISION TREE REPLICATION")
    print("="*60)
    
    # Root: Asia Size
    mask_small = df['asia_range'] <= ASIA_THRESHOLD
    mask_big = df['asia_range'] > ASIA_THRESHOLD
    
    # --- BRANCH 1: SMALL ASIA (< 70.9 pts) ---
    print(f"\nROOT 1: SMALL ASIA (n={mask_small.sum()})")
    
    # Node 1: PL Sweep
    # Did PL Sweep Asia High? Low? Both? None?
    pl_sw_h = df['pl_sweeps_asia_h']
    pl_sw_l = df['pl_sweeps_asia_l']
    
    mask_pl_sw_low_only = mask_small & pl_sw_l & ~pl_sw_h
    mask_pl_sw_high_only = mask_small & pl_sw_h & ~pl_sw_l
    mask_pl_no_sweep = mask_small & ~pl_sw_h & ~pl_sw_l
    
    analyze_branch(df, mask_pl_sw_low_only, "1. PL Swept Asia LOW (reversal setup?)")
    analyze_branch(df, mask_pl_sw_high_only, "2. PL Swept Asia HIGH (reversal setup?)")
    analyze_branch(df, mask_pl_no_sweep, "3. PL Inside Asia (Expansion setup?)")
    
    # --- BRANCH 2: BIG ASIA (> 70.9 pts) ---
    print(f"\nROOT 2: BIG ASIA (n={mask_big.sum()})")
    mask_pl_sw_low_big = mask_big & pl_sw_l & ~pl_sw_h
    mask_pl_sw_high_big = mask_big & pl_sw_h & ~pl_sw_l
    
    analyze_branch(df, mask_pl_sw_low_big, "1. PL Swept Asia LOW")
    analyze_branch(df, mask_pl_sw_high_big, "2. PL Swept Asia HIGH")

if __name__ == "__main__":
    main()
