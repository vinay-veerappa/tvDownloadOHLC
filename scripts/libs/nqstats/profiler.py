"""
NQStats Profiler Module - Statistical Aggregation for Daily Profiling.
Implements the core logic for filtering and generating conditional probabilities.
"""

import pandas as pd
import numpy as np

def calculate_touch_matrix(df_1m: pd.DataFrame, stats: pd.DataFrame) -> pd.DataFrame:
    """
    Check for each level if it was touched during any session play window.
    Standard definition: math.min(open, close) <= level <= math.max(open, close)
    """
    # Identify levels to check
    level_cols = [
        'pdh', 'pdl', 'pdm', 'settle', 'pwc', 
        'open_glob', 'open_mid', 'open_0730',
        'p12h', 'p12m', 'p12l', 
        'nyp12h', 'nyp12m', 'nyp12l',
        'prev_nyp12h', 'prev_nyp12m', 'prev_nyp12l',
        'asiabox_mid', 'londonbox_mid', 'ny1box_mid', 'ny2box_mid',
        'prev_asiabox_mid', 'prev_londonbox_mid', 'prev_ny1box_mid', 'prev_ny2box_mid'
    ]
    
    # Filter to actual levels present in stats
    level_cols = [c for c in level_cols if c in stats.columns]
    
    # high/low for touches (inclusive of wicks)
    low_vals = df_1m['low'].values
    high_vals = df_1m['high'].values
    
    touch_matrix = pd.DataFrame(index=df_1m.index)
    
    for lvl in level_cols:
        l_vals = stats[lvl].values
        # Vectorized touch check for every minute
        touch_matrix[f'touch_{lvl}'] = (low_vals <= l_vals) & (high_vals >= l_vals)
        
    return touch_matrix

def get_daily_profiler_data(df_1m: pd.DataFrame, stats: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregates per-day summary including session outcomes, LOD/HOD, and level touches.
    """
    et_df = df_1m.tz_convert('US/Eastern') if df_1m.index.tz else df_1m
    dates = et_df.index.date
    u_dates = np.unique(dates)
    
    # Get touch matrix first (vectorized)
    touches = calculate_touch_matrix(df_1m, stats)
    
    # Daily results aggregator
    daily_results = []
    
    # Grouping by date for HOD/LOD and Outcomes
    # Outcomes are already in 'stats' as 'asiabox_status', etc.
    # We take the 'last' status of the day for each session
    session_outcomes = stats[['asiabox_status', 'londonbox_status', 'ny1box_status', 'ny2box_status']].groupby(dates).last()
    
    # Prior Session Context for Ctx filters
    daily_context = session_outcomes.shift(1).rename(columns=lambda x: f"prev_{x}")
    
    # Level touches per day (was it touched at ANY minute during the day?)
    # TODO: Refine to session-specific touches as requested by user? 
    # Pine Script checks touches DURING the active session play window.
    
    daily_touches = touches.groupby(dates).max() # 1 if any minute was true
    
    # HOD/LOD Times and Distances (from standard daily open 18:00 prev day or 00:00?)
    # Pine: d_open = request.security(ticker, "D", open) which is usually the calendar day open for futures.
    # For NQ standard, we often use Midnight or 18:00 open.
    # User's engine.py has 'p12' (prior close) but we need 'd_open'.
    # Let's use 18:00 open as base for distances.
    day_open = stats['open_glob'].groupby(dates).last()
    
    # Calculate RTH HOD/LOD (08:00 - 16:00) as per classifiers.py
    rth_df = et_df.between_time("08:00", "16:00")
    rth_groups = rth_df.groupby(rth_df.index.date)
    
    hod_idx = rth_groups['high'].idxmax()
    lod_idx = rth_groups['low'].idxmin()
    
    hod_p = rth_groups['high'].max()
    lod_p = rth_groups['low'].min()
    
    # Distances in percentages
    hod_dist = (hod_p / day_open - 1) * 100
    lod_dist = (lod_p / day_open - 1) * 100
    
    # Time relative to 18:00? The user chart has times like 02:45.
    # Let's use minutes from Midnight or just HH:MM format.
    
    res = pd.DataFrame(index=u_dates)
    res = pd.concat([res, session_outcomes, daily_context, daily_touches], axis=1)
    
    res['hod_time'] = hod_idx.apply(lambda x: x.strftime('%H:%M') if not pd.isna(x) else 'N/A')
    res['lod_time'] = lod_idx.apply(lambda x: x.strftime('%H:%M') if not pd.isna(x) else 'N/A')
    res['hod_dist'] = hod_dist
    res['lod_dist'] = lod_dist
    
    return res

def filter_profiler_stats(daily_df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    """
    Apply filters (e.g. {'asiabox_status': 'LT'}) and return summarized probabilities.
    """
    filtered = daily_df.copy()
    for col, val in filters.items():
        if col in filtered.columns:
            filtered = filtered[filtered[col] == val]
            
    if filtered.empty:
        return pd.DataFrame()
        
    # Summarize Outcomes (Percent for London, NY1, NY2)
    summary = {}
    total = len(filtered)
    summary['count'] = total
    
    for sess in ['londonbox_status', 'ny1box_status', 'ny2box_status']:
        counts = filtered[sess].value_counts()
        for status in ['LT', 'LF', 'ST', 'SF']:
            summary[f"{sess}_{status}"] = (counts.get(status, 0) / total) * 100
            
    # Summarize Level Touches
    for col in filtered.columns:
        if 'touch_' in col:
            summary[col] = (filtered[col].sum() / total) * 100
            
    # HOD/LOD Medians
    # Convert 'HH:MM' back to minutes from Midnight if possible, but let's just use raw median string
    # Summary of median dist
    summary['hod_dist_med'] = filtered['hod_dist'].median()
    summary['lod_dist_med'] = filtered['lod_dist'].median()
    
    # 3. TRANSITION MATRIX (Follow-through)
    # e.g. If current is filtered by Asia=LT, what are London results?
    # This is already covered by London outcomes.
    
    return pd.Series(summary).to_frame().T

def get_followthrough_matrix(daily_df: pd.DataFrame, source_sess: str, target_sess: str) -> pd.DataFrame:
    """
    Generate a matrix like the UI: 'LT-LT', 'LT-LF', etc.
    """
    matrix = {}
    for src_val in ['LT', 'ST', 'LF', 'SF']:
        subset = daily_df[daily_df[source_sess] == src_val]
        total = len(subset)
        if total == 0: continue
        
        counts = subset[target_sess].value_counts()
        for tgt_val in ['LT', 'ST', 'LF', 'SF']:
            prob = (counts.get(tgt_val, 0) / total) * 100
            matrix[f"{src_val}-{tgt_val}"] = {'prob': prob, 'count': total}
            
    return pd.DataFrame(matrix).T
