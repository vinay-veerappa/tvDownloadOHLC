
import pandas as pd
import numpy as np
import json
import os

def analyze_key_levels(ticker="NQ1"):
    print(f"--- Starting Key Level Analysis for {ticker} (Session Breakdown) ---")
    
    # 1. Load Data
    base_dir = "c:/Users/vinay/tvDownloadOHLC/data"
    parquet_path = f"{base_dir}/{ticker}_1m.parquet"
    sessions_path = f"{base_dir}/sessions/{ticker}_sessions.json"
    
    if not os.path.exists(parquet_path) or not os.path.exists(sessions_path):
        print("Error: Missing data files.")
        return

    print(f"Loading 1m Data: {parquet_path}")
    df_1m = pd.read_parquet(parquet_path)
    
    # Ensure Index
    if not isinstance(df_1m.index, pd.DatetimeIndex):
        df_1m.index = pd.to_datetime(df_1m['datetime']) 
        
    try:
        df_1m.index = df_1m.index.tz_localize('UTC').tz_convert('US/Eastern')
    except TypeError:
        df_1m.index = df_1m.index.tz_convert('US/Eastern')
        
    df_1m['date'] = df_1m.index.date
    # Minute of day for filtering: 0 = 00:00, 570 = 09:30, 720 = 12:00, 960 = 16:00
    df_1m['mod'] = df_1m.index.hour * 60 + df_1m.index.minute
    
    # 2. Extract Session Stats (High/Low per window)
    
    # A. London/Pre (00:00 to 09:29)
    # Note: Asia is usually defined ending earlier, but for "Pre-NY", we check everything before open.
    # User asked: "If Asia 1 MM is hit in London then it does not matter"
    print("Extracting Session Data...")
    
    pre_mask = (df_1m['mod'] >= 0) & (df_1m['mod'] < 570)
    pre_stats = df_1m[pre_mask].groupby('date').agg({'high':'max', 'low':'min'}).rename(columns={'high':'Pre_High', 'low':'Pre_Low'})
    
    # B. NY AM (09:30 to 11:59)
    am_mask = (df_1m['mod'] >= 570) & (df_1m['mod'] < 720)
    am_stats = df_1m[am_mask].groupby('date').agg({'high':'max', 'low':'min'}).rename(columns={'high':'AM_High', 'low':'AM_Low'})
    
    # C. NY PM (12:00 to 15:59)
    pm_mask = (df_1m['mod'] >= 720) & (df_1m['mod'] < 960)
    pm_stats = df_1m[pm_mask].groupby('date').agg({'high':'max', 'low':'min'}).rename(columns={'high':'PM_High', 'low':'PM_Low'})
    
    # D. Full RTH (09:30 to 16:00) for context
    rth_mask = (df_1m['mod'] >= 570) & (df_1m['mod'] < 960)
    rth_stats = df_1m[rth_mask].groupby('date').agg({'open':'first'}).rename(columns={'open':'RTH_Open'})
    
    # E. Midnight Open
    midnight_mask = (df_1m.index.hour == 0) & (df_1m.index.minute == 0)
    midnight_opens = df_1m[midnight_mask].groupby('date')['open'].first().rename("Midnight_Open")
    
    # 3. Load & Merge Session Levels
    print(f"Loading Sessions: {sessions_path}")
    with open(sessions_path, 'r') as f:
        sess_data = json.load(f)
    df_sess = pd.DataFrame(sess_data)
    
    relevant = ['Asia', 'London', 'Open730']
    df_sess_filt = df_sess[df_sess['session'].isin(relevant)]
    pivoted = df_sess_filt.pivot_table(index='date', columns='session', values=['high', 'low', 'mid', 'price'], aggfunc='first')
    pivoted.columns = [f"{c[0]}_{c[1]}" for c in pivoted.columns]
    pivoted.index = pd.to_datetime(pivoted.index).date
    
    # Merge Sequence
    # Outer merge? No, we need dates with RTH data.
    df = pd.merge(rth_stats, midnight_opens, left_index=True, right_index=True, how='inner')
    df = pd.merge(df, pre_stats, left_index=True, right_index=True, how='left') # Pre stats might be missing if data starts mid-day?
    df = pd.merge(df, am_stats, left_index=True, right_index=True, how='left')
    df = pd.merge(df, pm_stats, left_index=True, right_index=True, how='left')
    df = pd.merge(df, pivoted, left_index=True, right_index=True, how='inner')
    
    # Fill missing session highs/lows with NaNs or handle logic?
    # If Pre_High is NaN, it means no data before 9:30.
    
    print("\n--- DEBUG: Session Stats ---")
    print(df[['Pre_High', 'AM_High', 'PM_High']].head())
    print("----------------------------\n")
    
    # 4. Feature Engineering
    df['Asia_Range'] = df['high_Asia'] - df['low_Asia']
    extensions = [1.0, 1.5, 2.0, 2.5]
    
    for ext in extensions:
        clean_ext = str(ext).replace('.', '')
        df[f'Ext_Up_{clean_ext}'] = df['high_Asia'] + (df['Asia_Range'] * ext)
        df[f'Ext_Down_{clean_ext}'] = df['low_Asia'] - (df['Asia_Range'] * ext)
        
    levels = {
        'Midnight Open': 'Midnight_Open',
        '07:30 Open': 'price_Open730', 
        'London Mid': 'mid_London',
        'Asia 1.0 Up': 'Ext_Up_10',
        'Asia 1.0 Down': 'Ext_Down_10',
        'Asia 1.5 Up': 'Ext_Up_15',
        'Asia 1.5 Down': 'Ext_Down_15',
        'Asia 2.0 Up': 'Ext_Up_20',
        'Asia 2.0 Down': 'Ext_Down_20',
        'Asia 2.5 Up': 'Ext_Up_25',
        'Asia 2.5 Down': 'Ext_Down_25'
    }
    
    # 5. Calculate Conditional Hit Rates
    print("\n## Part 9: Conditional Hit Rates (NY Fresh vs Stale)")
    print(f"Sample Size: {len(df)} Days")
    
    results = []
    
    for name, col in levels.items():
        if col not in df.columns: continue
        
        # Base Set: Valid Levels
        valid = df[col].notna()
        subset = df[valid].copy()
        
        target = subset[col]
        
        # 1. Was it hit in Pre-Market (London)?
        # Hit if Pre_Low <= Target <= Pre_High
        hit_pre = (subset['Pre_Low'] <= target) & (subset['Pre_High'] >= target)
        
        # 2. Was it hit in NY AM?
        hit_am = (subset['AM_Low'] <= target) & (subset['AM_High'] >= target)
        
        # 3. Was it hit in NY PM?
        hit_pm = (subset['PM_Low'] <= target) & (subset['PM_High'] >= target)
        
        # METRICS
        
        # A. Already Hit (Stale) Rate
        stale_rate = hit_pre.mean() * 100
        
        # B. Fresh Hit Rate (NY AM)
        # Condition: NOT hit in Pre, but Hit in AM
        fresh_am_hits = hit_am & (~hit_pre)
        # Denominator: All days where it was NOT hit in Pre
        not_hit_pre_mask = ~hit_pre
        if not_hit_pre_mask.sum() > 0:
            fresh_am_rate = fresh_am_hits[not_hit_pre_mask].mean() * 100
        else:
            fresh_am_rate = 0.0
            
        # C. Late Hit Rate (NY PM)
        # Condition: NOT hit in Pre AND NOT hit in AM, but Hit in PM
        fresh_pm_hits = hit_pm & (~hit_pre) & (~hit_am)
        not_hit_am_mask = (~hit_pre) & (~hit_am)
        if not_hit_am_mask.sum() > 0:
            fresh_pm_rate = fresh_pm_hits[not_hit_am_mask].mean() * 100
        else:
            fresh_pm_rate = 0.0
            
        results.append({
            'Level': name,
            'Hit in London %': stale_rate,
            'Fresh Hit NY AM %': fresh_am_rate,
            'Fresh Hit NY PM %': fresh_pm_rate
        })
        
    res_df = pd.DataFrame(results)
    # Format nice columns
    cols = ['Level', 'Hit in London %', 'Fresh Hit NY AM %', 'Fresh Hit NY PM %']
    print(res_df[cols].round(1).to_string(index=False))
    
    # 6. Specific Extension Logic (Directional)
    # Only check Up targets if Open > Asia High
    print("\n### Directional Fresh Hits (Trend Expansion)")
    
    for ext in extensions:
        clean = str(ext).replace('.', '')
        u_col = f'Ext_Up_{clean}'
        d_col = f'Ext_Down_{clean}'
        
        # UP
        if u_col in df.columns:
            # Filter: Open > Asia High
            bull_days = df[df['RTH_Open'] > df['high_Asia']].copy()
            if len(bull_days) > 0:
                t = bull_days[u_col]
                # Hit Pre?
                h_pre = (bull_days['Pre_High'] >= t) # Simply High >= Target for Up ext
                # Hit AM?
                h_am = (bull_days['AM_High'] >= t)
                
                fresh_am = h_am & (~h_pre)
                denom = (~h_pre).sum()
                
                rate = (fresh_am.sum() / denom * 100) if denom > 0 else 0
                print(f"Open > Asia High -> {ext}x Up: {rate:.1f}% Fresh Hit in AM (London Hit: {(h_pre.mean()*100):.1f}%)")

        # DOWN
        if d_col in df.columns:
            bear_days = df[df['RTH_Open'] < df['low_Asia']].copy()
            if len(bear_days) > 0:
                t = bear_days[d_col]
                h_pre = (bear_days['Pre_Low'] <= t)
                h_am = (bear_days['AM_Low'] <= t)
                
                fresh_am = h_am & (~h_pre)
                denom = (~h_pre).sum()
                
                rate = (fresh_am.sum() / denom * 100) if denom > 0 else 0
                print(f"Open < Asia Low  -> {ext}x Down: {rate:.1f}% Fresh Hit in AM (London Hit: {(h_pre.mean()*100):.1f}%)")

if __name__ == "__main__":
    analyze_key_levels("NQ1")
