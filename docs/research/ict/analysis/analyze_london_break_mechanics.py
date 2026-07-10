import json
import pandas as pd
import numpy as np
import os
import sys
from datetime import timedelta

# Add parent dir
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def analyze_london_break_mechanics():
    # Paths
    parquet_path = r"c:\Users\vinay\tvDownloadOHLC\data\NQ1_1m.parquet"
    profiler_path = r"c:\Users\vinay\tvDownloadOHLC\data\NQ1_profiler.json"
    
    if not os.path.exists(parquet_path) or not os.path.exists(profiler_path):
        print("Data files not found.")
        return

    print("1. Loading Data...")
    
    # --- PROFILER (London High/Low & NY1 Outcome) ---
    with open(profiler_path, 'r') as f:
        p_data = json.load(f)
    
    df_p = pd.DataFrame(p_data)
    df_p['date_str'] = pd.to_datetime(df_p['date']).dt.strftime('%Y-%m-%d')
    
    daily_data = {}
    
    # London Stats
    lon_sessions = df_p[df_p['session'] == 'London']
    for _, row in lon_sessions.iterrows():
        d = row['date_str']
        if d not in daily_data: daily_data[d] = {}
        daily_data[d]['Lon_High'] = row['range_high']
        daily_data[d]['Lon_Low'] = row['range_low']
        
    # NY1 Outcome
    def get_ny1_dir(status):
        if status in ['Long True', 'Short False']: return "UP"
        if status in ['Short True', 'Long False']: return "DOWN"
        return "NEUTRAL"

    ny1_sessions = df_p[df_p['session'].isin(['NY AM', 'NY1'])]
    for _, row in ny1_sessions.iterrows():
        d = row['date_str']
        if d in daily_data:
            daily_data[d]['NY1_Outcome'] = get_ny1_dir(row['status'])
            
    print(f"Daily Records Loaded: {len(daily_data)}")

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
    
    # Filter 1m data to only NY1 Session Times (09:30 - 12:00)
    # We want to check if/when London High/Low is broken.
    
    df_1m['date_str'] = df_1m.index.strftime('%Y-%m-%d')
    df_1m['time_str'] = df_1m.index.strftime('%H:%M')
    
    # Filter for NY1 Hours (09:30 to 12:00)
    # Actually just 09:30 to 12:00
    mask_ny1 = (
        (df_1m.index.hour == 9) & (df_1m.index.minute >= 30) |
        (df_1m.index.hour == 10) |
        (df_1m.index.hour == 11) |
        (df_1m.index.hour == 12) & (df_1m.index.minute == 0)
    )
    df_ny1_candles = df_1m[mask_ny1]
    
    print("2. Analyzing Break Mechanics...")
    
    results = []
    
    grouped = df_ny1_candles.groupby('date_str')
    
    for date_str, group in grouped:
        if date_str not in daily_data: continue
        rec = daily_data[date_str]
        
        lon_high = rec.get('Lon_High')
        lon_low = rec.get('Lon_Low')
        outcome = rec.get('NY1_Outcome')
        
        if not lon_high or not lon_low or not outcome: continue
        
        # Check Breaks
        # Did we break High?
        high_breaks = group[group['high'] > lon_high]
        low_breaks = group[group['low'] < lon_low]
        
        # Classify High Break
        if len(high_breaks) > 0:
            # Check for Close
            # Did ANY candle CLOSE above High?
            closes_above = group[group['close'] > lon_high]  # 1-min Close
            
            # 5-min Close?
            # Approximation: check every 5th minute?
            # Or assume 1-min close is "Close"
            
            # Let's categorize:
            # Type 1: Wick Only (Sweep) - High > Level but Close < Level (ALL occurrences?)
            # Type 2: Candle Close - High > Level and Close > Level
            
            # Simple check:
            if len(closes_above) > 0:
                break_type = "CLOSE"
            else:
                break_type = "SWEEP"
                
            results.append({
                'Date': date_str,
                'Break_Dir': 'UP', # Broke London High
                'Type': break_type,
                'NY1_Outcome': outcome
            })
            
        # Classify Low Break
        if len(low_breaks) > 0:
            closes_below = group[group['close'] < lon_low]
            
            if len(closes_below) > 0:
                break_type = "CLOSE"
            else:
                break_type = "SWEEP"
                
            results.append({
                'Date': date_str,
                'Break_Dir': 'DOWN', # Broke London Low
                'Type': break_type,
                'NY1_Outcome': outcome
            })

    df_res = pd.DataFrame(results)
    print(f"Total Breaks Analyzed: {len(df_res)}")
    
    # --- 3. PROBABILITIES ---
    
    print("\n--- BREAK MECHANICS ANALYSIS (NY1 Session) ---")
    
    # Overall Break Success (Baseline)
    # If High Broken -> Outcome UP? (Trend)
    # If Low Broken -> Outcome DOWN? (Trend)
    
    def get_trend_prob(subset, break_dir):
        if len(subset) == 0: return 0
        target = "UP" if break_dir == "UP" else "DOWN"
        return subset['NY1_Outcome'].value_counts(normalize=True).get(target, 0) * 100

    # UP BREAKS
    up_subset = df_res[df_res['Break_Dir'] == 'UP']
    up_base_prob = get_trend_prob(up_subset, 'UP')
    print(f"\n[UP BREAKS] (Lon High Taken) n={len(up_subset)}")
    print(f"  Base Trend Probability: {up_base_prob:.1f}%")
    
    # Split by Type
    up_sweep = up_subset[up_subset['Type'] == 'SWEEP']
    up_close = up_subset[up_subset['Type'] == 'CLOSE']
    
    print(f"  -> SWEEP Only (n={len(up_sweep)}): Trend Prob: {get_trend_prob(up_sweep, 'UP'):.1f}% (Reversal: {100-get_trend_prob(up_sweep, 'UP'):.1f}%)")
    print(f"  -> CANDLE CLOSE (n={len(up_close)}): Trend Prob: {get_trend_prob(up_close, 'UP'):.1f}%")

    # DOWN BREAKS
    dn_subset = df_res[df_res['Break_Dir'] == 'DOWN']
    dn_base_prob = get_trend_prob(dn_subset, 'DOWN')
    print(f"\n[DOWN BREAKS] (Lon Low Taken) n={len(dn_subset)}")
    print(f"  Base Trend Probability: {dn_base_prob:.1f}%")
    
    # Split by Type
    dn_sweep = dn_subset[dn_subset['Type'] == 'SWEEP']
    dn_close = dn_subset[dn_subset['Type'] == 'CLOSE']
    
    print(f"  -> SWEEP Only (n={len(dn_sweep)}): Trend Prob: {get_trend_prob(dn_sweep, 'DOWN'):.1f}% (Reversal: {100-get_trend_prob(dn_sweep, 'DOWN'):.1f}%)")
    print(f"  -> CANDLE CLOSE (n={len(dn_close)}): Trend Prob: {get_trend_prob(dn_close, 'DOWN'):.1f}%")
    
    # Conclusion
    print("\n[CONCLUSION]")
    if get_trend_prob(up_sweep, 'UP') < 40 and get_trend_prob(dn_sweep, 'DOWN') < 40:
        print("  >> SWEEPS are high probability Reversals.")
    if get_trend_prob(up_close, 'UP') > 55 or get_trend_prob(dn_close, 'DOWN') > 55:
        print("  >> CLOSES confirm Trend.")
    else:
        print("  >> CLOSES are still coin flips.")

if __name__ == "__main__":
    analyze_london_break_mechanics()
