import pandas as pd
from playbook_analyzer import PlaybookAnalyzer
import sys

# Constants
DATA_PATH = r"c:\Users\vinay\tvDownloadOHLC\data\NQ1_1m.parquet"

def print_stats_table(name, df, key_filter_col=None, key_filter_val=True):
    """
    Prints a Herman-style stats table for the given DataFrame subset.
    """
    print(f"\n### {name} Analysis")
    print(f"Total Days: {len(df)}")
    
    # Metrics
    # 1. First Sweep Distribution
    high_wins = len(df[df['london_first_sweep'] == 'High'])
    low_wins = len(df[df['london_first_sweep'] == 'Low'])
    none_wins = len(df[df['london_first_sweep'] == 'None'])
    total = len(df)
    
    print(f"\n**First Sweep Distribution**:")
    print(f"- High First: {high_wins} ({high_wins/total*100:.1f}%)")
    print(f"- Low First:  {low_wins} ({low_wins/total*100:.1f}%)")
    print(f"- None:       {none_wins} ({none_wins/total*100:.1f}%)")
    
    # 2. Median Penetration
    pen_h = df[df['london_first_sweep'] == 'High']['london_penetration'].median()
    pen_l = df[df['london_first_sweep'] == 'Low']['london_penetration'].median()
    print(f"\n**Median Penetration**:")
    print(f"- High Breaks: {pen_h:.2f} pts")
    print(f"- Low Breaks:  {pen_l:.2f} pts")
    
    # 3. Continuation Stats (if context available)
    # Check correlations: If PL Swept High -> Does Exp Sweep High?
    # Context specific checks
    if 'pl_sweeps_high' in df.columns:
        # P(Exp High | PL High)
        pl_h = df[df['pl_sweeps_high']]
        if not pl_h.empty:
            exp_h = len(pl_h[pl_h['london_first_sweep'] == 'High'])
            print(f"\n**Context Correlation**:")
            print(f"- If Setup Swept High -> Expansion Sweeps High: {exp_h/len(pl_h)*100:.1f}% (Follow)")
            print(f"- If Setup Swept High -> Expansion Sweeps Low:  {100 - (exp_h/len(pl_h)*100):.1f}% (Reversal?)")

def main():
    print("Loading Data...")
    df = pd.read_parquet(DATA_PATH)
    analyzer = PlaybookAnalyzer(df)
    
    # --- 1. LONDON VALIDATION ---
    print("\n" + "="*50)
    print("PHASE 1: LONDON PLAYBOOK VALIDATION")
    print("="*50)
    
    # Params: Asia (20-00), PL (00-02), OR (02-03), Lon (03-05)
    # Herman used 02:00-03:00 as OR. And 03:00 start for London Logic.
    # Our Analyzer handles this naturally.
    lon_stats = analyzer.analyze_session(
        "20:00", "00:00", # Base (Asia)
        "00:00", "02:00", # Setup (PL)
        "02:00", "03:00", # Trigger (OR)
        "03:00", "05:00"  # Expansion (London)
    )
    
    # Filter Small vs Large Asia
    # Herman Avg = 70.9. Let's use 71.
    lon_stats['is_large_asia'] = lon_stats['base_range'] > 70.9
    
    print("\n--- Large Asia London Stats ---")
    print_stats_table("Large Asia (London)", lon_stats[lon_stats['is_large_asia']])
    
    print("\n--- Small Asia London Stats ---")
    print_stats_table("Small Asia (London)", lon_stats[~lon_stats['is_large_asia']])


    # --- 2. NY AM EXTENSION ---
    print("\n" + "="*50)
    print("PHASE 2: NY AM EXTENSION")
    print("="*50)
    
    # Base: London (02:00-07:00?) User said "London range parameters".
    # Setup: Pre-NY (Implicit? Maybe 05:00-07:00?)
    # Trigger: 07:00-08:00 (User Specified)
    # Expansion: 08:00-11:00 (Morning Session)
    
    ny_am_stats = analyzer.analyze_session(
        "02:00", "05:00", # Base (London Decision Phase)
        "05:00", "07:00", # Setup (Pre-market gap)
        "07:00", "08:00", # Trigger (NY OR)
        "08:00", "11:00"  # Expansion
    )
    print_stats_table("NY AM Extension (07:00 OR)", ny_am_stats)
    
    
    # --- 3. NY PM EXTENSION ---
    print("\n" + "="*50)
    print("PHASE 3: NY PM EXTENSION (Variants)")
    print("="*50)
    
    # Variant A: Lunch Range (12:00-13:00) as Trigger
    # Base: NY AM (07:00-12:00)
    # Setup: None/Implicit
    # Trigger: 12:00-13:00
    # Expansion: 13:00-16:00
    
    pm_var_a = analyzer.analyze_session(
        "07:00", "12:00", # Base (AM Session)
        "11:00", "12:00", # Setup (11-12)
        "12:00", "13:00", # Trigger (Lunch)
        "13:00", "16:00"  # Expansion
    )
    print_stats_table("NY PM Variant A (Lunch 12-13 OR)", pm_var_a)
    
    # Variant B: 13:00-14:00 Range as Trigger
    # Trigger: 13:00-14:00
    # Expansion: 14:00-16:00
    pm_var_b = analyzer.analyze_session(
        "07:00", "12:00", 
        "12:00", "13:00", # Setup (Lunch becomes the 'Pre-London' equiv)
        "13:00", "14:00", # Trigger
        "14:00", "16:00"  # Expansion
    )
    print_stats_table("NY PM Variant B (13-14 OR)", pm_var_b)

    # Save logic to file? Markdown report later.

if __name__ == "__main__":
    main()
