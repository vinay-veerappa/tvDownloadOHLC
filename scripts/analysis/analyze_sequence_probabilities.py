import pandas as pd
import os
import numpy as np

def analyze_sequences(ticker="NQ1"):
    # 1. Load RTH Classifications
    class_path = f"c:/Users/vinay/tvDownloadOHLC/data/derived/{ticker}_daily_classification.parquet"
    if not os.path.exists(class_path):
        print(f"Error: Classification file not found at {class_path}")
        return
    
    df = pd.read_parquet(class_path)
    df = df.sort_values('date').reset_index(drop=True)
    
    # 2. Feature Engineering: Lags
    # Create lag columns for previous days
    for i in range(1, 4): # Look back up to 3 days for sequence building
        df[f'prev_{i}'] = df['type'].shift(i)
        
    df = df.dropna().copy()
    
    all_classes = ['R1', 'R2', 'DWP', 'DNP']

    # --- ANALYSIS 1: 1-Day Transition Matrix (P(Today | Prev_1)) ---
    print("\n### 1. Daily Transition Matrix (P(Today | Yesterday))")
    print("If Yesterday was X, what is the probability of Today being Y?")
    
    trans_counts = df.groupby(['prev_1', 'type']).size().unstack(fill_value=0)
    trans_totals = df.groupby('prev_1').size()
    trans_probs = (trans_counts.div(trans_totals, axis=0) * 100).round(1)
    
    # Format Output
    print(f"\n| Yesterday \\ Today | R1% | R2% | DWP% | DNP% | n |")
    print("| :--- | :--- | :--- | :--- | :--- | :--- |")
    for idx, row in trans_probs.iterrows():
        n = trans_totals.loc[idx]
        pcts = " | ".join([f"**{row.get(c, 0.0)}%**" for c in all_classes])
        print(f"| **{idx}** | {pcts} | {n} |")

    # --- ANALYSIS 2: 3-Day Sequences ---
    print("\n### 2. Common 3-Day Patterns")
    print("Most frequent sequences of 3 days and what usually follows on Day 4.")
    
    # Create sequence string: Prev_2 -> Prev_1 -> Today
    df['seq_3'] = df['prev_2'] + " -> " + df['prev_1'] + " -> " + df['type']
    
    seq_counts = df['seq_3'].value_counts().head(10)
    
    # Calculate Day 4 outcome for top sequences
    # We need a Day 4 target (Next Day) implies we shift 'type' backwards or just look forward from the seq
    # Let's shift 'type' -1 to get 'next_day' aligned with current row
    df['next_day'] = df['type'].shift(-1)
    
    print(f"\n| 3-Day Sequence | n | Next Day (Day 4) Probabilities |")
    print("| :--- | :--- | :--- |")
    
    for seq, count in seq_counts.items():
        # Get subset where this sequence happened
        subset = df[df['seq_3'] == seq]
        
        # Count outcomes for next day
        outcomes = subset['next_day'].value_counts(normalize=True) * 100
        
        # Get top outcome
        if not outcomes.empty:
            top_outcome = outcomes.idxmax()
            top_prob = outcomes.max()
            outcome_str = f"**{top_outcome}** ({top_prob:.1f}%)"
            
            # Secondary check for strong runners
            avg_str = ", ".join([f"{idx}={val:.0f}%" for idx, val in outcomes.items() if val > 20])
        else:
            avg_str = "N/A"
            
        print(f"| {seq} | {count} | {avg_str} |")

    # --- ANALYSIS 3: Streak Analysis ---
    print("\n### 3. Streak Analysis")
    print("Does the probability change after N consecutive days of the same type?")
    
    for cls in all_classes:
        # Identify streaks
        # Create a boolean mask for the class
        is_cls = df['type'] == cls
        
        # Group consecutively
        # Trick: Cumsum of inequality gives group IDs
        groups = (is_cls != is_cls.shift()).cumsum()
        
        # Filter for rows where it IS the class
        streak_df = df[is_cls].groupby(groups).cumcount() + 1
        
        # Assign back to original DF (non-matching will be NaN)
        df[f'{cls}_streak'] = np.nan
        df.loc[is_cls, f'{cls}_streak'] = streak_df.values
        
        # Analyze outcome AFTER streak of 2, 3
        # We need to look at the day *after* a streak of length N matches
        # So look at rows where streak == N, and check 'next_day'
        
        for length in [2, 3]:
            # Get days where the streak reached 'length'
            # Note: A streak of 3 implies day 1, day 2, and day 3 were all CLS.
            # We want to know what happened on day 4.
            # So we check rows where streak == length AND next_day is valid
            subset = df[(df[f'{cls}_streak'] == length) & (df['next_day'].notna())]
            
            if len(subset) > 5: # Min sample size
                next_counts = subset['next_day'].value_counts(normalize=True) * 100
                top = next_counts.idxmax()
                top_prob = next_counts.max()
                
                # Check for Mean Reversion (Not CLS) vs Continuation (Is CLS)
                continuation = next_counts.get(cls, 0.0)
                mean_reversion = 100.0 - continuation
                
                print(f"After {length}x **{cls}**: n={len(subset)} -> Next Day: {top} ({top_prob:.1f}%) | Continuation: {continuation:.1f}%")

    # --- OUTPUT to Markdown ---
    output_dir = "c:/Users/vinay/tvDownloadOHLC/docs/DailyClassification"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    md_path = f"{output_dir}/{ticker}_SEQUENCE_PROBABILITIES.md"
    
    with open(md_path, 'w') as f:
        f.write(f"# {ticker} Sequential Classification Analysis\n\n")
        f.write("This document analyzes the probability of today's Daily Classification (R1, R2, DWP, DNP) based on previous day sequences.\n\n")
        
        # 1. Transition Matrix
        f.write("## 1. Daily Transition Matrix (P(Today | Yesterday))\n")
        f.write("If Yesterday was X, what is the probability of Today being Y?\n\n")
        
        f.write("| Yesterday \\ Today | R1% | R2% | DWP% | DNP% | n |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- | :--- |\n")
        
        for idx, row in trans_probs.iterrows():
            n = trans_totals.loc[idx]
            pcts = " | ".join([f"**{row.get(c, 0.0)}%**" for c in all_classes])
            f.write(f"| **{idx}** | {pcts} | {n} |\n")
        f.write("\n")

        # 2. 3-Day Sequences
        f.write("## 2. Common 3-Day Patterns\n")
        f.write("Most frequent sequences of 3 days and what usually follows on Day 4.\n\n")
        f.write("| 3-Day Sequence | n | Next Day (Day 4) Probabilities |\n")
        f.write("| :--- | :--- | :--- |\n")
        
        # Recalculate for loop inside writing context
        for seq, count in seq_counts.items():
            subset = df[df['seq_3'] == seq]
            outcomes = subset['next_day'].value_counts(normalize=True) * 100
            if not outcomes.empty:
                avg_str = ", ".join([f"**{idx}**={val:.0f}%" for idx, val in outcomes.items() if val > 20])
            else:
                avg_str = "N/A"
            f.write(f"| {seq} | {count} | {avg_str} |\n")
        f.write("\n")

        # 3. Streak Analysis
        f.write("## 3. Streak Analysis\n")
        f.write("Does the probability change after N consecutive days of the same type?\n\n")
        
        # Streak logic needs to run before writing, assuming it's done above.
        # We need to capture the print output logic into the file.
        # Let's re-run the loop logic here to print to file.
        
        for cls in all_classes:
            # Re-calculating streak logic or reusing df if existing logic populated it
            # The original code populated df[f'{cls}_streak']
            pass # assumed populated
            
            for length in [2, 3]:
                if f'{cls}_streak' not in df.columns: continue
                subset = df[(df[f'{cls}_streak'] == length) & (df['next_day'].notna())]
                
                if len(subset) > 5:
                    next_counts = subset['next_day'].value_counts(normalize=True) * 100
                    top = next_counts.idxmax()
                    top_prob = next_counts.max()
                    continuation = next_counts.get(cls, 0.0)
                    
                    f.write(f"- After {length}x **{cls}** (n={len(subset)}): **{top} ({top_prob:.1f}%)** | Continuation: {continuation:.1f}%\n")
                    
    print(f"\n[SUCCESS] Markdown Report saved to {md_path}")
    
    # Save CSV as backup
    csv_path = f"{output_dir}/{ticker}_sequential_probabilities.csv"
    trans_probs.to_csv(csv_path)

import sys
if __name__ == "__main__":
    ticker_arg = sys.argv[1] if len(sys.argv) > 1 else "NQ1"
    analyze_sequences(ticker_arg)
