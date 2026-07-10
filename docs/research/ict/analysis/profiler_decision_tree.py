import json
import pandas as pd
import numpy as np
import os
import sys

# Add parent dir
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def run_decision_tree_analysis():
    profiler_path = r"c:\Users\vinay\tvDownloadOHLC\data\NQ1_profiler.json"
    research_path = r"c:\Users\vinay\tvDownloadOHLC\ict_research\data\trading_days_enhanced_NQ.csv"
    
    if not os.path.exists(profiler_path):
        print("Profiler JSON not found.")
        return

    print("1. Loading Profiler Data...")
    with open(profiler_path, 'r') as f:
        p_data = json.load(f)
    
    # Convert to DataFrame
    df_p = pd.DataFrame(p_data)
    
    # Filter for relevant sessions
    # Sessions: 1=Asia, 2=London, 3=NY AM (NY1), 4=Lunch, 5=NY PM
    # Let's check unique session names/ids
    sessions = df_p['session'].unique()
    print(f"Sessions found: {sessions}")
    
    # We need to pivot.
    # Pivot key: date
    # Columns to keep: status, range_high - range_low (Range), broken
    
    # Calculate Range
    df_p['range_size'] = df_p['range_high'] - df_p['range_low']
    
    # Normalize Date (ensure YYYY-MM-DD)
    df_p['date_str'] = pd.to_datetime(df_p['date']).dt.strftime('%Y-%m-%d')
    
    # Pivot Manual
    # We want: Asia_Status, Asia_Range, Asia_Broken
    #          London_Status, London_Range, London_Broken
    #          NY_AM_Status (Target)
    
    daily_records = {}
    
    print("2. Pivoting Data...")
    for _, row in df_p.iterrows():
        d = row['date_str']
        s = row['session']
        
        if d not in daily_records: daily_records[d] = {}
        
        prefix = ""
        if s == "Asia": prefix = "Asia"
        elif s == "London": prefix = "London"
        elif s == "NY1": prefix = "NY_AM"
        elif s == "NY2": prefix = "NY_PM"
        else: continue
        
        daily_records[d][f"{prefix}_Status"] = row['status']
        daily_records[d][f"{prefix}_Range"] = row['range_size']
        daily_records[d][f"{prefix}_Broken"] = row['broken']
        
    analysis_df = pd.DataFrame.from_dict(daily_records, orient='index')
    analysis_df.index.name = 'date'
    analysis_df = analysis_df.reset_index(inplace=False)
    
    # Filter for full days (must have Asia, London, NY_AM)
    analysis_df = analysis_df.dropna(subset=['Asia_Status', 'London_Status', 'NY_AM_Status'])
    
    # Add Range Quartiles (Small, Med, Large)
    # We calculate quartiles based on the entire dataset
    
    for sess in ['Asia', 'London']:
        analysis_df[f'{sess}_Range_Q'] = pd.qcut(analysis_df[f'{sess}_Range'], q=3, labels=["Small", "Med", "Large"])
        
    # --------------------------------------------------------------------------
    # 3. Decision Tree Logic
    # --------------------------------------------------------------------------
    # Target: NY_AM_Status is "True" (Long True / Short True) vs "False" (Long False / Short False)
    # Or "Trending" vs "Reversing"
    
    def classify_target(status):
        if status in ['Long True', 'Short True']: return "TREND"
        if status in ['Long False', 'Short False']: return "REVERSAL"
        if status == 'None': return "RANGE"
        return "OTHER"
        
    analysis_df['NY1_Type'] = analysis_df['NY_AM_Status'].apply(classify_target)
    
    # We only care about predicting Trend (True) vs Reversal (False)
    valid_df = analysis_df[analysis_df['NY1_Type'].isin(['TREND', 'REVERSAL'])].copy()
    
    print("\n--- BASELINE: NY1 OUTCOME ---")
    print(valid_df['NY1_Type'].value_counts(normalize=True))
    
    # --------------------------------------------------------------------------
    # 4. Generate Hints / Decision Nodes
    # --------------------------------------------------------------------------
    # Factor 1: Broken Mids
    # Does breaking Asia Mid imply Reversal?
    
    print("\n--- FACTOR 1: ASIA/LONDON BROKEN STATUS ---")
    # Define a combined state: Asia_Broken + London_Broken
    valid_df['Broken_State'] = "Asia:" + valid_df['Asia_Broken'].astype(str) + " | Lon:" + valid_df['London_Broken'].astype(str)
    
    print(valid_df.groupby('Broken_State')['NY1_Type'].value_counts(normalize=True).unstack().fillna(0) * 100)
    
    # Factor 2: Session Combinations (Asia Status + London Status)
    # Does Asia LT + London LT -> NY LT?
    
    print("\n--- FACTOR 2: SESSION STATUS COMBO ---")
    valid_df['Combo'] = valid_df['Asia_Status'] + " -> " + valid_df['London_Status']
    
    # Show top 10 combos with strong Trend bias (>70%)
    combo_stats = valid_df.groupby('Combo')['NY1_Type'].value_counts(normalize=True).unstack().fillna(0)
    print("\nTop Trend Predictors (High Probability of 'True' Outcome):")
    print(combo_stats[combo_stats['TREND'] > 0.65].sort_values('TREND', ascending=False) * 100)
    
    print("\nTop Reversal Predictors (High Probability of 'False' Outcome):")
    print(combo_stats[combo_stats['REVERSAL'] > 0.65].sort_values('REVERSAL', ascending=False) * 100)
    
    # Factor 3: Range Sizing Impact
    # Does a Large London Range mean Reversal in NY?
    print("\n--- FACTOR 3: LONDON RANGE SIZE ---")
    print(valid_df.groupby('London_Range_Q', observed=False)['NY1_Type'].value_counts(normalize=True).unstack().fillna(0) * 100)

if __name__ == "__main__":
    run_decision_tree_analysis()