import pandas as pd
import json
import os
import numpy as np

def analyze_probabilities(ticker="NQ1"):
    # 1. Load RTH Classifications
    class_path = f"c:/Users/vinay/tvDownloadOHLC/data/derived/{ticker}_daily_classification.parquet"
    if not os.path.exists(class_path):
        print(f"Error: Classification file not found at {class_path}")
        return
    
    df_class = pd.read_parquet(class_path, columns=['date', 'type'])
    df_class['date'] = pd.to_datetime(df_class['date']).dt.date
    
    # 2. Load Session Profiler Data
    profiler_path = f"c:/Users/vinay/tvDownloadOHLC/data/{ticker}_profiler.json"
    if not os.path.exists(profiler_path):
        print(f"Error: Profiler file not found at {profiler_path}")
        return
        
    with open(profiler_path, 'r') as f:
        profiler_data = json.load(f)
    
    df_prof = pd.DataFrame(profiler_data)
    df_prof['date'] = pd.to_datetime(df_prof['date']).dt.date
    
    # 3. Process Asia and London Interaction
    # Filter for relevant sessions
    df_asia = df_prof[df_prof['session'] == 'Asia'].copy()
    df_london = df_prof[df_prof['session'] == 'London'].copy()
    
    # Merge on date to compare timestamps
    df_sessions = pd.merge(
        df_asia, 
        df_london, 
        on='date', 
        how='inner', # We need both to analyze interaction
        suffixes=('_asia', '_london')
    )
    
    # Vectorized check: Asia Broken in London?
    if not df_sessions.empty:
        # Check if Asia's broken_ts falls within London's start and end time
        df_sessions['asia_broken_in_london'] = (
            (~df_sessions['broken_ts_asia'].isna()) & 
            (df_sessions['broken_ts_asia'] >= df_sessions['start_ts_london']) & 
            (df_sessions['broken_ts_asia'] <= df_sessions['end_ts_london'])
        )
    else:
        df_sessions['asia_broken_in_london'] = False
    
    # Format Statuses (Lowercase)
    df_sessions['status_asia'] = df_sessions['status_asia'].str.lower()
    df_sessions['status_london'] = df_sessions['status_london'].str.lower()
    
    # Create Composite Key
    df_sessions['overnight_key'] = (
        df_sessions['status_asia'] + " | " + 
        df_sessions['status_london'] + " | " + 
        "LdnBreak:" + df_sessions['asia_broken_in_london'].astype(str)
    )
    
    # --- SCENARIO MAPPING (Vectorized) ---
    bulls = [('long true', 'short false'), ('long true', 'long true'), 
             ('short false', 'short false'), ('short false', 'long true')]
    bears = [('long false', 'short true'), ('long false', 'long false'), 
             ('short true', 'long false'), ('short true', 'short true')]
    contradicting = [('long true', 'short true'), ('long true', 'long false'), 
                    ('long false', 'long true'), ('long false', 'short false'), 
                    ('short true', 'long true'), ('short true', 'short false'), 
                    ('short false', 'long false'), ('short false', 'short true')]

    # Vectorized mapping using zip + isin
    pair_index = pd.MultiIndex.from_arrays([df_sessions['status_asia'], df_sessions['status_london']])
    
    df_sessions['scenario'] = "Neutral/Other"
    df_sessions.loc[pair_index.isin(bulls), 'scenario'] = "Bullish"
    df_sessions.loc[pair_index.isin(bears), 'scenario'] = "Bearish"
    df_sessions.loc[pair_index.isin(contradicting), 'scenario'] = "Contradicting"

    # 4. Merge with Daily Classification
    df_merged = pd.merge(
        df_sessions[['date', 'overnight_key', 'status_asia', 'status_london', 'asia_broken_in_london', 'scenario']], 
        df_class[['date', 'type']], 
        on='date',
        how='inner'
    )
    
    # 5. Analysis & Calculation
    # A. By Key
    totals = df_merged.groupby('overnight_key').size()
    counts = df_merged.groupby(['overnight_key', 'type']).size().unstack(fill_value=0)
    probs = (counts.div(totals, axis=0) * 100).round(1)
    
    df_results = pd.DataFrame(index=counts.index)
    df_results['n'] = totals
    # Restore scenario for the key-based df so we can group output later
    # Map key to scenario (taking unique value since key implies scenario)
    key_to_scenario = df_merged.groupby('overnight_key')['scenario'].first()
    df_results['scenario'] = key_to_scenario
    
    df_results['most_likely'] = counts.idxmax(axis=1)
    
    all_classes = ['R1', 'R2', 'DWP', 'DNP']
    for cls in all_classes:
        if cls in probs.columns:
            df_results[f"{cls}%"] = probs[cls]
        else:
            df_results[f"{cls}%"] = 0.0
            
    # B. By Scenario (Aggregate)
    scen_totals = df_merged.groupby('scenario').size()
    scen_counts = df_merged.groupby(['scenario', 'type']).size().unstack(fill_value=0)
    scen_probs = (scen_counts.div(scen_totals, axis=0) * 100).round(1)
    
    df_scen = pd.DataFrame(index=scen_counts.index)
    df_scen['n'] = scen_totals
    df_scen['most_likely'] = scen_counts.idxmax(axis=1)
    for cls in all_classes:
        if cls in scen_probs.columns:
            df_scen[f"{cls}%"] = scen_probs[cls]
        else:
            df_scen[f"{cls}%"] = 0.0
            
    # Sort alphabetically
    df_results = df_results.sort_index()
    
    # 6. Outputs
    
    # A) CSV Export
    output_dir = "c:/Users/vinay/tvDownloadOHLC/docs/DailyClassification"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    csv_path = f"{output_dir}/{ticker}_overnight_probability_matrix.csv"
    df_results.to_csv(csv_path)
    print(f"\n[SUCCESS] CSV Matrix saved to: {csv_path}")

    # B) Generate Consolidated Markdown Report
    md_path = f"{output_dir}/{ticker}_OVERNIGHT_PROBABILITIES.md"
    
    with open(md_path, 'w') as f:
        f.write(f"# {ticker} Overnight Classification Probability Matrix\n\n")
        f.write("This document analyzes the correlation between overnight session outcomes and the final Daily Classification (R1, R2, DWP, DNP).\n\n")
        
        # Methodology
        f.write("## Methodology\n")
        f.write(f"- **Data Source**: {len(df_merged)} trading sessions of {ticker} history.\n")
        f.write("- **Grouping**: Sessions grouped into **Bullish**, **Bearish**, and **Contradicting** based on Asia/London alignment.\n")
        f.write("- **Asia Broken in London**: Logic specifically checks if the **Asia Session Mid-Point** was broken *during* the **London Session** timeframe (02:30 – 03:30 ET).\n\n")
        
        # 1. Aggregate Scenario Analysis
        f.write("## 1. Aggregate Scenario Analysis\n")
        f.write("Do 'Bullish' overnight sessions actually lead to Bullish RTH days?\n\n")
        
        header = "| Scenario | n | Most Likely | " + " | ".join([f"{c}%" for c in all_classes]) + " |"
        separator = "| :--- | :--- | :--- | " + " | ".join([":---" for _ in all_classes]) + " |"
        f.write(header + "\n")
        f.write(separator + "\n")
        
        # Sort custom order: Bullish, Bearish, Contradicting, Neutral/Other
        custom_order = ["Bullish", "Bearish", "Contradicting", "Neutral/Other"]
        # Filter to only existing scenarios
        existing = [s for s in custom_order if s in df_scen.index]
        
        for scen in existing:
            row = df_scen.loc[scen]
            pct_str = " | ".join([str(row[f'{c}%']) for c in all_classes])
            f.write(f"| **{scen}** | {row['n']} | {row['most_likely']} | {pct_str} |\n")
        
        f.write("\n")

        # 2. Trend Day Analysis (DWP + DNP)
        f.write("## 2. Trend Day Analysis (DWP + DNP)\n")
        f.write("Which specific setups have the highest probability of a generic 'Trend Day' (Either DWP or DNP)?\n\n")
        
        # Calculate Trend% (DWP% + DNP%)
        df_results['Trend%'] = df_results['DWP%'] + df_results['DNP%']
        trend_setups = df_results[df_results['n'] >= 10].sort_values('Trend%', ascending=False).head(10)
        
        f.write("| Setup (Asia \\| London \\| Broken) | Trend% (DWP+DNP) | DWP% | DNP% | n |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- |\n")
        
        for idx, row in trend_setups.iterrows():
            key_clean = idx.replace(" | ", " \\| ").replace("LdnBreak:", "Brk:")
            f.write(f"| {key_clean} | **{row['Trend%']}%** | {row['DWP%']}% | {row['DNP%']}% | {row['n']} |\n")

        f.write("\n> [!TIP]\n")
        f.write("> **Trend Insight**: failed breakouts (Broken:True) often convert into DWP Trend Days as the market retraces deep but holds the trend direction.\n\n")

        # 3. Independent Analysis (Other Insights)
        f.write("## 3. Top High-Probability Setups (Other Insights)\n")
        f.write("Setups with >40% probability for specific outcomes.\n\n")
        
        significant = df_results[df_results['n'] >= 10].copy()
        
        # Helper to print table
        def print_insight_table(label, target_class, threshold=40.0):
            f.write(f"### {label} (>{int(threshold)}% {target_class})\n")
            # Safe checking if column exists (it should, but robust)
            if f"{target_class}%" not in significant.columns: return
            
            matches = significant[significant[f"{target_class}%"] >= threshold].sort_values(f"{target_class}%", ascending=False)
            
            if matches.empty:
                f.write("_No setups met the threshold._\n\n")
                return

            f.write("| Setup (Asia \\| London) | Broken? | Prob % | n |\n")
            f.write("| :--- | :--- | :--- | :--- |\n")
            
            for idx, row in matches.iterrows():
                parts = idx.split(" | ")
                asia_london = f"{parts[0]} \\| {parts[1]}"
                broken_status = "Yes" if "True" in parts[2] else "No"
                prob = row[f"{target_class}%"]
                f.write(f"| {asia_london} | {broken_status} | **{prob}%** | {row['n']} |\n")
            f.write("\n")

        print_insight_table("Trend Killers / Range Days", "R1")
        print_insight_table("Clean Trend Runners", "DNP", threshold=30.0) # Lower threshold for rare DNP
        print_insight_table("Reversion / Deep Pullback", "DWP")
        print_insight_table("Range Extensions", "R2")

        # 4. Exhaustive Matrix (Grouped by Scenario)
        f.write("## 4. Exhaustive Probability Matrix (By Scenario)\n")
        
        for scen in existing:
            f.write(f"### {scen} Scenarios\n")
            subset = df_results[df_results['scenario'] == scen]
            
            header = "| Overnight Key | n | Most Likely | " + " | ".join([f"{c}%" for c in all_classes]) + " |"
            separator = "| :--- | :--- | :--- | " + " | ".join([":---" for _ in all_classes]) + " |"
            
            f.write(header + "\n")
            f.write(separator + "\n")
            
            for idx, row in subset.iterrows():
                key_clean = idx.replace(" | ", " \\| ").replace("LdnBreak:", "Broken:")
                pct_str = " | ".join([str(row[f'{c}%']) for c in all_classes])
                f.write(f"| {key_clean} | {row['n']} | {row['most_likely']} | {pct_str} |\n")
            f.write("\n")
            
    print(f"[SUCCESS] Markdown Report saved to: {md_path}")

import sys
if __name__ == "__main__":
    ticker_arg = sys.argv[1] if len(sys.argv) > 1 else "NQ1"
    analyze_probabilities(ticker_arg)
