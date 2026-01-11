import pandas as pd
import numpy as np
import os

# =============================================================================
# CONFIGURATION
# =============================================================================
DATA_PATH = r"data/NQ1_1m.parquet"
OUTPUT_DIR = r"docs/strategies/magic_hour_analysis"
FROM_DATE = "2013-01-01"
TO_DATE = "2026-12-31"

STRATEGIES = {
    "RANK #1: 07:00": {"magic_h": 7, "stop_h": 11},
    "RANK #2: 08:00": {"magic_h": 8, "stop_h": 12},
    "RANK #3: 06:00": {"magic_h": 6, "stop_h": 10},
    "RANK #4: 00:00": {"magic_h": 0, "stop_h": 4},
    "RANK #5: 01:00": {"magic_h": 1, "stop_h": 5},
    "RANK #6: 02:00": {"magic_h": 2, "stop_h": 6},
    "RANK #7: 23:00": {"magic_h": 23, "stop_h": 3},
}

def load_data():
    print(f"Loading {DATA_PATH}...")
    df = pd.read_parquet(DATA_PATH)
    
    # Convert UTC to EST/EDT and make timezone-naive for simpler comparisons
    if df.index.tz is None:
        df.index = df.index.tz_localize('UTC')
    df.index = df.index.tz_convert('America/New_York')
    # Remove timezone info to avoid dtype comparison issues
    df.index = df.index.tz_localize(None)
    
    # Pre-calculate hour for fast filtering
    df['hour'] = df.index.hour
    df['date'] = df.index.date
    
    # Filter Date Range
    mask = (df.index >= pd.Timestamp(FROM_DATE)) & \
           (df.index <= pd.Timestamp(TO_DATE))
    df = df[mask]
    
    print(f"Data Loaded: {len(df)} rows")
    return df

def analyze_strategy_vectorized(df, name, magic_h, stop_h):
    print(f"Analyzing {name} (Magic: {magic_h}:00)...")
    
    # 1. Identify Magic Hour Ranges
    # Filter data to only magic hour rows
    magic_data = df[df['hour'] == magic_h]
    if magic_data.empty: return pd.DataFrame()
    
    # Group by date to get High/Low/Mid
    daily_stats = magic_data.groupby('date').agg(
        mh_high=('high', 'max'),
        mh_low=('low', 'min'),
    )
    # Get max time separately to avoid index error
    reset_magic = magic_data.reset_index()
    ts_col = reset_magic.columns[0]  # First column is the former index
    last_times = reset_magic.groupby('date')[ts_col].max()
    daily_stats['mh_end'] = last_times
    daily_stats['mh_rng'] = daily_stats['mh_high'] - daily_stats['mh_low']
    daily_stats['mh_mid'] = (daily_stats['mh_high'] + daily_stats['mh_low']) / 2
    
    # 2. Prepare Analysis Window Data
    # We need to map every 1m bar to its corresponding "Magic Session"
    # Logic: If stop_h > magic_h, same day. If stop_h < magic_h (e.g. 23 -> 3), next day?
    # Actually, simpler: Merge daily_stats onto the main DF by Date
    # For rollover (23:00), the session belongs to Date D, but analysis runs into D+1. 
    
    # Strategy: 
    # Get all data.
    # Create a 'session_date' column.
    # For normal hours (0-23), session_date is mostly date.
    # For 23:00 strategy, hours 0,1,2,3 belong to Previous Day's session.
    
    df_window = df.copy()
    
    if magic_h == 23:
        # If magic is 23, then hours 0,1,2,3 belong to the session of (Date - 1 Day)
        # Shift date for early morning hours to match the previous day's 23:00
        is_early = df_window['hour'] <= stop_h
        df_window.loc[is_early, 'date'] = df_window.loc[is_early, 'date'] - pd.Timedelta(days=1)
        
    # Merge stats
    df_merged = df_window.merge(daily_stats, left_on='date', right_index=True, how='inner')
    
    # Filter for Analysis Window ONLY
    # Time > mh_end AND Time <= mh_end + 3h
    # Note: mh_end is the last minute of the magic hour for that session
    
    # Calculate limits per row
    # This is slightly expensive, but vectorized
    # Better: Filter by HOUR first
    
    if stop_h > magic_h:
        # Same day window: Magic < Hour <= Stop
        # e.g. Magic 7, Stop 11 (Window 8, 9, 10, maybe bits of 11)
        # Detailed check:
        # Start: Strictly > Magic Hour (since mh_end is usually XX:59)
        # End: <= Stop Hour (strictly, or Stop Hour:00?) 
        # Report says "3 hours after". 7->8,9,10. Stop at 11:00?
        hour_mask = (df_merged['hour'] > magic_h) & (df_merged['hour'] < stop_h) 
        # This gets 8, 9, 10 fully.
    else:
        # Rollover: 23 -> 0, 1, 2. Stop 3.
        # Hours > 23 OR Hours < 3
        hour_mask = (df_merged['hour'] > magic_h) | (df_merged['hour'] < stop_h)

    # Apply coarse filter
    window_data = df_merged[hour_mask].copy()
    
    if window_data.empty: return pd.DataFrame()
    
    # 3. Detect Breakouts
    # High Break: High > mh_high
    # Low Break: Low < mh_low
    
    window_data['break_H'] = window_data['high'] > window_data['mh_high']
    window_data['break_L'] = window_data['low'] < window_data['mh_low']
    
    # Find FIRST breakout per session
    # We only care about the first one.
    # Assign breakout type: 1 for High, -1 for Low, 0 None
    # If both happen in same bar (rare), prioritize? Code assumes one.
    
    # Identify breakout bars
    breaks = window_data[window_data['break_H'] | window_data['break_L']].copy()
    
    if breaks.empty: return pd.DataFrame()
    
    # Store timestamp in column before grouping
    breaks['bar_ts'] = breaks.index
    
    # Get first break per date
    first_breaks = breaks.groupby('date').first()
    # Determine side of first break
    first_breaks['side'] = np.where(first_breaks['break_H'], 'HIGH', 'LOW')
    # break_time is now the actual timestamp from bar_ts
    first_breaks['break_time'] = first_breaks['bar_ts']
    
    # Join break info back to window_data to mark "Post-Breakout Phase"
    window_data = window_data.merge(
        first_breaks[['side', 'break_time']], 
        left_on='date', 
        right_index=True, 
        how='left'
    )
    
    # Filter: Keep only rows >= break_time
    # Need to add index as column for comparison
    window_data['ts'] = window_data.index
    # Index is already timezone-naive, direct comparison works
    active_data = window_data[window_data['ts'] >= window_data['break_time']].copy()
    
    # 4. Check Targets (50% Reversion)
    # High Break (side='HIGH') -> Target is Low <= mh_mid
    # Low Break (side='LOW') -> Target is High >= mh_mid
    
    active_data['hit_target'] = (
        ((active_data['side'] == 'HIGH') & (active_data['low'] <= active_data['mh_mid'])) |
        ((active_data['side'] == 'LOW') & (active_data['high'] >= active_data['mh_mid']))
    )
    
    # Find FIRST target hit per session
    targets = active_data[active_data['hit_target']].groupby('date').first()
    # target_time should be the actual timestamp from 'ts' column
    targets['target_time'] = targets['ts']
    
    # 5. Measure MAE
    # We need max deviation between [break_time, target_time] (or end of window if no target)
    # Map target_time back to active_data
    # If no target hit, target_time is NaT (or acts as end of session)
    
    # Merge target time
    active_data = active_data.merge(
        targets[['target_time']], 
        left_on='date', 
        right_index=True, 
        how='left'
    )
    
    # Limit rows to BEFORE target hit (inclusive of hit bar for calc? usually MAE is pre-target)
    # Rows where Time <= TargetTime OR TargetTime is Null
    mae_phase = active_data[ 
        (active_data.index <= active_data['target_time']) | 
        (active_data['target_time'].isna()) 
    ].copy()
    
    # Calculate Deviation for every row in MAE phase
    # High Break -> Bad is High - HighLimit
    # Low Break -> Bad is LowLimit - Low
    mae_phase['dev'] = 0.0
    
    mask_h = mae_phase['side'] == 'HIGH'
    mae_phase.loc[mask_h, 'dev'] = mae_phase.loc[mask_h, 'high'] - mae_phase.loc[mask_h, 'mh_high']
    
    mask_l = mae_phase['side'] == 'LOW'
    mae_phase.loc[mask_l, 'dev'] = mae_phase.loc[mask_l, 'mh_low'] - mae_phase.loc[mask_l, 'low']
    
    # Max Dev per session
    session_mae = mae_phase.groupby('date')['dev'].max()
    
    # Normalize by Range -> %
    # We need mh_rng from daily_stats
    results = pd.DataFrame(index=first_breaks.index)
    results['break'] = first_breaks['side']
    results['win'] = False # Default
    results.loc[targets.index, 'win'] = True
    
    results['mh_rng'] = daily_stats['mh_rng']
    results['mae_val'] = session_mae
    results['mae_pct'] = (results['mae_val'] / results['mh_rng']) * 100
    
    # Time to Target
    results['time_mins'] = np.nan
    if not targets.empty:
        # Match targets to breaks to calc delta
        # Use .values to ensure proper subtraction
        t_times = pd.to_datetime(targets['target_time'].values)
        b_times = pd.to_datetime(first_breaks.loc[targets.index, 'break_time'].values)
        deltas = t_times - b_times
        results.loc[targets.index, 'time_mins'] = deltas.total_seconds() / 60

    return results

def generate_report(all_results):
    lines = []
    lines.append("# Magic Hour Validation Report (2013-2026)")
    lines.append(f"**Data Source:** {DATA_PATH}")
    lines.append(f"**Generated:** {pd.Timestamp.now()}\n")
    
    lines.append("## Summary Comparison")
    lines.append("| Strategy | My Total | My Win% | Rep Win% | My MAE | Rep MAE | My Time(Med) | Rep Time(Med) |")
    lines.append("|---|---|---|---|---|---|---|---|")
    
    benchmarks = {
        "RANK #1: 07:00": {'win': 83.4, 'mae': 53.8, 'time': 29},
        "RANK #2: 08:00": {'win': 79.7, 'mae': 48.2, 'time': 18},
        "RANK #3: 06:00": {'win': 78.7, 'mae': 59.3, 'time': 44},
        "RANK #4: 00:00": {'win': 76.8, 'mae': 55.2, 'time': 31},
    }
    
    for name, res_df in all_results.items():
        if res_df.empty:
            lines.append(f"| {name} | NO DATA | - | - | - | - | - | - |")
            continue
            
        total = len(res_df)
        wins = res_df['win'].sum()
        win_rate = (wins / total) * 100
        
        winners = res_df[res_df['win']]
        avg_mae = winners['mae_pct'].median() if not winners.empty else 0
        med_time = winners['time_mins'].median() if not winners.empty else 0
        
        bm = benchmarks.get(name, {'win':0, 'mae':0, 'time':0})
        
        row = f"| **{name}** | {total} | **{win_rate:.1f}%** | {bm['win']}% | {avg_mae:.1f}% | {bm['mae']}% | {med_time:.0f}m | {bm['time']}m |"
        lines.append(row)
        
    return "\n".join(lines)

if __name__ == "__main__":
    df = load_data()
    all_res = {}
    
    for name, p in STRATEGIES.items():
        res = analyze_strategy_vectorized(df, name, p['magic_h'], p['stop_h'])
        all_res[name] = res
        
    report = generate_report(all_res)
    out_path = os.path.join(OUTPUT_DIR, "MAGIC_HOUR_VALIDATION.md")
    with open(out_path, "w") as f:
        f.write(report)
    print(f"\nReport saved: {out_path}")
