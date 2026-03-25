import json
import pandas as pd
import numpy as np
import os
import sys
from datetime import timedelta

# Add parent dir
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def analyze_open_levels():
    # Paths
    parquet_path = r"c:\Users\vinay\tvDownloadOHLC\data\NQ1_1m.parquet"
    profiler_path = r"c:\Users\vinay\tvDownloadOHLC\data\NQ1_profiler.json"
    
    if not os.path.exists(parquet_path) or not os.path.exists(profiler_path):
        print("Data files not found.")
        return

    print("1. Loading Data...")
    
    # --- LOAD PROFILER (Outcomes) ---
    with open(profiler_path, 'r') as f:
        p_data = json.load(f)
    
    df_p = pd.DataFrame(p_data)
    df_p['date_str'] = pd.to_datetime(df_p['date']).dt.strftime('%Y-%m-%d')
    
    # Organize Outcomes by Date
    daily_outcomes = {}
    
    def get_dir(status):
        if status in ['Long True', 'Short False']: return "UP"
        if status in ['Short True', 'Long False']: return "DOWN"
        return "NEUTRAL"
    
    for _, row in df_p.iterrows():
        d = row['date_str']
        s = row['session']
        if d not in daily_outcomes: daily_outcomes[d] = {}
        
        if s == 'London':
            daily_outcomes[d]['London_Outcome'] = get_dir(row['status'])
        elif s in ['NY AM', 'NY1']:
            daily_outcomes[d]['NY1_Outcome'] = get_dir(row['status'])

    # --- LOAD 1M DATA (Price) ---
    print(f"Loading {parquet_path}...")
    df_1m = pd.read_parquet(parquet_path)
    
    # Timezone Handling (Same as before)
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
             
    # Convert to US/Eastern
    print("Converting to US/Eastern...")
    df_1m['datetime'] = df_1m['datetime'].dt.tz_convert('US/Eastern')
    df_1m.set_index('datetime', inplace=True)
    df_1m.sort_index(inplace=True)
    
    print("2. Extracting Key Levels (Midnight & Globex Open)...")
    
    results = []
    
    # We iterate through the DATES in daily_outcomes
    sorted_dates = sorted(daily_outcomes.keys())
    
    for date_str in sorted_dates:
        current_date = pd.to_datetime(date_str).date()
        outcomes = daily_outcomes[date_str]
        
        # We need data for this day to find Midnight Open (00:00 ET)
        # And data from prev day 18:00 ET for Globex Open
        
        # 1. MIDNIGHT OPEN (00:00 ET on current_date)
        # Define window: 00:00 to 00:05
        # Careful with timezone. current_date is just date.
        # We need localized timestamp.
        
        try:
            # Construct Midnight timestamp (US/Eastern)
            t_midnight = pd.Timestamp(current_date).tz_localize('US/Eastern')
            
            # Construct Globex timestamp (18:00 ET on Prev Day)
            # Need to find prev trading day? Or just prev calendar day?
            # Usually prev calendar day. Monday's Globex Open is Sunday 18:00.
            # If current is Tuesday, Globex is Monday 18:00.
            t_globex = (t_midnight - timedelta(days=1)).replace(hour=18, minute=0)
            
            # Construct Check Times
            t_london = t_midnight.replace(hour=3, minute=0)
            t_ny1 = t_midnight.replace(hour=9, minute=30)
            
            # --- GET OPEN PRICES ---
            
            # Helper to get price
            def get_price_at(ts):
                # Search within 30 mins
                ts_end = ts + timedelta(minutes=30)
                slice = df_1m[ts:ts_end]
                if len(slice) > 0:
                    return slice.iloc[0]['open']
                return None

            midnight_open = get_price_at(t_midnight)
            globex_open = get_price_at(t_globex)
            
            # --- LONDON ANALYSIS ---
            if 'London_Outcome' in outcomes:
                london_check_price = get_price_at(t_london)
                
                if london_check_price and midnight_open and globex_open:
                    res = {
                        'Session': 'London',
                        'Outcome': outcomes['London_Outcome'],
                        'Vs_Midnight': 'ABOVE' if london_check_price > midnight_open else 'BELOW',
                        'Vs_Globex': 'ABOVE' if london_check_price > globex_open else 'BELOW'
                    }
                    results.append(res)
                    
            # --- NY1 ANALYSIS ---
            if 'NY1_Outcome' in outcomes:
                ny1_check_price = get_price_at(t_ny1)
                
                if ny1_check_price and midnight_open and globex_open:
                    res = {
                        'Session': 'NY1',
                        'Outcome': outcomes['NY1_Outcome'],
                        'Vs_Midnight': 'ABOVE' if ny1_check_price > midnight_open else 'BELOW',
                        'Vs_Globex': 'ABOVE' if ny1_check_price > globex_open else 'BELOW'
                    }
                    results.append(res)

        except Exception as e:
            # print(e)
            continue
            
    df_res = pd.DataFrame(results)
    print(f"Total Correlation Points: {len(df_res)}")
    
    # --- 3. CALCULATE PROBABILITIES ---
    
    for session in ['London', 'NY1']:
        print(f"\n=== {session} SESSION ANALYSIS ===")
        subset = df_res[df_res['Session'] == session]
        
        # 1. Midnight Open Correlation
        print("\n[Midnight Open Correlation]")
        for pos in ['ABOVE', 'BELOW']:
            sub_pos = subset[subset['Vs_Midnight'] == pos]
            if len(sub_pos) == 0: continue
            
            # Count Outcomes
            up_rate = sub_pos['Outcome'].value_counts(normalize=True).get('UP', 0) * 100
            dn_rate = sub_pos['Outcome'].value_counts(normalize=True).get('DOWN', 0) * 100
            
            print(f"  Price {pos} Midnight Open (n={len(sub_pos)}):")
            print(f"    -> Bullish ({session} UP): {up_rate:.1f}%")
            print(f"    -> Bearish ({session} DOWN): {dn_rate:.1f}%")

        # 2. Globex Open Correlation
        print("\n[Globex Open Correlation]")
        for pos in ['ABOVE', 'BELOW']:
            sub_pos = subset[subset['Vs_Globex'] == pos]
            if len(sub_pos) == 0: continue
            
            up_rate = sub_pos['Outcome'].value_counts(normalize=True).get('UP', 0) * 100
            dn_rate = sub_pos['Outcome'].value_counts(normalize=True).get('DOWN', 0) * 100
            
            print(f"  Price {pos} Globex Open (n={len(sub_pos)}):")
            print(f"    -> Bullish ({session} UP): {up_rate:.1f}%")
            print(f"    -> Bearish ({session} DOWN): {dn_rate:.1f}%")
            
        # 3. Combined Power
        print("\n[Combined Confluence]")
        # ABOVE BOTH
        sub_all_above = subset[(subset['Vs_Midnight']=='ABOVE') & (subset['Vs_Globex']=='ABOVE')]
        if len(sub_all_above) > 0:
            rate = sub_all_above['Outcome'].value_counts(normalize=True).get('UP', 0) * 100
            print(f"  ABOVE BOTH (n={len(sub_all_above)}): -> Bullish: {rate:.1f}%")
            
        # BELOW BOTH
        sub_all_below = subset[(subset['Vs_Midnight']=='BELOW') & (subset['Vs_Globex']=='BELOW')]
        if len(sub_all_below) > 0:
            rate = sub_all_below['Outcome'].value_counts(normalize=True).get('DOWN', 0) * 100
            print(f"  BELOW BOTH (n={len(sub_all_below)}): -> Bearish: {rate:.1f}%")

        # MIXED
        sub_mixed = subset[subset['Vs_Midnight'] != subset['Vs_Globex']]
        if len(sub_mixed) > 0:
            rate = sub_mixed['Outcome'].value_counts(normalize=True).get('UP', 0) * 100 # Measure Bullishness
            print(f"  MIXED (n={len(sub_mixed)}): -> Bullish: {rate:.1f}% (Random?)")

if __name__ == "__main__":
    analyze_open_levels()
