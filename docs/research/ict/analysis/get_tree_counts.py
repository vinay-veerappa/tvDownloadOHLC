import json
import pandas as pd
import os
import sys

def get_tree_counts():
    profiler_path = r"c:\Users\vinay\tvDownloadOHLC\data\NQ1_profiler.json"
    
    if not os.path.exists(profiler_path):
        print("Profiler JSON not found.")
        return

    with open(profiler_path, 'r') as f:
        p_data = json.load(f)
    
    df_p = pd.DataFrame(p_data)
    
    # Pivot to get daily sessions
    df_p['date_str'] = pd.to_datetime(df_p['date']).dt.strftime('%Y-%m-%d')
    daily_records = {}
    
    for _, row in df_p.iterrows():
        d = row['date_str']
        s = row['session']
        if d not in daily_records: daily_records[d] = {}
        
        prefix = ""
        if s == "Asia": prefix = "Asia"
        elif s == "London": prefix = "London"
        else: continue
        
        daily_records[d][f"{prefix}_Status"] = row['status']
        daily_records[d][f"{prefix}_Range"] = row['range_high'] - row['range_low']

    df = pd.DataFrame.from_dict(daily_records, orient='index')
    df = df.dropna(subset=['Asia_Status', 'London_Status'])
    
    total_days = len(df)
    print(f"Total Days Analyzed: {total_days}")
    
    # Tree A: Expansion Reversal (Opposing Trends)
    # Asia LT -> Lon ST OR Asia ST -> Lon LT
    tree_a = df[
        ((df['Asia_Status'] == 'Long True') & (df['London_Status'] == 'Short True')) |
        ((df['Asia_Status'] == 'Short True') & (df['London_Status'] == 'Long True'))
    ]
    print(f"\nTREE A (Expansion Reversal): {len(tree_a)} occurrences ({len(tree_a)/total_days*100:.1f}%)")
    
    # Tree B: Double Failure (Same Direction Failure)
    # Asia LF -> Lon LF OR Asia SF -> Lon SF
    tree_b = df[
        ((df['Asia_Status'] == 'Long False') & (df['London_Status'] == 'Long False')) |
        ((df['Asia_Status'] == 'Short False') & (df['London_Status'] == 'Short False'))
    ]
    print(f"TREE B (Double Failure): {len(tree_b)} occurrences ({len(tree_b)/total_days*100:.1f}%)")
    
    # Tree C: Inside Trap (Asia Inside -> Lon Breakout)
    # Asia None -> Lon LT OR Asia None -> Lon ST
    tree_c = df[
        (df['Asia_Status'].isin(['None', 'Inside'])) & 
        (df['London_Status'].isin(['Long True', 'Short True']))
    ]
    print(f"TREE C (Inside Trap): {len(tree_c)} occurrences ({len(tree_c)/total_days*100:.1f}%)")

    # Tree D: Continuation (Same Trend) - Just for context
    # Asia LT -> Lon LT OR Asia ST -> Lon ST
    tree_d = df[
        ((df['Asia_Status'] == 'Long True') & (df['London_Status'] == 'Long True')) |
        ((df['Asia_Status'] == 'Short True') & (df['London_Status'] == 'Short True'))
    ]
    print(f"TREE D (Continuation): {len(tree_d)} occurrences ({len(tree_d)/total_days*100:.1f}%)")

if __name__ == "__main__":
    get_tree_counts()
