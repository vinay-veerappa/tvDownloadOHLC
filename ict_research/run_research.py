import argparse
import dataclasses
import pandas as pd
import numpy as np
import datetime
from datetime import time, timedelta
import os
import multiprocessing
from multiprocessing import Pool, cpu_count
from functools import partial

from session_extractor import extract_session_stats, TradingDay
from pattern_classifier import (
    classify_overnight_pattern, classify_manipulation, classify_ny_position,
    classify_pm_pattern, classify_pm_manipulation, detect_judas_pm, detect_judas_london
)
from pda_detector import detect_london_pd_arrays
from outcome_measurer import (
    measure_outcomes, measure_ny_enhanced, measure_pm_outcomes, measure_asia_outcomes,
    NYOutcome, PMOutcome, AsiaOutcome
)
from data_loader import load_data, slice_trading_days, get_trading_day_data

def process_day_worker(args):
    """
    Worker function for parallel processing.
    args: (t_date, df_day, day_stats)
    """
    t_date, df_day, day_stats = args
    
    if df_day.empty or day_stats is None:
        return None

    # 2. Classify Patterns
    pattern = classify_overnight_pattern(day_stats)
    manipulation = classify_manipulation(day_stats)
    ny_position = classify_ny_position(day_stats)
    
    # NEW: Detect Judas London
    is_judas_london = detect_judas_london(day_stats, manipulation)
    
    # 3. Detect PD Arrays
    pd_arrays = detect_london_pd_arrays(df_day, day_stats, manipulation)
    
    # 4. Measure Outcomes (Original)
    ny_outcome = measure_outcomes(df_day, day_stats, pd_arrays, manipulation)
    
    # 5. Measure Outcomes (Enhanced)
    measure_ny_enhanced(df_day, day_stats, ny_outcome)
    
    # 6. PM Classification (NEW)
    pm_pattern = classify_pm_pattern(day_stats)
    pm_manipulation = classify_pm_manipulation(day_stats)
    day_stats.pattern_pm = pm_pattern
    day_stats.manip_pm = pm_manipulation
    day_stats.is_judas_pm = detect_judas_pm(day_stats, pm_manipulation)
    
    # 7. PM Outcomes (NEW)
    pm_outcome = measure_pm_outcomes(df_day, day_stats)
    
    # Return a dictionary of results and the updated stats object (needed for Asia pass)
    # Use dataclasses.asdict to capture ALL fields (fixes missing columns bug)
    row = dataclasses.asdict(day_stats)
    
    # Fix Datetime Serialization
    for k, v in row.items():
        if isinstance(v, (datetime.datetime, datetime.time, pd.Timestamp)):
            row[k] = str(v) if v is not None else None

    # Merge NY Outcome fields
    for field in dataclasses.fields(ny_outcome):
        key = field.name
        val = getattr(ny_outcome, key)
        if key not in ['arrays_touched', 'arrays_respected', 'arrays_failed']: 
            # Prefix helpful? Most are unique. 
            row[key] = val

    # Merge PM Outcome fields (prefixed)
    for field in dataclasses.fields(pm_outcome):
        row[f'pm_{field.name}'] = getattr(pm_outcome, field.name)

    # Add Phase 2 Classifications (not in TradingDay)
    row['pattern'] = pattern
    row['manipulation'] = manipulation
    row['ny_position'] = ny_position
    row['is_judas_london'] = is_judas_london
    
    return row, day_stats

def main():
    # Enforce spawn method for Windows compatibility if needed, 
    # but strictly inside main block to avoid recursive loops
    pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run ICT Research Pipeline')
    parser.add_argument('--ticker', type=str, required=True, help='Ticker symbol (e.g. NQ)')
    parser.add_argument('--no-parallel', action='store_true', help='Disable parallel processing')
    args = parser.parse_args()

    ticker = args.ticker
    print(f"Loading data for {ticker}...")
    
    # Load 1m data
    df_1m = load_data(ticker, '1m')
    df_1m = slice_trading_days(df_1m)
    
    # Load 1d data for weekly/monthly stats
    try:
        df_1d = load_data(ticker, '1d')
        if not df_1d.empty:
            df_1d = df_1d.sort_index()
    except FileNotFoundError:
        print("Warning: Daily data not found. Weekly/Monthly stats will be missing.")
        df_1d = pd.DataFrame()

    unique_dates = df_1m['trading_date'].unique()
    # Filter out NaT/None values that cannot be compared/sorted
    unique_dates = unique_dates[pd.notna(unique_dates)]
    unique_dates.sort()
    
    print(f"Processing {len(unique_dates)} trading days...")
    
    # --- PHASE 1: Sequential Extraction (Preserve History) ---
    print("Phase 1: extracting session stats (sequential)...")
    
    # Optimization: Group by date once to avoid repeated filtering
    print("  Splitting data by date...")
    day_groups = df_1m.groupby('trading_date')
    
    day_stats_list = []
    day_dfs_cache = {} # Cache df slices for Phase 2
    
    # Context Tracking
    prev_day_stats = None
    prev_week_stats = None
    prev_month_stats = None
    
    # Running Aggregates
    curr_week_h, curr_week_l, curr_week_o = None, None, None
    curr_month_h, curr_month_l, curr_month_o = None, None, None
    last_week_num = None
    last_month_num = None
    
    print("  Extracting stats...")
    for i, t_date in enumerate(unique_dates):
        try:
            day_1m = day_groups.get_group(t_date)
        except KeyError:
            continue
            
        day_dfs_cache[t_date] = day_1m 
        
        # --- Context Logic (Group E) ---
        ts = pd.Timestamp(t_date)
        week_num = ts.isocalendar()[1]
        month_num = ts.month
        
        # Week Boundary
        if last_week_num is not None and week_num != last_week_num:
            prev_week_stats = {
                'high': curr_week_h, 'low': curr_week_l,
                'weekly_open': curr_week_o,
                'close': prev_day_stats.get('close') if prev_day_stats else None,
                'mid': (curr_week_h + curr_week_l)/2 if (curr_week_h and curr_week_l) else None
            }
            curr_week_h, curr_week_l, curr_week_o = None, None, None
            
        # Month Boundary
        if last_month_num is not None and month_num != last_month_num:
            prev_month_stats = {
                'high': curr_month_h, 'low': curr_month_l,
                'monthly_open': curr_month_o,
                'close': prev_day_stats.get('close') if prev_day_stats else None,
            }
            curr_month_h, curr_month_l, curr_month_o = None, None, None
            
        last_week_num = week_num
        last_month_num = month_num

        if i % 100 == 0:
            print(f"  Processed {i}/{len(unique_dates)} days...", end='\r')
            
        # Pass full context
        day_stats = extract_session_stats(day_1m, prev_day_stats, prev_week_stats, prev_month_stats)
        
        if day_stats:
            day_stats_list.append((t_date, day_stats))
            
            # --- Update Running Aggregates ---
            ny_h, ny_l, ny_c = day_stats.ny_high, day_stats.ny_low, day_stats.ny_close
            
            # Weekly
            if curr_week_h is None:
                curr_week_h = ny_h
                curr_week_l = ny_l
                curr_week_o = day_stats.globex_open # Week starts Sunday 18:00
            else:
                if pd.notna(ny_h): curr_week_h = max(curr_week_h, ny_h)
                if pd.notna(ny_l): curr_week_l = min(curr_week_l, ny_l)
                
            # Monthly
            if curr_month_h is None:
                curr_month_h = ny_h
                curr_month_l = ny_l
                curr_month_o = day_stats.globex_open
            else:
                if pd.notna(ny_h): curr_month_h = max(curr_month_h, ny_h)
                if pd.notna(ny_l): curr_month_l = min(curr_month_l, ny_l)

            # Update prev stats for next iteration
            prev_day_stats = {
                'high': day_stats.ny_high, 'low': day_stats.ny_low, 
                'close': day_stats.ny_close,
                'am_high': day_stats.ny_am_high, 'am_low': day_stats.ny_am_low,
                'pm_high': day_stats.ny_pm_high, 'pm_low': day_stats.ny_pm_low,
                'pm_mid': day_stats.ny_pm_mid,
                'lunch_high': day_stats.lunch_high, 'lunch_low': day_stats.lunch_low,
            }
        else:
            # Handle empty day
            pass

    # --- PHASE 2: Parallel Analysis ---
    print("Phase 2: running analysis (parallel)...")
    
    # Prepare arguments
    tasks = []
    for t_date, day_stats in day_stats_list:
        tasks.append((t_date, day_dfs_cache[t_date], day_stats))
    
    final_stats_map = {} # Map date -> updated day_stats (with PM classification)
    results = []
    
    if args.no_parallel:
        print("Running in serial mode...")
        worker_outputs = [process_day_worker(task) for task in tasks]
    else:
        num_cores = cpu_count()
        print(f"Running on {num_cores} cores...")
        with Pool(processes=num_cores) as pool:
            worker_outputs = pool.map(process_day_worker, tasks)
            
    # Collect results
    for out in worker_outputs:
        if out:
            row, updated_stats = out
            results.append(row)
            final_stats_map[row['date']] = updated_stats

    # --- PHASE 3: Asia Outcomes (Sequential - Cross-Day) ---
    print("Phase 3: measuring Asia outcomes (cross-day)...")
    
    # We iterate through the RESULTS.
    # For result i (Date T), we calculate Asia outcomes using Day T's NEW PM stats vs Day T+1's data.
    # Note: Pass 2 computed PM stats and stored them in final_stats_map.
    
    # Convert results to DataFrame for easy indexing logic, or just iterate list
    # Because we need T+1's data, we need to find the next date in our cache.
    
    date_to_next_date = {unique_dates[i]: unique_dates[i+1] for i in range(len(unique_dates)-1)}
    
    for row in results:
        curr_date = row['date']
        next_date = date_to_next_date.get(curr_date)
        
        # Default empty values
        row['asia_hit_pm_high'] = False
        row['asia_hit_pm_low'] = False
        row['asia_hit_pdh'] = False
        row['asia_hit_pdl'] = False
        row['asia_pm_manip_reversed'] = False
        
        if next_date and next_date in day_dfs_cache:
            next_day_df = day_dfs_cache[next_date]
            curr_stats = final_stats_map[curr_date] # Get stats with PM info
            
            asia_outcome = measure_asia_outcomes(next_day_df, curr_stats)
            
            row['asia_hit_pm_high'] = asia_outcome.hit_pm_high
            row['asia_hit_pm_low'] = asia_outcome.hit_pm_low
            row['asia_hit_pdh'] = asia_outcome.hit_pdh
            row['asia_hit_pdl'] = asia_outcome.hit_pdl
            row['asia_pm_manip_reversed'] = asia_outcome.pm_manip_reversed
            row['asia_pm_high_first'] = asia_outcome.pm_high_first

    # Save Results
    results_df = pd.DataFrame(results)
    
    # Ensure data directory exists
    data_dir = 'ict_research/data'
    if not os.path.exists(data_dir):
        if os.path.exists('data'):
            data_dir = 'data'
        else:
             os.makedirs(data_dir, exist_ok=True)
             
    output_path = os.path.join(data_dir, f"trading_days_enhanced_{ticker}.csv")
    results_df.to_csv(output_path, index=False)
    print(f"Saved enhanced results to {output_path}")
