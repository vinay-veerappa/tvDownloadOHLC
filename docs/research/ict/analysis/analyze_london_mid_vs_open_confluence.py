import json
import pandas as pd
import numpy as np
import os
import sys
from datetime import timedelta

# Add parent dir
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def analyze_confluence():
    # Paths
    parquet_path = r"c:\Users\vinay\tvDownloadOHLC\data\NQ1_1m.parquet"
    profiler_path = r"c:\Users\vinay\tvDownloadOHLC\data\NQ1_profiler.json"
    
    if not os.path.exists(parquet_path) or not os.path.exists(profiler_path):
        print("Data files not found.")
        return

    print("1. Loading Data for Confluence Analysis...")
    
    # --- PROFILER (London Mid & Outcome) ---
    with open(profiler_path, 'r') as f:
        p_data = json.load(f)
    
    df_p = pd.DataFrame(p_data)
    df_p['date_str'] = pd.to_datetime(df_p['date']).dt.strftime('%Y-%m-%d')
    
    daily_data = {}
    
    def get_ny1_dir(status):
        if status in ['Long True', 'Short False']: return "UP"
        if status in ['Short True', 'Long False']: return "DOWN"
        return "NEUTRAL"
        
    # Outcome Map
    ny1_sessions = df_p[df_p['session'].isin(['NY AM', 'NY1'])]
    for _, row in ny1_sessions.iterrows():
        daily_data[row['date_str']] = {'NY1_Outcome': get_ny1_dir(row['status'])}
        
    # London Mid Map
    lon_sessions = df_p[df_p['session'] == 'London']
    for _, row in lon_sessions.iterrows():
        d = row['date_str']
        if d in daily_data:
            daily_data[d]['London_Mid'] = row['mid']
            
    # --- 1M DATA ---
    print(f"Loading {parquet_path}...")
    df_1m = pd.read_parquet(parquet_path)
    
    # Timezone Handling (Vectorized)
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
    df_1m = df_1m.set_index('datetime')
    df_1m = df_1m.sort_index()
    
    # Create Helper Columns
    df_1m['hour'] = df_1m.index.hour
    df_1m['minute'] = df_1m.index.minute
    df_1m['date'] = df_1m.index.date
    
    # --- EXTRACT PRICES ---
    print("2. Extracting Prices...")
    
    # 1. Midnight Open (00:00)
    df_midnight = df_1m[df_1m['hour'] == 0].groupby('date').first()['open'].rename('Midnight_Open')
    
    # 2. Globex Open (18:00 prev day) - approximated by shifting dates if contiguous
    # Let's use loop for precision? No, too slow.
    # Shift approach: Get 18:00 prices. Shift index to next trading day day.
    df_globex_raw = df_1m[df_1m['hour'] == 18].groupby('date').first()['open']
    df_globex_shifted = df_globex_raw.copy()
    df_globex_shifted.index = df_globex_shifted.index + timedelta(days=1) 
    # (Note: Fridays will shift to Saturdays, need to map to Mondays. But merge handles intersection)
    df_globex_shifted.name = 'Globex_Open'
    
    # 3. Price at 10:00 AM (Confirmation Time)
    df_10am = df_1m[df_1m['hour'] == 10].groupby('date').first()['open'].rename('Price_10am')
    
    # --- MERGE ---
    # Merge on Date Index
    df_levels = pd.concat([df_midnight, df_10am], axis=1)
    
    # Join Outcomes & London Mid
    # Convert index to str
    df_levels.index = df_levels.index.astype(str)
    
    # Convert daily_data to DF
    df_daily = pd.DataFrame.from_dict(daily_data, orient='index')
    
    # Combine
    df_final = df_levels.join(df_daily)
    
    # Add Globex separately because of date shift
    df_globex_shifted.index = df_globex_shifted.index.astype(str)
    df_final = df_final.join(df_globex_shifted)
    
    df_final = df_final.dropna(inplace=False)
    print(f"Total Combined Days: {len(df_final)}")
    
    # --- ANALYSIS ---
    # Condition: 
    # Price(10am) > London Mid (Trend Signal)
    
    # Case 1: Alone
    # Case 2: + Above Midnight Open
    # Case 3: + Above Globex Open
    # Case 4: + Above Both
    
    print("\n--- BASELINE: London Mid Signal (at 10:00) ---")
    
    # Condition: Bullish Signal
    cond_lm_bull = df_final['Price_10am'] > df_final['London_Mid']
    cond_lm_bear = df_final['Price_10am'] < df_final['London_Mid']
    
    def get_win_rate(subset, direction):
        if len(subset) == 0: return 0
        return subset['NY1_Outcome'].value_counts(normalize=True).get(direction, 0) * 100
        
    base_bull_wr = get_win_rate(df_final[cond_lm_bull], 'UP')
    base_bear_wr = get_win_rate(df_final[cond_lm_bear], 'DOWN')
    avg_base = (base_bull_wr + base_bear_wr) / 2
    
    print(f"London Mid Alone (Win Rate): {avg_base:.1f}% (Bull: {base_bull_wr:.1f}, Bear: {base_bear_wr:.1f})")
    
    print("\n--- CONFLUENCE: London Mid + Midnight Open ---")
    
    # Bullish Confluence: Price > LM AND Price > Midnight
    cond_conf_bull_mid = (cond_lm_bull) & (df_final['Price_10am'] > df_final['Midnight_Open'])
    conf_bull_mid_wr = get_win_rate(df_final[cond_conf_bull_mid], 'UP')
    
    # Bearish Confluence: Price < LM AND Price < Midnight
    cond_conf_bear_mid = (cond_lm_bear) & (df_final['Price_10am'] < df_final['Midnight_Open'])
    conf_bear_mid_wr = get_win_rate(df_final[cond_conf_bear_mid], 'DOWN')
    
    avg_conf_mid = (conf_bull_mid_wr + conf_bear_mid_wr) / 2
    print(f"LM + Midnight Open (Win Rate): {avg_conf_mid:.1f}% (Diff: {avg_conf_mid - avg_base:+.1f}%)")
    
    print("\n--- CONFLUENCE: London Mid + Globex Open ---")
    
    cond_conf_bull_glo = (cond_lm_bull) & (df_final['Price_10am'] > df_final['Globex_Open'])
    conf_bull_glo_wr = get_win_rate(df_final[cond_conf_bull_glo], 'UP')
    
    cond_conf_bear_glo = (cond_lm_bear) & (df_final['Price_10am'] < df_final['Globex_Open'])
    conf_bear_glo_wr = get_win_rate(df_final[cond_conf_bear_glo], 'DOWN')
    
    avg_conf_glo = (conf_bull_glo_wr + conf_bear_glo_wr) / 2
    print(f"LM + Globex Open (Win Rate): {avg_conf_glo:.1f}% (Diff: {avg_conf_glo - avg_base:+.1f}%)")
    
    print("\n--- CONFLUENCE: London Mid + BOTH ---")
    
    cond_conf_bull_all = (cond_conf_bull_mid) & (cond_conf_bull_glo)
    conf_bull_all_wr = get_win_rate(df_final[cond_conf_bull_all], 'UP')
    
    cond_conf_bear_all = (cond_conf_bear_mid) & (cond_conf_bear_glo)
    conf_bear_all_wr = get_win_rate(df_final[cond_conf_bear_all], 'DOWN')
    
    avg_conf_all = (conf_bull_all_wr + conf_bear_all_wr) / 2
    print(f"LM + BOTH (Win Rate): {avg_conf_all:.1f}% (Diff: {avg_conf_all - avg_base:+.1f}%)")

if __name__ == "__main__":
    analyze_confluence()