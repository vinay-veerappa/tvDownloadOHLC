import pandas as pd
import numpy as np
from tqdm import tqdm
import os
from concurrent.futures import ProcessPoolExecutor
from data_loader import load_data, slice_trading_days, get_trading_day_data
from session_extractor import extract_session_stats, TradingDay
from pattern_classifier import classify_manipulation, classify_ny_position, classify_overnight_pattern
from pda_detector import detect_london_pd_arrays
from outcome_measurer import measure_outcomes

def process_day_worker(day_task):
    """
    Worker function for parallel processing.
    day_task: (date, day_df, prev_stats_dict)
    """
    d, day_df, prev_stats = day_task
    
    # 1. Extract Stats
    stats = extract_session_stats(day_df, prev_stats)
    if not stats or pd.isna(stats.ny_open) or pd.isna(stats.london_high):
        return None, None
        
    # 2. Classify
    manipulation = classify_manipulation(stats)
    ny_pos = classify_ny_position(stats)
    pattern = classify_overnight_pattern(stats)
    
    # 3. Detect Arrays
    arrays = detect_london_pd_arrays(day_df, stats, manipulation)
    
    # 4. Measure Outcomes
    outcome = measure_outcomes(day_df, stats, arrays, manipulation)
    
    # Prepare results
    row = {
        'date': d,
        'manipulation': manipulation,
        'ny_position': ny_pos,
        'pattern': pattern,
        'rth_gap': stats.rth_gap,
        'rth_gap_pct': stats.rth_gap_pct,
        'prev_settle': stats.prev_settle,
        'asia_range': stats.asia_range,
        'london_range': stats.london_range,
        'london_high_first': stats.london_high_first,
        'ny_hit_high_first': stats.ny_hit_high_first,
        'asia_high': stats.asia_high,
        'asia_low': stats.asia_low,
        'london_high': stats.london_high,
        'london_low': stats.london_low,
        'london_mid': stats.london_mid,
        'asia_mid': stats.asia_mid,
        'prev_day_high': stats.prev_day_high,
        'prev_day_low': stats.prev_day_low,
        'hit_london_high': outcome.hit_london_high,
        'hit_london_low': outcome.hit_london_low,
        'hit_london_high_first': outcome.hit_london_high_first,
        'gap_fill_25': outcome.gap_fill_25,
        'gap_fill_50': outcome.gap_fill_50,
        'gap_fill_100': outcome.gap_fill_100,
        'manipulation_reversed': outcome.manipulation_reversed,
        'reversal_time': outcome.reversal_time
    }
    
    pd_arrays_results = []
    for arr in arrays:
         pd_arrays_results.append({
             'date': d,
             'type': arr.type,
             'high': arr.high,
             'low': arr.low,
             'midpoint': arr.midpoint,
             'time': arr.time,
             'session': arr.session,
             'in_manipulation_zone': arr.in_manipulation_zone,
             'touched': f"{arr.type}_{arr.time}" in outcome.arrays_touched,
             'respected': f"{arr.type}_{arr.time}" in outcome.arrays_respected,
             'failed': f"{arr.type}_{arr.time}" in outcome.arrays_failed
         })
         
    return row, pd_arrays_results

def run_pipeline(ticker='NQ', limit=None, parallel=True):
    # Load data
    print(f"Loading data for {ticker}...")
    try:
        df_1m = load_data(ticker, '1m')
        df_1d = load_data(ticker, '1d')
    except Exception as e:
        print(f"Error loading data: {e}")
        return

    # Prepare Previous Day Stats from Daily Data
    print("Preparing daily reference data...")
    # Drop duplicates in daily data if any (e.g. rolls)
    df_1d_ext = df_1d.copy()
    df_1d_ext['temp_date'] = df_1d_ext.index.date
    df_1d_clean = df_1d_ext.drop_duplicates('temp_date').copy()
    
    # Shift daily data by 1 to get 'previous' stats for each session date
    df_1d_shifted = df_1d_clean[['high', 'low', 'close']].shift(1)
    df_1d_shifted['date'] = df_1d_clean['temp_date']
    
    # Convert to dictionary for fast lookup: {date_obj: {'high': ..., 'low': ..., 'close': ...}}
    prev_stats_lookup = df_1d_shifted.set_index('date').to_dict('index')

    # Slice 1m data
    print("Slicing trading days...")
    df_sliced = slice_trading_days(df_1m)
    dates = df_sliced['trading_date'].unique()
    dates = dates[pd.notna(dates)]
    dates.sort()
    
    if limit:
        dates = dates[:limit]
    
    # Prepare Tasks
    print(f"Preparing tasks...")
    # Use groupby to avoid O(N*D) search complexity
    day_groups = df_sliced.groupby('trading_date')
    
    tasks = []
    for d in tqdm(dates):
        if d in day_groups.groups:
            day_df = day_groups.get_group(d)
            prev_data = prev_stats_lookup.get(d)
            tasks.append((d, day_df.copy(), prev_data))

    # Run Analysis
    results = []
    all_pd_arrays = []
    
    print(f"Running Analysis on {len(tasks)} days...")
    
    if parallel:
        import multiprocessing
        num_workers = multiprocessing.cpu_count() - 1
        print(f"Using {num_workers} parallel workers.")
        
        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            # results_list will contain (row, arrays) or (None, None)
            results_list = list(tqdm(executor.map(process_day_worker, tasks), total=len(tasks)))
            
        for res in results_list:
            if res and res[0]:
                row, arrays = res
                results.append(row)
                all_pd_arrays.extend(arrays)
    else:
        for task in tqdm(tasks):
            row, arrays = process_day_worker(task)
            if row:
                results.append(row)
                all_pd_arrays.extend(arrays)
            
    # Save Results
    os.makedirs('ict_research/data', exist_ok=True)
    
    results_df = pd.DataFrame(results)
    results_df.to_csv(f'ict_research/data/trading_days_{ticker}.csv', index=False)
    print(f"Saved {len(results_df)} days to trading_days_{ticker}.csv")
    
    arrays_df = pd.DataFrame(all_pd_arrays)
    arrays_df.to_csv(f'ict_research/data/pd_arrays_{ticker}.csv', index=False)
    print(f"Saved {len(arrays_df)} PD arrays to pd_arrays_{ticker}.csv")
    
    return results_df, arrays_df

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Run ICT session research pipeline.')
    parser.add_argument('--ticker', type=str, default='NQ', help='Ticker symbol (e.g. NQ, ES, CL)')
    parser.add_argument('--limit', type=int, default=None, help='Limit number of days to process')
    parser.add_argument('--no-parallel', action='store_true', help='Disable parallel processing')
    
    args = parser.parse_args()
    run_pipeline(ticker=args.ticker, limit=args.limit, parallel=not args.no_parallel)
