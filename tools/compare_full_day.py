
import sys
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import json
from datetime import timedelta

# Add project root to path
sys.path.append(os.getcwd())

from api.services.profiler_service import ProfilerService
from api.services.data_loader import DATA_DIR

def compare_full_day():
    ticker = "NQ1"
    target_session = "NY1"
    target_outcome = "Short True" # User specified
    
    print(f"--- Full Day Comparison Analysis: {ticker} {target_session} {target_outcome} ---")

    # 1. Get Session History (to find valid days)
    print("1. Fetching Session History...")
    # analyze_profiler_stats returns a dict with 'history' list
    # User requested FULL history to match frontend (not just 365 days)
    stats = ProfilerService.analyze_profiler_stats(ticker, days=10000)
    print(f"Debug Stats Keys: {stats.keys()}")
    if "error" in stats:
        print(f"Error getting stats: {stats['error']}")
        return

    history = pd.DataFrame(stats.get('sessions', []))
    if history.empty:
        print("No history found.")
        return

    # Filter Logic: Complete Filters
    # 1. Group by Date
    day_map = {}
    for _, row in history.iterrows():
        d = row['date']
        s = row['session']
        if d not in day_map: day_map[d] = {}
        day_map[d][s] = row

    # 2. Apply "Given" Filters
    # Asia: Short True
    # London: Long False (Inferred from "Long Fa...")
    # NY1: Short True (Target)
    
    filtered_matches = []
    
    print("Applying Complete Filters: Asia=Short True (Broken), London=Long False (Broken), NY1=Short True")
    
    # debug_matches = 0 # No longer needed for the simplified debug output
    for d, sessions in day_map.items():
        # DEBUG: Inspect candidates
        ny1 = sessions.get(target_session)
        if ny1 is not None and ny1['status'] == target_outcome:
            # Check logic implicitly
            pass # Remove verbal debug to reduce noise, rely on final count?
            # Or keep it but simple
        
        # Check Asia
        asia = sessions.get('Asia')
        if asia is None or asia['status'] != 'Short True' or not asia.get('broken'):
            continue
            
        # Check London
        london = sessions.get('London')
        # Check for 'Long False' (and Broken)
        if london is None or london['status'] != 'Long False' or not london.get('broken'):
            continue
            
        # Check Target (NY1)
        if ny1 is None or ny1['status'] != target_outcome:
            continue
            
        filtered_matches.append(ny1)
        
    matches = pd.DataFrame(filtered_matches)
    
    print(f"Found {len(matches)} fully filtered sessions.")

    # 2. Prepare 00:00 Sessions
    print("2. preparing 00:00 Sessions...")
    
    # Load 1m Data for Open Prices
    df_1m = ProfilerService._cache.get(ticker)
    if df_1m is None:
        file_path = DATA_DIR / f"{ticker}_1m.parquet"
        df_1m = pd.read_parquet(file_path)
        
        # DEBUG: Inspect Raw Time
        print("--- TIMEZONE DEBUG ---")
        if not df_1m.empty:
            raw_ts = df_1m.iloc[0]['time'] if 'time' in df_1m.columns else df_1m.index[0]
            print(f"Raw First Timestamp: {raw_ts} (Type: {type(raw_ts)})")
        
        if df_1m.index.tz is None: 
            print("Index is TZ-naive. Assuming UTC and converting to US/Eastern...")
            df_1m = df_1m.tz_localize('UTC').tz_convert('US/Eastern')
        else: 
            print(f"Index is TZ-aware: {df_1m.index.tz}. Converting to US/Eastern...")
            df_1m = df_1m.tz_convert('US/Eastern')
            
        print(f"Localized First Timestamp: {df_1m.index[0]}")
        
        # Check for CME Close Gap (Expect no data 17:00-18:00 ET)
        # Let's count bars by hour for a sample day
        sample_day = df_1m.index[1000].date()
        sample_data = df_1m[df_1m.index.date == sample_day]
        print(f"Sample Day ({sample_day}) Hourly Counts:")
        print(sample_data.groupby(sample_data.index.hour).size().to_dict())
        print("----------------------")
        
        ProfilerService._cache[ticker] = df_1m
        
    full_day_sessions = []
    
    # ... (Previous imports and setup) ...

    # 4. Load Reference and Rotate
    print("4. Loading and Rotating Reference...")
    with open('docs/reference_medians.json', 'r') as f:
        ref_data = json.load(f)
    ref_df = pd.DataFrame(ref_data.get('medians', []))
    
    # Rotate Reference so 18:00:00 is first
    try:
        start_idx = ref_df[ref_df['time'] == "18:00:00"].index[0]
        ref_df = pd.concat([ref_df.iloc[start_idx:], ref_df.iloc[:start_idx]]).reset_index(drop=True)
        print(f"Reference Data rotated. Start Time: {ref_df.iloc[0]['time']}")
    except IndexError:
        print("Warning: 18:00:00 not found in reference. Using default order.")

    # 2. preparing 18:00 Aligned Sessions & Monte Carlo Data...
    
    df_1m = ProfilerService._cache.get(ticker) # Ensure loaded
    
    # Monte Carlo Storage
    # Max minutes = 24 * 60 = 1440. 
    # Use 1440 length arrays.
    mc_highs = []
    mc_lows = []
    
    valid_sessions = 0
    
    print(f"DEBUG: df_1m length: {len(df_1m) if df_1m is not None else 'None'}")
    
    debug_limit = 5
    debug_count = 0
    
    for _, row in matches.iterrows():
        sess_start = pd.Timestamp(row['start_time']) # US/Eastern
        
        # Cycle Start Logic (18:00)
        if sess_start.hour < 18:
            cycle_start = sess_start.replace(hour=18, minute=0, second=0, microsecond=0) - pd.Timedelta(days=1)
        else:
            cycle_start = sess_start.replace(hour=18, minute=0, second=0, microsecond=0)
            
        # Get Data for this Cycle (24h)
        cycle_end = cycle_start + pd.Timedelta(hours=24)
        
        # Slice Data
        # Ensure we have data
        try:
            start_idx = df_1m.index.searchsorted(cycle_start)
            end_idx = df_1m.index.searchsorted(cycle_end)
            
            if start_idx >= len(df_1m): 
                if debug_count < debug_limit:
                    print(f"DEBUG SKIP: Start Index Out of Bounds. CycleStart: {cycle_start}")
                    debug_count += 1
                continue
            
            # Check gap from requested start
            actual_start_ts = df_1m.index[start_idx]
            diff_seconds = (actual_start_ts - cycle_start).total_seconds()
            
            if diff_seconds > 3600: 
                if debug_count < debug_limit:
                     print(f"DEBUG SKIP: Large Gap ({diff_seconds}s). Target: {cycle_start}, Actual: {actual_start_ts}")
                     debug_count += 1
                continue
            
            sub_df = df_1m.iloc[start_idx:end_idx]
            if sub_df.empty: 
                print("DEBUG SKIP: Empty Sub DF")
                continue
            
            open_price = sub_df.iloc[0]['open']
            if open_price <= 0: continue
            
            # Normalize
            # Map timestamps to minutes from cycle_start
            minutes = (sub_df.index - cycle_start).total_seconds() / 60.0
            minutes = minutes.astype(int)
            
            # Filter to 0..1439
            valid_mask = (minutes >= 0) & (minutes < 1440)
            minutes = minutes[valid_mask]
            
            if len(minutes) < 100: # Limit usage of very fragmented sessions?
                 if debug_count < debug_limit:
                     print(f"DEBUG SKIP: Too few bars ({len(minutes)})")
                     debug_count += 1
                 continue
                 
            sub_high = sub_df['high'].values[valid_mask]
            sub_low = sub_df['low'].values[valid_mask]
            
            # Create dense arrays filled with NaN
            path_h = np.full(1440, np.nan)
            path_l = np.full(1440, np.nan)
            
            norm_h = (sub_high - open_price) / open_price * 100
            norm_l = (sub_low - open_price) / open_price * 100
            
            path_h[minutes] = norm_h
            path_l[minutes] = norm_l
            
            # Forward Fill (optional, but good for gaps)?
            # Or leave NaN for stats (numpy handles nanmean)
            # Let's simple polyfill NaN? No, keep pure.
            
            mc_highs.append(path_h)
            mc_lows.append(path_l)
            valid_sessions += 1
            
        except Exception as e:
            print(f"DEBUG Error: {e}")
            continue
            
    print(f"Collected {valid_sessions} paths for Monte Carlo.")
    
    # Convert to Matrix
    if valid_sessions == 0:
        print("No valid sessions found.")
        return

    mat_h = np.array(mc_highs) # (N, 1440)
    mat_l = np.array(mc_lows)
    
    # 3. Calculate Models
    print("3. Calculating Statistics...")
    
    # Mean Model
    mean_h = np.nanmean(mat_h, axis=0)
    mean_l = np.nanmean(mat_l, axis=0)
    std_h = np.nanstd(mat_h, axis=0)
    std_l = np.nanstd(mat_l, axis=0)
    
    # Median Model
    med_h = np.nanmedian(mat_h, axis=0)
    med_l = np.nanmedian(mat_l, axis=0)
    # User asked for StdDev from Average... or Median? 
    # "makes an average and then takes one standard deviation... make one more graph but use median instead of average and then do 1 standard deviation"
    # So reuse StdDev.
    
    # 5. Correlation Analysis
    # Reference Data is at 5m intervals. We need to align our 1m arrays to Ref Index.
    # Ref Index 0 = Minute 0. Ref Index 1 = Minute 5.
    # Create valid indices map
    
    ref_indices = [] # 0, 5, 10
    ref_clean_h = []
    ref_clean_l = []
    
    model_mean_h = []
    model_mean_l = []
    model_med_h = []
    model_med_l = []
    
    for i, row in ref_df.iterrows():
        minute_idx = i * 5
        if minute_idx < 1440:
            # Check if we have valid model data at this minute
            # Use nearest valid if NaN? Or just check NaN
            if not np.isnan(mean_h[minute_idx]):
                ref_indices.append(minute_idx)
                ref_clean_h.append(row['med_high_pct'])
                ref_clean_l.append(row['med_low_pct'])
                
                model_mean_h.append(mean_h[minute_idx])
                model_mean_l.append(mean_l[minute_idx])
                
                model_med_h.append(med_h[minute_idx])
                model_med_l.append(med_l[minute_idx])

    # Calculate Pearson Correlation
    if len(ref_clean_h) > 10:
        corr_mean_h = np.corrcoef(ref_clean_h, model_mean_h)[0, 1]
        corr_mean_l = np.corrcoef(ref_clean_l, model_mean_l)[0, 1]
        
        corr_med_h = np.corrcoef(ref_clean_h, model_med_h)[0, 1]
        corr_med_l = np.corrcoef(ref_clean_l, model_med_l)[0, 1]
        
        print("\n--- Correlation Analysis (vs Reference) ---")
        print(f"Mean Model (High): {corr_mean_h:.4f}")
        print(f"Mean Model (Low):  {corr_mean_l:.4f}")
        print(f"Median Model (High): {corr_med_h:.4f}")
        print(f"Median Model (Low):  {corr_med_l:.4f}")
        
    # 6. Plotting - Quarterly Breakdown (Clean)
    print("5. Plotting Quarterly Breakdown...")
    
    total_points = len(ref_df)
    points_per_q = total_points // 4
    
    # Ensure lists are numpy arrays for easier slicing if needed, or just list slice
    # model arrays are lists atm. ref_df columns are Series.
    
    for q in range(4):
        start_idx = q * points_per_q
        end_idx = (q + 1) * points_per_q if q < 3 else total_points
        
        # Quarter Label
        start_h = (q * 6) 
        end_h = ((q + 1) * 6)
        q_label = f"Hours {start_h:02d}-{end_h:02d}"
        
        fig, axes = plt.subplots(2, 1, figsize=(14, 10), sharex=True)
        plt.style.use('bmh')
        
        # Slices
        # Model X (Reference Index Scaled)
        # We need to preserve the monotonic X to keep plots correct? 
        # Actually, simpler to just use 0..N for the subplot X axis but label properly?
        # Let's align them.
        ref_x_slice = range(start_idx, end_idx) # Use absolute indices for X to keep consistent labels? 
        # Or relative? Relative 0..72 is often cleaner for "Zoom". 
        # But labels need to be correct.
        # Let's use range(0, length_of_slice) and map labels.
        slice_len = end_idx - start_idx
        x_plot_slice = range(slice_len)
        
        # Arrays
        # Ref
        ref_h_slice = ref_df['med_high_pct'].iloc[start_idx:end_idx]
        ref_l_slice = ref_df['med_low_pct'].iloc[start_idx:end_idx]
        ref_times_slice = ref_df['time'].iloc[start_idx:end_idx].tolist()
        
        # Models (Lists)
        mod_mean_h_slice = model_mean_h[start_idx:end_idx]
        mod_mean_l_slice = model_mean_l[start_idx:end_idx]
        mod_med_h_slice = model_med_h[start_idx:end_idx]
        mod_med_l_slice = model_med_l[start_idx:end_idx]
        
        # Subplot 1: Mean
        ax_mean = axes[0]
        ax_mean.set_title(f"Mean Model vs Ref ({q_label}) - Corr: {corr_mean_l:.2f}") # Global corr for context
        ax_mean.plot(x_plot_slice, ref_h_slice, color='green', linewidth=2, label='Reference High')
        ax_mean.plot(x_plot_slice, ref_l_slice, color='red', linewidth=2, label='Reference Low')
        ax_mean.plot(x_plot_slice, mod_mean_h_slice, color='blue', linestyle='--', linewidth=1.5, label='Mean High')
        ax_mean.plot(x_plot_slice, mod_mean_l_slice, color='orange', linestyle='--', linewidth=1.5, label='Mean Low')
        ax_mean.legend(loc='upper left')
        ax_mean.grid(True)
        
        # Subplot 2: Median
        ax_med = axes[1]
        ax_med.set_title(f"Median Model vs Ref ({q_label})")
        ax_med.plot(x_plot_slice, ref_h_slice, color='green', linewidth=2, label='Reference High')
        ax_med.plot(x_plot_slice, ref_l_slice, color='red', linewidth=2, label='Reference Low')
        ax_med.plot(x_plot_slice, mod_med_h_slice, color='blue', linestyle=':', linewidth=1.5, label='Median High')
        ax_med.plot(x_plot_slice, mod_med_l_slice, color='orange', linestyle=':', linewidth=1.5, label='Median Low')
        ax_med.legend(loc='upper left')
        ax_med.grid(True)
        
        # X Ticks
        # Show every 6th tick (~30 mins)
        tick_step = 6
        ax_med.set_xticks(list(range(slice_len))[::tick_step])
        ax_med.set_xticklabels([t[:5] for t in ref_times_slice[::tick_step]], rotation=45)
        
        fname = f"docs/comparison_q{q+1}_clean.png"
        plt.tight_layout()
        plt.savefig(fname)
        plt.close(fig) 
        print(f"Saved {fname}")

if __name__ == "__main__":
    compare_full_day()

