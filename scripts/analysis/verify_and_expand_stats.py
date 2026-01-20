import pandas as pd
import numpy as np
import json
import os
from datetime import datetime

print("GLOBAL START")

def analyze_comprehensive_stats(ticker="NQ1"):
    print(f"--- Starting Master Trader Analysis for {ticker} ---")
    
    # 1. Load Data
    # A. Daily Classification
    class_path = f"c:/Users/vinay/tvDownloadOHLC/data/derived/{ticker}_daily_classification.parquet"
    print(f"Loading Classification: {class_path}")
    if not os.path.exists(class_path):
        print("Error: Daily Classification file not found.")
        return
    df_class = pd.read_parquet(class_path)
    print(f"Loaded Classification: {len(df_class)} rows")
    df_class = pd.read_parquet(class_path)
    df_class['date'] = pd.to_datetime(df_class['date'])
    df_class = df_class.sort_values('date')
    
    # B. Session Profiler
    prof_path = f"c:/Users/vinay/tvDownloadOHLC/data/{ticker}_profiler.json"
    df_prof = pd.DataFrame()
    if os.path.exists(prof_path):
        with open(prof_path, 'r') as f:
            prof_data = json.load(f)
        df_prof = pd.DataFrame(prof_data)
        # Infer date from start_ts (unix) if 'date' column missing or string
        if 'start_ts' in df_prof.columns:
            df_prof['dt'] = pd.to_datetime(df_prof['start_ts'], unit='s', utc=True).dt.tz_convert('America/New_York')
            df_prof['date_str'] = df_prof['dt'].dt.strftime('%Y-%m-%d')
    else:
        print("Warning: Profiler file not found. Session stats will be skipped.")

    # C. VVIX Data
    vvix_path = "C:/Users/vinay/Downloads/VVIX_Daily_OHLC - Sheet1.csv"
    df_vvix = pd.DataFrame()
    if os.path.exists(vvix_path):
        df_vvix = pd.read_csv(vvix_path)
        # Parse Dates "Nov 26, 2025"
        try:
            df_vvix['Date'] = pd.to_datetime(df_vvix['Date'], format='%b %d, %Y')
            df_vvix = df_vvix.sort_values('Date')
        except Exception as e:
            print(f"Error parsing VVIX dates: {e}")
            df_vvix = pd.DataFrame() # Reset on failure
    else:
        print("Warning: VVIX file not found.")

    # --- Helper Function for Distribution ---
    all_classes = ['R1', 'R2', 'DWP', 'DNP']
    def get_dist(df_subset, label):
        total = len(df_subset)
        if total == 0: return
        counts = df_subset['type'].value_counts()
        print(f"\n### {label} (n={total})")
        print("| Type | Count | % |")
        print("| :--- | :--- | :--- |")
        for cls in all_classes:
            c = counts.get(cls, 0)
            p = (c / total) * 100
            print(f"| {cls} | {c} | {p:.1f}% |")

    # --- 2. TIME-BASED ANALYSIS ---
    print("\n## 1. Time-Based Edge")
    
    # A. Day of Week
    df_class['dow'] = df_class['date'].dt.day_name()
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    print("\n### Day of Week Breakdown")
    print("| Day | R1 | R2 | DWP | DNP | Directional (DWP+DNP) |")
    print("| :--- | :--- | :--- | :--- | :--- | :--- |")
    for day in days:
        subset = df_class[df_class['dow'] == day]
        if len(subset) == 0: continue
        counts = subset['type'].value_counts(normalize=True) * 100
        r1 = counts.get('R1', 0)
        r2 = counts.get('R2', 0)
        dwp = counts.get('DWP', 0)
        dnp = counts.get('DNP', 0)
        directional = dwp + dnp
        print(f"| **{day}** | {r1:.1f}% | {r2:.1f}% | {dwp:.1f}% | {dnp:.1f}% | **{directional:.1f}%** |")

    # B. Monthly Seasonality
    df_class['month'] = df_class['date'].dt.month_name()
    months = ['January', 'February', 'March', 'April', 'May', 'June', 
              'July', 'August', 'September', 'October', 'November', 'December']
    print("\n### Monthly Seasonality (Best Month for Each Type)")
    month_stats = []
    for m in months:
        subset = df_class[df_class['month'] == m]
        if len(subset) == 0: continue
        counts = subset['type'].value_counts(normalize=True) * 100
        stats = {k: counts.get(k, 0) for k in all_classes}
        stats['Month'] = m
        month_stats.append(stats)
    
    df_month = pd.DataFrame(month_stats).set_index('Month')
    for cls in all_classes:
        best_month = df_month[cls].idxmax()
        val = df_month[cls].max()
        print(f"- **{cls}**: Peaks in **{best_month}** ({val:.1f}%)")

    # C. Quarterly Analysis
    df_class['quarter'] = df_class['date'].dt.quarter
    print("\n### Quarterly Performance")
    print("| Quarter | R1 | R2 | DWP | DNP |")
    print("| :--- | :--- | :--- | :--- | :--- |")
    for q in [1, 2, 3, 4]:
        subset = df_class[df_class['quarter'] == q]
        counts = subset['type'].value_counts(normalize=True) * 100
        print(f"| Q{q} | {counts.get('R1',0):.1f}% | {counts.get('R2',0):.1f}% | {counts.get('DWP',0):.1f}% | {counts.get('DNP',0):.1f}% |")

    # D. Year-on-Year Trend (2006 vs Recent)
    df_class['year'] = df_class['date'].dt.year
    print("\n### Year-on-Year Trend (Evolution)")
    years = sorted(df_class['year'].unique())
    # Group into buckets: 2006-2015, 2016-2023, 2024-2026
    def get_era(y):
        if y >= 2024: return "Recent (2024-26)"
        if y >= 2016: return "Modern (2016-23)"
        return "Legacy (2006-15)"
    
    df_class['era'] = df_class['year'].apply(get_era)
    print("| Era | R1 | R2 | DWP | DNP | Total Days |")
    print("| :--- | :--- | :--- | :--- | :--- | :--- |")
    era_order = ["Legacy (2006-15)", "Modern (2016-23)", "Recent (2024-26)"]
    for era in era_order:
        subset = df_class[df_class['era'] == era]
        if len(subset) == 0: continue
        counts = subset['type'].value_counts(normalize=True) * 100
        print(f"| {era} | {counts.get('R1',0):.1f}% | {counts.get('R2',0):.1f}% | {counts.get('DWP',0):.1f}% | {counts.get('DNP',0):.1f}% | {len(subset)} |")

    # --- 3. VOLATILITY ANALYSIS (VVIX) ---
    if not df_vvix.empty:
        print("\n## 2. Volatility Edge (VVIX)")
        # Merge VVIX with Class on Date
        # Ensure dates match format
        # df_class dates are YYYY-MM-DD
        df_vvix['date_match'] = df_vvix['Date']
        
        df_vol = pd.merge(df_class, df_vvix, left_on='date', right_on='date_match', how='inner')
        
        # Define Regimes
        # Low < 90, Normal 90-110, High > 110 (Based on user file visual scan roughly)
        # Using Close for regime
        def get_regime(v):
            if v < 90: return "Low (<90)"
            if v > 110: return "High (>110)"
            return "Normal (90-110)"
            
        df_vol['regime'] = df_vol['Close'].apply(get_regime)
        
        print("\n### VVIX Regime Correlations")
        print("| Regime | R1 | R2 | DWP | DNP | n | Expectation |")
        print("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
        
        regimes = ["Low (<90)", "Normal (90-110)", "High (>110)"]
        for r in regimes:
            subset = df_vol[df_vol['regime'] == r]
            if len(subset) < 10: continue
            counts = subset['type'].value_counts(normalize=True) * 100
            n = len(subset)
            
            p_dnp = counts.get('DNP', 0)
            p_r1 = counts.get('R1', 0)
            
            note = "Neutral"
            if p_dnp > 20: note = "TREND FAVORABLE"
            if p_r1 > 25: note = "CHOP WARNING"
            
            print(f"| **{r}** | {counts.get('R1',0):.1f}% | {counts.get('R2',0):.1f}% | {counts.get('DWP',0):.1f}% | {counts.get('DNP',0):.1f}% | {n} | {note} |")

    # --- 4. SESSION PROFILER ANALYSIS ---
    if not df_prof.empty:
        print("\n## 3. Session Edge (Break/Hold Rates)")
        # We need to map sessions to their characteristics
        # profiler.json structure: { 'session': 'Asia', 'range_broken': true/false, ... }
        # Let's aggregate by session name
        
        sessions = ['Asia', 'London', 'NY_AM', 'NY_PM'] # Adjust keys as per your json structure
        # Checking actual keys in df
        available_sessions = df_prof['session'].unique()
        
        print("| Session | Break Rate (Range Broken) | Directional Conviction |")
        print("| :--- | :--- | :--- |")
        
        for sess in available_sessions:
            subset = df_prof[df_prof['session'] == sess]
            if len(subset) == 0: continue
            
            # Break Rate
            # Assuming 'range_broken' or similar boolean exists
            # Checking columns...
            # If not standard, look for columns
            # Common keys: 'broken', 'status', etc.
            # Based on previous tasks, we know 'broken' boolean exists?
            # Actually, let's just count 'status' != 'none' if broken specific field missing.
            # But let's assume 'failed' vs 'broken' logic if available.
            # Based on 'analyze_overnight' logic: checking 'status' being neutral vs direction.
            
            # Let's count 'status' types
            # Counts of 'long true', 'short true' vs 'none'
            stat_counts = subset['status'].value_counts(normalize=True)
            
            # Simplified Break Rate: % of time it picks a direction (not 'none' or 'neutral')
            # Adjust logical check based on actual data
            # If 'status' contains 'true' or 'false', it broke initial bounds?
            # Creating a rough proxy
            
            break_rate = (1.0 - stat_counts.get('none', 0)) * 100
            
            # Conviction: Of the breaks, how many held? (True vs False)
            # Filter for 'true' or 'false' in status string
            breaks = subset[subset['status'] != 'none']
            if len(breaks) > 0:
                held = breaks['status'].str.contains('true').sum()
                conviction = (held / len(breaks)) * 100
            else:
                conviction = 0
                
            
            print(f"| **{sess}** | {break_rate:.1f}% | {conviction:.1f}% (Hold Rate) |")

    # --- 5. OVERNIGHT RANGE ANALYSIS ---
    if not df_prof.empty:
        print("\n## 4. Overnight Range Edge")
        # Logic: 
        # 1. Group profiler by Date
        # 2. Extract Asia High/Low and London High/Low
        # 3. ON_High = max(AsiaMax, LdnMax), ON_Low = min(AsiaMin, LdnMin)
        # 4. Range = ON_High - ON_Low
        
        # We need raw OHLC from profiler.json. 
        # profiler.json usually has 'session_high', 'session_low' fields?
        # Let's check structure. Assuming keys exist based on 'profiler' naming.
        # If keys are 'high', 'low' or similar.
        
        # Let's try to extract if columns exist
        if 'high' in df_prof.columns and 'low' in df_prof.columns and 'date_str' in df_prof.columns:
            # Pivot to get sessions per date
            # We want Asia and London for the SAME trading day.
            # Pivot table: Index=date_str, Columns=session, Values=[high, low]
            
            piv = df_prof.pivot_table(index='date_str', columns='session', values=['high', 'low'], aggfunc='first')
            
            # We need both Asia and London to compute full ON Range
            # Check if columns exist in pivot
            # Columns will be MultiIndex: (high, Asia), (high, London), etc.
            
            try:
                # Filter for dates having both
                valid_dates = piv.dropna(subset=[('high', 'Asia'), ('high', 'London')])
                
                # Calculate ON High/Low
                on_high = np.maximum(valid_dates[('high', 'Asia')], valid_dates[('high', 'London')])
                on_low = np.minimum(valid_dates[('low', 'Asia')], valid_dates[('low', 'London')])
                on_range = on_high - on_low
                
                # Create Analysis DataFrame
                df_on = pd.DataFrame({'on_range': on_range})
                
                # Calculate Rolling Average (20 day)
                df_on['avg_range'] = df_on['on_range'].rolling(20).mean()
                
                # Define Regime
                # Compressed: < 80% of Avg
                # Expanded: > 120% of Avg
                # Normal: 80-120%
                
                def get_range_regime(row):
                    if pd.isna(row['avg_range']): return "N/A"
                    ratio = row['on_range'] / row['avg_range']
                    if ratio < 0.8: return "Compressed (<80%)"
                    if ratio > 1.2: return "Expanded (>120%)"
                    return "Normal (80-120%)"
                
                df_on['regime'] = df_on.apply(get_range_regime, axis=1)
                
                # Merge with Classifications
                # df_class has 'date' column. df_on index is string YYYY-MM-DD.
                df_class['date_str'] = df_class['date'].dt.strftime('%Y-%m-%d')
                
                df_final = pd.merge(df_class, df_on, left_on='date_str', right_index=True, how='inner')
                
                print("\n### Correlation: Overnight Range vs Day Type")
                print("| ON Range Regime | R1 | R2 | DWP | DNP | n | Expectation |")
                print("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
                
                regimes = ["Compressed (<80%)", "Normal (80-120%)", "Expanded (>120%)"]
                for r in regimes:
                    subset = df_final[df_final['regime'] == r]
                    if len(subset) < 10: continue
                    
                    counts = subset['type'].value_counts(normalize=True) * 100
                    n = len(subset)
                    
                    p_dnp = counts.get('DNP', 0)
                    p_r1 = counts.get('R1', 0)
                    
                    note = "Neutral"
                    if p_dnp > 20: note = "EXPLOSIVE POTENTIAL"
                    if p_r1 > 25: note = "EXHAUSTION / CHOP"
                    
                    print(f"| **{r}** | {counts.get('R1',0):.1f}% | {counts.get('R2',0):.1f}% | {counts.get('DWP',0):.1f}% | {counts.get('DNP',0):.1f}% | {n} | {note} |")

            except KeyError as e:
                print(f"Warning: Missing session columns in profiler pivot. Skipping ON Range. {e}")
        else:
             print("Warning: Profiler JSON missing 'high'/'low' fields.")

if __name__ == '__main__':
    analyze_comprehensive_stats('NQ1')
