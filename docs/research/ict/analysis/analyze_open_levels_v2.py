import json
import pandas as pd
import numpy as np
import os
import sys
from datetime import timedelta

# Add parent dir
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def analyze_open_levels_v2():
    # Paths
    parquet_path = r"c:\Users\vinay\tvDownloadOHLC\data\NQ1_1m.parquet"
    profiler_path = r"c:\Users\vinay\tvDownloadOHLC\data\NQ1_profiler.json"
    
    if not os.path.exists(parquet_path) or not os.path.exists(profiler_path):
        print("Data files not found.")
        return

    print("1. Loading Data...")
    
    # --- PROFILER ---
    with open(profiler_path, 'r') as f:
        p_data = json.load(f)
    
    df_p = pd.DataFrame(p_data)
    df_p['date_str'] = pd.to_datetime(df_p['date']).dt.strftime('%Y-%m-%d')
    
    # Extract Outcomes
    def get_dir(status):
        if status in ['Long True', 'Short False']: return "UP"
        if status in ['Short True', 'Long False']: return "DOWN"
        return "NEUTRAL"
    
    df_outcomes = df_p.pivot(index='date_str', columns='session', values='status')
    
    # We want London Outcome and NY1 Outcome
    # Rename columns and Map Direction
    if 'London' in df_outcomes.columns:
        df_outcomes['London_Outcome'] = df_outcomes['London'].apply(get_dir)
    if 'NY AM' in df_outcomes.columns:
        df_outcomes['NY1_Outcome'] = df_outcomes['NY AM'].apply(get_dir)
    elif 'NY1' in df_outcomes.columns:
        df_outcomes['NY1_Outcome'] = df_outcomes['NY1'].apply(get_dir)
        
    # --- 1M DATA ---
    print(f"Loading {parquet_path}...")
    df_1m = pd.read_parquet(parquet_path)
    
    # Timezone Handling
    if 'time' in df_1m.columns:
        df_1m['datetime'] = pd.to_datetime(df_1m['time'], unit='s', utc=True)
    elif 'datetime' in df_1m.index.names:
         df_1m['datetime'] = df_1m.index
         if df_1m['datetime'].dt.tz is None:
             df_1m['datetime'] = df_1m['datetime'].dt.tz_localize('UTC')
    else:
        df_1m['datetime'] = df_1m.index
        if df_1m['datetime'].dt.tz is None:
             df_1m['datetime'] = df_1m['datetime'].dt.tz_localize('UTC')

    print("Converting to US/Eastern...")
    df_1m['datetime'] = df_1m['datetime'].dt.tz_convert('US/Eastern')
    df_1m.set_index('datetime', inplace=True)
    df_1m.sort_index(inplace=True)
    
    # --- EXTRACT LEVELS VECTORIZED ---
    print("2. Extracting Levels (Vectorized)...")
    
    # Create Columns for Hour/Minute
    df_1m['hour'] = df_1m.index.hour
    df_1m['minute'] = df_1m.index.minute
    df_1m['date'] = df_1m.index.date
    
    # Midnight Open (00:00)
    # We take the first candle where hour=0
    df_midnight = df_1m[df_1m['hour'] == 0].groupby('date').first()['open'].rename('Midnight_Open')
    
    # Globex Open (18:00 previous day)
    # We take candle at 18:00. This belongs to the NEXT trading day date.
    # So if index is 2023-01-01 18:00, it belongs to trading day 2023-01-02 (if weekday).
    # Actually, simplistic approach: 
    # Get all 18:00 opens. Shift their date + 1 day?
    # Weekends complicate this. Friday 18:00? No, Sunday 18:00 is Monday open.
    # Let's just create a 'TradingDate' column? 
    # Or just grab 18:00 candles, shift index by +1 Day (approx), then re-align.
    
    df_globex_raw = df_1m[df_1m['hour'] == 18].groupby('date').first()['open']
    # Vectorized check: which date does this 18:00 belong to?
    # Usually next valid day.
    # Let's assume +1 day for now.
    
    # Better approach: Iterate dates in `df_midnight` (valid trading days) and lookback.
    # But for speed, let's try shifting.
    df_globex = df_globex_raw.copy()
    df_globex.index = df_globex.index + timedelta(days=1)
    # Handle Weekend Gap (Friday 18:00 -> Saturday? No market.)
    # Sunday 18:00 -> Monday. (Sunday+1 = Monday). Correct.
    df_globex.name = 'Globex_Open'
    
    # London Check (03:00)
    df_london = df_1m[df_1m['hour'] == 3].groupby('date').first()['open'].rename('London_Check_Price')
    
    # NY1 Check (09:30)
    df_ny1 = df_1m[(df_1m['hour'] == 9) & (df_1m['minute'] == 30)].groupby('date').first()['open'].rename('NY1_Check_Price')
    
    # --- MERGE ALL ---
    # Merge on Date
    df_levels = pd.concat([df_midnight, df_london, df_ny1], axis=1)
    
    # Merge Globex (careful with alignment)
    # df_levels = df_levels.join(df_globex, how='left') 
    # Since indices are objects (dates), join works.
    # But `df_globex` index is date.
    
    # Convert index to string for merging with Profiler
    df_levels.index = df_levels.index.astype(str)
    
    # Merge Globex with string index
    df_globex.index = df_globex.index.astype(str)
    df_levels = df_levels.join(df_globex)
    
    # Merge Outcomes
    df_final = df_levels.join(df_outcomes[['London_Outcome', 'NY1_Outcome']])
    df_final.dropna(inplace=True)
    
    print(f"Total Correlation Points: {len(df_final)}")
    
    # --- 3. ANALYZE ---
        
    def analyze_session(name, outcome_col, price_col):
        print(f"\n=== {name} SESSION ANALYSIS ===")
        subset = df_final.copy()
        
        # Vs Midnight
        subset['Vs_Midnight'] = np.where(subset[price_col] > subset['Midnight_Open'], 'ABOVE', 'BELOW')
        
        print("\n[Midnight Open Correlation]")
        for pos in ['ABOVE', 'BELOW']:
            sub = subset[subset['Vs_Midnight'] == pos]
            if len(sub) == 0: continue
            up = sub[outcome_col].value_counts(normalize=True).get('UP', 0) * 100
            dn = sub[outcome_col].value_counts(normalize=True).get('DOWN', 0) * 100
            print(f"  Price {pos} Midnight Open (n={len(sub)}):")
            print(f"    -> Bullish: {up:.1f}%")
            print(f"    -> Bearish: {dn:.1f}%")
            
        # Vs Globex
        subset['Vs_Globex'] = np.where(subset[price_col] > subset['Globex_Open'], 'ABOVE', 'BELOW')
        
        print("\n[Globex Open Correlation]")
        for pos in ['ABOVE', 'BELOW']:
            sub = subset[subset['Vs_Globex'] == pos]
            if len(sub) == 0: continue
            up = sub[outcome_col].value_counts(normalize=True).get('UP', 0) * 100
            dn = sub[outcome_col].value_counts(normalize=True).get('DOWN', 0) * 100
            print(f"  Price {pos} Globex Open (n={len(sub)}):")
            print(f"    -> Bullish: {up:.1f}%")
            print(f"    -> Bearish: {dn:.1f}%")
            
        # Combined
        print("\n[Combined Confluence]")
        # ABOVE BOTH
        sub_all_above = subset[(subset['Vs_Midnight']=='ABOVE') & (subset['Vs_Globex']=='ABOVE')]
        if len(sub_all_above) > 0:
            rate = sub_all_above[outcome_col].value_counts(normalize=True).get('UP', 0) * 100
            print(f"  ABOVE BOTH (n={len(sub_all_above)}): -> Bullish: {rate:.1f}%")
            
        # BELOW BOTH
        sub_all_below = subset[(subset['Vs_Midnight']=='BELOW') & (subset['Vs_Globex']=='BELOW')]
        if len(sub_all_below) > 0:
            rate = sub_all_below[outcome_col].value_counts(normalize=True).get('DOWN', 0) * 100
            print(f"  BELOW BOTH (n={len(sub_all_below)}): -> Bearish: {rate:.1f}%")

    analyze_session('London', 'London_Outcome', 'London_Check_Price')
    analyze_session('NY1', 'NY1_Outcome', 'NY1_Check_Price')

if __name__ == "__main__":
    analyze_open_levels_v2()
