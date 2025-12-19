
import pandas as pd
import numpy as np
import os

def analyze_es_comprehensive():
    print("Loading ES analysis data...")
    levels_path = 'docs/expected_moves/analysis_data/em_daily_levels_ES.csv'
    overnight_path = 'docs/expected_moves/analysis_data/em_overnight_es.csv'
    
    if not os.path.exists(levels_path):
        print(f"Error: {levels_path} not found.")
        return

    df = pd.read_csv(levels_path)
    
    # Ensure methods are analyzed
    methods = df['method'].unique()
    multiples = df['multiple'].unique()
    
    results = []

    print(f"Analyzing {len(methods)} methods across {len(multiples)} multiples...")

    for method in methods:
        for multiple in multiples:
            # Filter data
            subset = df[(df['method'] == method) & (df['multiple'] == multiple)].copy()
            if subset.empty: continue
            
            total_days = len(subset)
            
            # 1. Containment (Close within levels)
            # Assuming 'close' is the daily close vs 'level_upper'/'level_lower'
            # Note: em_daily_levels_ES.csv has 'close', 'level_upper', 'level_lower'
            
            # Check if columns exist
            if 'close' not in subset.columns: 
                # might be 'es_close' or just 'close' depending on generation script
                # extrapolate_em_to_futures.py drops 'es_close' but might keep 'close' scaled?
                # checking file cols... 
                # extrapolate script: 
                # price_cols = ['prev_close', 'open', 'high', 'low', 'close'...]
                # es_levels[col] = es_levels[col] * es_scale
                pass
            
            # Verify columns
            req_cols = ['high', 'low', 'close', 'level_upper', 'level_lower']
            if not all(col in subset.columns for col in req_cols):
                print(f"Skipping {method} x {multiple}: Missing columns")
                continue

            # Containment Calculation
            # "Contained" usually means High < Upper AND Low > Lower for strict containment?
            # Or Close within? Usually "Close Containment" or "Range Containment".
            # The previous report cited "82.7% Containment". Let's assume Range Containment for "Breach" stats, 
            # but usually EM stats cite "Close Containment". Let's calculate both.
            
            # Close Containment
            close_contained = ((subset['close'] <= subset['level_upper']) & (subset['close'] >= subset['level_lower'])).mean()
            
            # Range Breach (Touch)
            touched_upper = (subset['high'] >= subset['level_upper']).mean()
            touched_lower = (subset['low'] <= subset['level_lower']).mean()
            any_touch = ((subset['high'] >= subset['level_upper']) | (subset['low'] <= subset['level_lower'])).mean()
            
            # Precision / S/R Analysis
            # "Bounce": Touched level but Closed INSIDE
            # "Break": Touched level and Closed OUTSIDE
            
            # Upper Interactions
            upper_touches = subset[subset['high'] >= subset['level_upper']]
            upper_breaks = upper_touches[upper_touches['close'] > upper_touches['level_upper']]
            upper_bounce_rate = 1.0 - (len(upper_breaks) / len(upper_touches)) if len(upper_touches) > 0 else 0
            
            # Lower Interactions
            lower_touches = subset[subset['low'] <= subset['level_lower']]
            lower_breaks = lower_touches[lower_touches['close'] < lower_touches['level_lower']]
            lower_bounce_rate = 1.0 - (len(lower_breaks) / len(lower_touches)) if len(lower_touches) > 0 else 0
            
            # Weighted Average Bounce Rate
            total_touches = len(upper_touches) + len(lower_touches)
            avg_bounce_rate = ((len(upper_touches) * upper_bounce_rate) + (len(lower_touches) * lower_bounce_rate)) / total_touches if total_touches > 0 else 0

            # MFE/MAE (Normalized by EM Value)
            # MFE: Max expansion beyond anchor in direction of trend?
            # Existing report def:
            # MFE: (High - Anchor) / EM
            # MAE: (Anchor - Low) / EM
            # Anchor column needed.
            
            subset['em_val'] = (subset['level_upper'] - subset['level_lower']) / (multiple * 2) if multiple > 0 else 0
            # If multiple is 0, em_val is 0.
            
            if 'anchor' in subset.columns:
                mfe = ((subset['high'] - subset['anchor']) / subset['em_val']).median()
                mae = ((subset['anchor'] - subset['low']) / subset['em_val']).median()
            else:
                mfe = 0
                mae = 0

            results.append({
                'Method': method,
                'Multiple': multiple,
                'Containment_Close': close_contained,
                'Touch_Rate': any_touch,
                'Bounce_Rate': avg_bounce_rate,
                'Median_MFE': mfe,
                'Median_MAE': mae,
                'Total_Days': total_days
            })

    # Sort and rank
    res_df = pd.DataFrame(results)
    res_df.to_csv('docs/expected_moves/analysis_data/es_comprehensive_stats.csv', index=False)
    
    # Generate Markdown Report
    with open('docs/expected_moves/ES_COMPREHENSIVE_ANALYSIS.md', 'w') as f:
        f.write("# ES Futures: Comprehensive Expected Move Analysis\n\n")
        f.write("This document details the performance of Expected Move (EM) levels specifically for **ES Futures**, based on extrapolated settlement data and aligned trading sessions.\n\n")
        
        f.write("## 1. Executive Summary\n\n")
        
        # Best Method at 100% (Standard Deviation)
        best_100 = res_df[res_df['Multiple'] == 1.0].sort_values('Containment_Close', ascending=False).iloc[0]
        f.write(f"**Top Performing Method (1.0x / 100% EM):** {best_100['Method']}\n")
        f.write(f"- Close Containment: **{best_100['Containment_Close']*100:.1f}%**\n")
        f.write(f"- Intraday Touch Rate: **{best_100['Touch_Rate']*100:.1f}%**\n")
        f.write(f"- S/R Bounce Rate: **{best_100['Bounce_Rate']*100:.1f}%** (Probability of holding when tested)\n\n")
        
        f.write("---\n\n")
        
        f.write("## 2. Intraday S/R Analysis (Bounce vs. Break)\n\n")
        f.write("This metric answers: *\"If the level is hit intraday, how likely is it to hold by the close?\"*\n\n")
        f.write("| Method | Multiple | Touch Rate | Bounce Rate (Hold) | Break Rate (Fail) |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- |\n")
        
        # Table of key methods at 1.0x
        key_methods = res_df[res_df['Multiple'] == 1.0].sort_values('Bounce_Rate', ascending=False)
        for _, row in key_methods.iterrows():
            f.write(f"| {row['Method']} | {row['Multiple']}x | {row['Touch_Rate']*100:.1f}% | **{row['Bounce_Rate']*100:.1f}%** | {(1-row['Bounce_Rate'])*100:.1f}% |\n")
            
        f.write("\n> **Trading Insight**: A high Bounce Rate (>60%) suggests the level acts as valid Support/Resistance for fading. A low Bounce Rate (<40%) suggests the level is a breakout trigger.\n\n")

        f.write("---\n\n")

        f.write("## 3. Overnight Session Analysis\n\n")
        # Add Overnight summary if available
        if os.path.exists(overnight_path):
            ov_df = pd.read_csv('docs/expected_moves/analysis_data/em_overnight_summary.csv')
            f.write("Overnight containment of Previous Daily Close Levels:\n\n")
            # Manual Markdown Table
            f.write("| Session | Anchor | Multiple | Containment % | Touch Upper % | Touch Lower % | Median MFE | Median MAE | Samples |\n")
            f.write("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n")
            for _, row in ov_df.iterrows():
                f.write(f"| {row['session']} | {row['anchor']} | {row['multiple']} | {row['containment_pct']}% | {row['touch_upper_pct']}% | {row['touch_lower_pct']}% | {row['median_mfe']} | {row['median_mae']} | {row['sample_size']} |\n")
            f.write("\n\n")
        
        f.write("## 4. Full Performance Data\n\n")
        f.write("| Method | Multiple | Containment (Close) | Median MFE | Median MAE |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- |\n")
        
        # Sort by multiple then method
        full_table = res_df.sort_values(['Multiple', 'Containment_Close'], ascending=[True, False])
        for _, row in full_table.iterrows():
            f.write(f"| {row['Method']} | {row['Multiple']} | {row['Containment_Close']*100:.1f}% | {row['Median_MFE']:.3f} | {row['Median_MAE']:.3f} |\n")

    print("Report generated: docs/expected_moves/ES_COMPREHENSIVE_ANALYSIS.md")

if __name__ == "__main__":
    analyze_es_comprehensive()
