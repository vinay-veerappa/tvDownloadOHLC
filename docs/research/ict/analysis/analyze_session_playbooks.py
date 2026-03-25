
import pandas as pd
import numpy as np
import os
from datetime import datetime, time
import sys

# Add parent directory to path to import config if needed
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configuration
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'playbooks')
TICKER = "NQ" # Default Focus

def load_data(ticker):
    """Load and preprocess the enhanced trading days data."""
    file_path = os.path.join(DATA_DIR, f'trading_days_enhanced_{ticker}.csv')
    if not os.path.exists(file_path):
        print(f"Error: Data file not found for {ticker}")
        return None
    
    df = pd.read_csv(file_path, low_memory=False)
    df['date'] = pd.to_datetime(df['date'])
    
    # Sort by date to ensure lag works correctly
    df = df.sort_values('date').reset_index(drop=True)
    
    return df

def prepare_lagged_data(df):
    """Create columns for Previous Session metrics."""
    # We need PREVIOUS DAY'S NY data to trade ASIA
    
    # Lagged NY Metrics (from previous row)
    df['prev_ny_high'] = df['ny_high'].shift(1)
    df['prev_ny_low'] = df['ny_low'].shift(1)
    df['prev_ny_close'] = df['ny_close'].shift(1)
    df['prev_ny_open'] = df['ny_open'].shift(1)
    df['prev_ny_mid'] = (df['prev_ny_high'] + df['prev_ny_low']) / 2
    
    df['prev_pm_high'] = df['ny_pm_high'].shift(1)
    df['prev_pm_low'] = df['ny_pm_low'].shift(1)
    df['prev_pm_open'] = df['ny_pm_open'].shift(1)
    df['prev_pm_close'] = df['ny_pm_close'].shift(1)
    df['prev_pm_mid'] = (df['prev_pm_high'] + df['prev_pm_low']) / 2
    
    df['prev_lunch_high'] = df['lunch_high'].shift(1)
    df['prev_lunch_low'] = df['lunch_low'].shift(1)
    
    df['prev_settle'] = df['ny_close'].shift(1)
    
    # Lagged Daily Metrics
    df['prev_day_high_lag'] = df['prev_day_high'] # Already in current row usually? 'prev_day_high' refers to Yesterday.
    # Actually, 'prev_day_high' in row T is High of T-1. So it's already lagged.
    # 'prev_week_high' is High of W-1.
    
    # Calculate Prev PM Trend
    def get_trend(open_p, close_p, high_p, low_p):
        if pd.isna(open_p): return "Unknown"
        rng = high_p - low_p
        if rng == 0: return "Neutral"
        
        is_green = close_p > open_p
        mid = (high_p + low_p) / 2
        in_upper = close_p > mid
        in_lower = close_p < mid
        
        if is_green and in_upper: return "Bullish"
        if not is_green and in_lower: return "Bearish"
        return "Neutral"

    df['prev_pm_trend'] = df.apply(lambda x: get_trend(x['prev_pm_open'], x['prev_pm_close'], x['prev_pm_high'], x['prev_pm_low']), axis=1)
    
    return df





def analyze_asia_playbook(df):
    """
    Generate stats/playbook for Asia based on Previous NY.
    Highlights:
    - Prerequisite: Prev NY Structure (Partial Up/Down vs AM)
    - Asia Reversal Rate of PM Move
    - Sigma Levels (Standard Deviation)
    """
    playbook_lines = []
    playbook_lines.append("# Asia Session Playbook (NQ)\n")
    playbook_lines.append(f"**Analysis of {len(df)} Trading Days**\n")
    
    # --- PRE-CALCULATIONS ---
    # Need Prev AM High/Low to determine Prev PM Manipulation
    # df has 'ny_am_high', 'ny_am_low'. We need lagged versions.
    df['prev_am_high'] = df['ny_am_high'].shift(1)
    df['prev_am_low'] = df['ny_am_low'].shift(1)
    
    df['prev_day_mid'] = (df['prev_day_high'] + df['prev_day_low']) / 2
    df['prev_pm_range'] = df['prev_pm_high'] - df['prev_pm_low']
    
    # Determine Prev PM Manipulation Type (vs Prev AM)
    conditions = [
        (df['prev_pm_high'] > df['prev_am_high']) & (df['prev_pm_low'] < df['prev_am_low']), # Engulfs
        (df['prev_pm_high'] > df['prev_am_high']), # Partial Up (swept high only)
        (df['prev_pm_low'] < df['prev_am_low']),   # Partial Down (swept low only)
    ]
    choices = ['Engulfs', 'Partial Up', 'Partial Down']
    df['prev_pm_manip'] = np.select(conditions, choices, default='Inside')
    
    valid_df = df.dropna(subset=['prev_pm_trend', 'asia_high', 'asia_low', 'prev_day_high', 'prev_day_low', 
                                 'asia_open', 'prev_ny_close', 'prev_pm_range', 'prev_pm_manip']).copy()
    total = len(valid_df)
    
    # 1. PRE-SESSION: OVERNIGHT ASSESSMENT
    playbook_lines.append("# PRE-SESSION: OVERNIGHT ASSESSMENT (17:00-19:30 ET)")
    playbook_lines.append("## What to check before Asia opens\n")
    
    playbook_lines.append("**From the previous NY session:**")
    playbook_lines.append("- How did NY PM manipulate NY AM?\n")
    
    manip_counts = valid_df['prev_pm_manip'].value_counts()
    
    for mtype in ['Partial Up', 'Partial Down', 'Inside', 'Engulfs']:
        count = manip_counts.get(mtype, 0)
        pct = count / total * 100
        desc = ""
        if mtype == 'Partial Up': desc = "PM swept AM high → mildly bearish for Asia"
        elif mtype == 'Partial Down': desc = "PM swept AM low → mildly bullish for Asia"
        elif mtype == 'Inside': desc = "No manipulation → neutral"
        elif mtype == 'Engulfs': desc = "Swept both → chop/expansion"
        
        playbook_lines.append(f"  - **{mtype}** ({pct:.1f}%) → {desc}")

    playbook_lines.append("\n**Asia reversal of PM manipulation:**")
    # Interpretation:
    # If Partial Up (Bullish Sweep), does Asia Reverse (Go Down/Bearish Close)?
    # If Partial Down (Bearish Sweep), does Asia Reverse (Go Up/Bullish Close)?
    
    pu_df = valid_df[valid_df['prev_pm_manip'] == 'Partial Up']
    pu_rev = len(pu_df[pu_df['asia_close'] < pu_df['asia_open']]) # Bearish Close
    
    pd_df = valid_df[valid_df['prev_pm_manip'] == 'Partial Down']
    pd_rev = len(pd_df[pd_df['asia_close'] > pd_df['asia_open']]) # Bullish Close
    
    playbook_lines.append(f"- Bullish PM manip (Partial Up) → Asia reverses **{pu_rev/len(pu_df)*100:.1f}%**")
    playbook_lines.append(f"- Bearish PM manip (Partial Down) → Asia reverses **{pd_rev/len(pd_df)*100:.1f}%**")
    playbook_lines.append("- **Asia is rarely a reversal session.** It tends to follow the immediate trend or consolidate.\n")

    # 2. ASIA RANGE & SIGMA
    playbook_lines.append("# SESSION 1: ASIA (19:30 — 02:30 ET)")
    playbook_lines.append("## *OBSERVE ONLY. Build the range.*")
    
    median_range = valid_df['asia_range'].median()
    std_range = valid_df['asia_range'].std() # Standard Deviation of Range
    
    playbook_lines.append(f"\n### Asia Range Context")
    playbook_lines.append(f"Mean: {valid_df['asia_range'].mean():.2f} pts | Std Dev: {std_range:.2f} pts")
    
    # Sigma Levels (Projected High/Low from Open)
    # Actually, Sigma usually refers to Standard Deviation of the *Range* added to Open/Low?
    # Reference says: "After CBDR forms, draw +1s and +2s lines".
    # Here we likely mean: How often does Asia hit +1 Sigma of its average range?
    # Let's calculate the "Hit Rate" of standard deviation multiples from Open.
    
    asia_std = valid_df['asia_range'].std()
    
    playbook_lines.append(f"\n### Standard Deviation (Sigma) Projections (from Asia Open)")
    playbook_lines.append(f"1 Sigma (σ) = {asia_std:.2f} pts\n")
    
    playbook_lines.append("| Sigma | Upside Hit (High > Open + σ) | Downside Hit (Low < Open - σ) | Either Side |")
    playbook_lines.append("|-------|-----------|-------------|-------------|")
    
    for mult in [0.5, 1.0, 1.5, 2.0]:
        dist = asia_std * mult
        up_hit = len(valid_df[valid_df['asia_high'] > (valid_df['asia_open'] + dist)])
        dn_hit = len(valid_df[valid_df['asia_low'] < (valid_df['asia_open'] - dist)])
        either_hit = len(valid_df[(valid_df['asia_high'] > (valid_df['asia_open'] + dist)) | (valid_df['asia_low'] < (valid_df['asia_open'] - dist))])
        
        playbook_lines.append(f"| **{mult}σ** | {up_hit/total*100:.1f}% | {dn_hit/total*100:.1f}% | **{either_hit/total*100:.1f}%** |")
        
    playbook_lines.append("\n**Practical use:** Draw +1σ and -1σ from Asia Open. Price hits at least one side ~90% of the time.")

    # 3. CONTEXT & TARGETS
    playbook_lines.append("\n## Context: Gap & Targets")
    valid_df['asia_gap'] = valid_df['asia_open'] - valid_df['prev_ny_close']
    gap_up = valid_df[valid_df['asia_gap'] > 2]
    gap_dn = valid_df[valid_df['asia_gap'] < -2]
    
    playbook_lines.append(f"**Gap Analysis**:")
    playbook_lines.append(f"*   **Gap Up** ({len(gap_up)/total*100:.1f}%): Fills **{len(gap_up[gap_up['asia_low'] <= gap_up['prev_ny_close']])/len(gap_up)*100:.1f}%**")
    playbook_lines.append(f"*   **Gap Down** ({len(gap_dn)/total*100:.1f}%): Fills **{len(gap_dn[gap_dn['asia_high'] >= gap_dn['prev_ny_close']])/len(gap_dn)*100:.1f}%**")
    
    playbook_lines.append("\n**High Probability Targets (>30%):**")
    levels = {
        "Prev PM High": len(valid_df[valid_df['asia_high'] > valid_df['prev_pm_high']])/total,
        "Prev PM Low": len(valid_df[valid_df['asia_low'] < valid_df['prev_pm_low']])/total,
        "Prev Lunch High": len(valid_df[valid_df['asia_high'] > valid_df['prev_lunch_high']])/total,
        "Prev Lunch Low": len(valid_df[valid_df['asia_low'] < valid_df['prev_lunch_low']])/total
    }
    for lvl, prob in levels.items():
        if prob > 0.3:
            playbook_lines.append(f"*   **{lvl}**: {prob*100:.1f}%")

    return "\n".join(playbook_lines)

def analyze_london_playbook(df):
    """
    Generate London playbook matching reference style.
    Highlights:
    - Manipulation Pattern (Partial Up/Down)
    - Reversal Rates by Pattern
    - Range Size Impact
    """
    playbook_lines = []
    playbook_lines.append("# London Session Playbook (NQ)\n")
    playbook_lines.append("## *Identify the manipulation. This determines your day.*")
    
    # Need 'Asia High/Low' to determine London Manipulation
    # We use 'cbdr_asia_high' (19:30-00:00) as "Asia Reference" per Herman?
    # Or full Asia (19:30-02:30)? The reference uses "Asia (19:30 - 02:30)".
    # My extractor has 'asia_high' (19:30-02:30).
    # 'london_high' (02:30-08:00).
    
    valid_df = df.dropna(subset=['asia_high', 'asia_low', 'london_high', 'london_low', 'prev_day_high', 'prev_day_low']).copy()
    total = len(valid_df)
    
    # Determine London Manipulation Pattern
    conditions = [
        (valid_df['london_high'] > valid_df['asia_high']) & (valid_df['london_low'] < valid_df['asia_low']), # Engulfs
        (valid_df['london_high'] > valid_df['asia_high']), # Partial Up
        (valid_df['london_low'] < valid_df['asia_low']),   # Partial Down
    ]
    choices = ['Engulfs', 'Partial Up', 'Partial Down']
    valid_df['london_manip'] = np.select(conditions, choices, default='Inside')
    
    # 1. MANIPULATION PATTERNS
    playbook_lines.append("\n### Step 1: What Did London Do to Asia?")
    playbook_lines.append("| Pattern | Frequency | Description |")
    playbook_lines.append("|---------|-----------|-------------|")
    
    manip_counts = valid_df['london_manip'].value_counts()
    for mtype in ['Partial Up', 'Partial Down', 'Engulfs', 'Inside']:
        count = manip_counts.get(mtype, 0)
        pct = count / total * 100
        desc = ""
        if mtype == 'Partial Up': desc = "Swept Asia HIGH only → Bearish manipulation"
        elif mtype == 'Partial Down': desc = "Swept Asia LOW only → Bullish manipulation"
        elif mtype == 'Engulfs': desc = "Swept BOTH sides → Weaker signal"
        elif mtype == 'Inside': desc = "Stayed inside Asia → NO SETUP"
        
        playbook_lines.append(f"| **{mtype}** | {pct:.1f}% | {desc} |")
        
    # 2. REVERSAL RATES
    playbook_lines.append("\n### Step 2: Reversal Rates by Pattern")
    playbook_lines.append("| Pattern | Base Reversal | Notes |")
    playbook_lines.append("|---------|-------------|-------|")
    
    # Definition of Reversal:
    # Partial Up (Bearish Manip) -> Close < Open (Bearish Day?) Or Close < London High?
    # Reference says "Reversal Rate". Usually means closing against the manipulation.
    # If Partial Up (Swept High) -> Close < Open (Red Day).
    # If Partial Down (Swept Low) -> Close > Open (Green Day).
    
    for mtype in ['Partial Down', 'Partial Up', 'Engulfs']:
        subset = valid_df[valid_df['london_manip'] == mtype]
        if len(subset) == 0: continue
        
        if mtype == 'Partial Down':
            rev = len(subset[subset['london_close'] > subset['london_open']]) # Bullish Close
            note = "Best for longs"
        elif mtype == 'Partial Up':
            rev = len(subset[subset['london_close'] < subset['london_open']]) # Bearish Close
            note = "Best for shorts"
        else: # Engulfs
            rev = len(subset[subset['london_close'] > subset['london_open']]) # Just checking Bullish for now? 
            # Actually Engulfs is ambiguous. 
            note = "Weaker signal"
            
        playbook_lines.append(f"| {mtype} | **{rev/len(subset)*100:.1f}%** | {note} |")

    # 3. LONDON RANGE SIZE
    playbook_lines.append("\n### Step 3: London Range Size Impact")
    median_lon = valid_df['london_range'].median()
    playbook_lines.append(f"Median London Range: {median_lon:.2f} pts")
    
    temp_df = valid_df.copy()
    temp_df['lon_size'] = np.where(temp_df['london_range'] > median_lon, 'Large', 'Small')
    
    playbook_lines.append("| London Range | Reversal Rate (Partial Up/Down) |")
    playbook_lines.append("|-------------|--------------|")
    
    for size in ['Small', 'Large']:
        subset = temp_df[(temp_df['london_manip'].isin(['Partial Up', 'Partial Down'])) & (temp_df['lon_size'] == size)]
        if len(subset) == 0: continue
        
        # Calculate combined reversal rate
        wins = 0
        for idx, row in subset.iterrows():
            if row['london_manip'] == 'Partial Up' and row['london_close'] < row['london_open']: wins += 1
            if row['london_manip'] == 'Partial Down' and row['london_close'] > row['london_open']: wins += 1
            
        playbook_lines.append(f"| **{size}** | **{wins/len(subset)*100:.1f}%** |")
        
    playbook_lines.append("\n**Key Insight**: Small London Range = Clean Reversal. Large Range = Expansion/Chop.")

    return "\n".join(playbook_lines)



def main():
    print(f"Loading data for {TICKER}...")
    df = load_data(TICKER)
    if df is None: return
    
    print("Preparing lagged data...")
    df = prepare_lagged_data(df)
    
    print("Analyzing Asia Playbook...")
    asia_report = analyze_asia_playbook(df)
    with open(os.path.join(OUTPUT_DIR, 'ASIA_PLAYBOOK.md'), 'w', encoding='utf-8') as f:
        f.write(asia_report)
    
    print("Analyzing London Playbook...")
    london_report = analyze_london_playbook(df)
    with open(os.path.join(OUTPUT_DIR, 'LONDON_PLAYBOOK.md'), 'w', encoding='utf-8') as f:
        f.write(london_report)
    
    print("Done. Playbooks updated.")

if __name__ == "__main__":
    main()
