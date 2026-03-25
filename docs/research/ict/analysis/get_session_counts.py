import json
import pandas as pd
import os
import sys

def get_session_counts():
    profiler_path = r"c:\Users\vinay\tvDownloadOHLC\data\NQ1_profiler.json"
    
    if not os.path.exists(profiler_path):
        print("Profiler JSON not found.")
        return

    print("Loading Profiler Data...")
    with open(profiler_path, 'r') as f:
        p_data = json.load(f)
    
    df_p = pd.DataFrame(p_data)
    
    # Filter for Asia and London sessions
    asia_df = df_p[df_p['session'] == 'Asia']
    london_df = df_p[df_p['session'] == 'London']
    
    print("\n--- ASIA SESSION COUNTS ---")
    asia_counts = asia_df['status'].value_counts()
    asia_pct = asia_df['status'].value_counts(normalize=True) * 100
    
    asia_stats = pd.DataFrame({'Count': asia_counts, 'Percent': asia_pct})
    print(asia_stats.round(1))
    print(f"Total Asia Sessions: {len(asia_df)}")

    print("\n--- LONDON SESSION COUNTS ---")
    lon_counts = london_df['status'].value_counts()
    lon_pct = london_df['status'].value_counts(normalize=True) * 100
    
    lon_stats = pd.DataFrame({'Count': lon_counts, 'Percent': lon_pct})
    print(lon_stats.round(1))
    print(f"Total London Sessions: {len(london_df)}")

if __name__ == "__main__":
    get_session_counts()
