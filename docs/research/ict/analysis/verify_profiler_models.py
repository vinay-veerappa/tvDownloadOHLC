import json
import pandas as pd
import numpy as np
import os
import sys

# Add parent dir
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def analyze_session_continuation():
    profiler_path = r"c:\Users\vinay\tvDownloadOHLC\data\NQ1_profiler.json"
    
    if not os.path.exists(profiler_path):
        print("Profiler JSON not found.")
        return

    print("1. Loading Profiler Data...")
    with open(profiler_path, 'r') as f:
        p_data = json.load(f)
    
    df_p = pd.DataFrame(p_data)
    df_p['date_str'] = pd.to_datetime(df_p['date']).dt.strftime('%Y-%m-%d')
    
    # 2. Pivot Data
    daily_records = {}
    print("2. Processing Sessions...")
    
    for _, row in df_p.iterrows():
        d = row['date_str']
        s = row['session']
        if d not in daily_records: daily_records[d] = {}
        
        prefix = ""
        if s == "Asia": prefix = "Asia"
        elif s == "London": prefix = "London"
        elif s == "NY AM" or s == "NY1": prefix = "NY"
        else: continue
        
        daily_records[d][f"{prefix}_Status"] = row['status']
        daily_records[d][f"{prefix}_Range"] = row['range_high'] - row['range_low']

    df = pd.DataFrame.from_dict(daily_records, orient='index')
    df = df.dropna(subset=['Asia_Status', 'London_Status', 'NY_Status'])
    
    # 3. Define Directional Bias
    def get_direction(status):
        if status == 'Long True': return "UP"
        if status == 'Short True': return "DOWN"
        # For False statuses, the *resultant* move is the reversal
        if status == 'Long False': return "DOWN" # Broke High then Low -> Bearish result
        if status == 'Short False': return "UP"  # Broke Low then High -> Bullish result
        return "NEUTRAL"

    # Define Structural Intent (Initial Break) - distinct from Resultant Direction
    # This helps see if we are following the *breakout* or the *result*
    def get_initial_break(status):
        if 'Long' in status: return "UP"
        if 'Short' in status: return "DOWN"
        return "NEUTRAL"

    # Apply classifications
    df['Asia_Dir'] = df['Asia_Status'].apply(get_direction)
    df['Lon_Dir'] = df['London_Status'].apply(get_direction)
    df['NY_Dir'] = df['NY_Status'].apply(get_direction)
    
    # Filter out Neutral London/NY sessions for binary analysis
    valid = df[(df['Lon_Dir'] != "NEUTRAL") & (df['NY_Dir'] != "NEUTRAL")].copy()
    
    # 4. Define Outcome: Trend vs Reversal relative to London
    # Trend = NY Direction matches London Direction
    valid['Outcome'] = np.where(valid['NY_Dir'] == valid['Lon_Dir'], "TREND", "REVERSAL")
    
    print("\n--- GLOBAL BASELINE ---")
    print(valid['Outcome'].value_counts(normalize=True).round(3) * 100)
    
    # 5. Matrix Construction
    # We want: Asia Status + London Status -> Outcome Probability
    
    # Clean statuses for reporting
    valid['Asia_Simple'] = valid['Asia_Status'].replace({'None': 'Inside'})
    valid['Lon_Simple'] = valid['London_Status'].replace({'None': 'Inside'})
    
    # Group by Combination
    valid['Combo'] = valid['Asia_Simple'] + " -> " + valid['Lon_Simple']
    
    stats = valid.groupby(['Asia_Simple', 'Lon_Simple'])['Outcome'].value_counts(normalize=True).unstack().fillna(0) * 100
    stats['Count'] = valid.groupby(['Asia_Simple', 'Lon_Simple'])['Outcome'].count()
    
    # Filter for statistically significant samples (>20 occurrences)
    stats = stats[stats['Count'] > 20].sort_values('TREND', ascending=False)
    
    print("\n--- PRE-MARKET COMBINATION MATRIX (Percent TREND vs REVERSAL) ---")
    print(stats[['TREND', 'REVERSAL', 'Count']].round(1))
    
    # 6. Specific Decision Trees
    
    # Tree 1: When Asia is Trending (LT/ST)
    print("\n--- TREE 1: ASIA TRENDING (LT/ST) ---")
    asia_trend = valid[valid['Asia_Status'].isin(['Long True', 'Short True'])]
    tree1 = asia_trend.groupby('London_Status')['Outcome'].value_counts(normalize=True).unstack().fillna(0) * 100
    print(tree1[['TREND', 'REVERSAL']].round(1))
    
    # Tree 2: When Asia is Reversing (LF/SF)
    print("\n--- TREE 2: ASIA REVERSING (LF/SF) ---")
    asia_rev = valid[valid['Asia_Status'].isin(['Long False', 'Short False'])]
    tree2 = asia_rev.groupby('London_Status')['Outcome'].value_counts(normalize=True).unstack().fillna(0) * 100
    print(tree2[['TREND', 'REVERSAL']].round(1))
    
    # Tree 3: When Asia is Inside
    print("\n--- TREE 3: ASIA CONSTRICTED (INSIDE) ---")
    asia_ins = valid[valid['Asia_Status'] == 'None']
    tree3 = asia_ins.groupby('London_Status')['Outcome'].value_counts(normalize=True).unstack().fillna(0) * 100
    print(tree3[['TREND', 'REVERSAL']].round(1))

    # 7. Range Size Impact on Top Setups
    # Does range size validate the best setups?
    # Best Trend Setup: Asia Inside -> Lon LT (Hypothesis)
    
    print("\n--- RANGE SIZE VALIDATION ---")
    target_setup = valid[(valid['Asia_Simple'] == 'Inside') & (valid['Lon_Simple'] == 'Long True')]
    
    target_setup.loc[:, 'Lon_Range_Q'] = pd.qcut(target_setup['London_Range'], 3, labels=["Small", "Med", "Large"])
    rng_stats = target_setup.groupby('Lon_Range_Q', observed=False)['Outcome'].value_counts(normalize=True).unstack().fillna(0) * 100
    print("Setup: Asia Inside -> London LT (Expect Trend)")
    print(rng_stats[['TREND', 'REVERSAL']].round(1))

if __name__ == "__main__":
    analyze_session_continuation()
