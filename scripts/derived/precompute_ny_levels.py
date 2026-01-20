"""
Precompute NY Levels Statistics (MFE and Time Distributions).

Analyzes the 09:30-12:00 window to find:
1. Max Favorable Excursion (MFE) % from 9:30 OR high/low.
2. The exact time the peak MFE occurred.
3. Distribution of these values across all historical days.

Output: data/{ticker}_ny_levels_stats.json
"""

import pandas as pd
import numpy as np
import json
import pytz
from datetime import datetime, time
from pathlib import Path
import sys

# Data directory
DATA_DIR = Path("data")
NY_TZ = pytz.timezone("America/New_York")

def load_1m_data(ticker: str) -> pd.DataFrame:
    parquet_path = DATA_DIR / f"{ticker}_1m.parquet"
    if not parquet_path.exists():
        raise FileNotFoundError(f"Data file not found: {parquet_path}")
    
    df = pd.read_parquet(parquet_path)
    if 'time' in df.columns:
        if df['time'].dtype == 'int64':
            df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
        df['datetime'] = df['time']
    
    if df['datetime'].dt.tz is None:
        df['datetime'] = df['datetime'].dt.tz_localize('UTC')
    df['datetime'] = df['datetime'].dt.tz_convert(NY_TZ)
    df['time_only'] = df['datetime'].dt.time
    df['date'] = df['datetime'].dt.date
    
    return df

def analyze_ny_levels(df: pd.DataFrame, grouping='D'):
    daily_stats = []
    
    for date_obj, day_df in df.groupby('date'):
        # 9:30 candle for reference (1m)
        or_row = day_df[day_df['time_only'] == time(9, 30)]
        if or_row.empty: continue
        
        row_ref = or_row.iloc[0]
        o_ref = row_ref['open']
        h_ref = row_ref['high']
        l_ref = row_ref['low']
        
        # Window: 09:30 - 12:00
        window = day_df[(day_df['time_only'] >= time(9, 30)) & (day_df['time_only'] <= time(12, 0))]
        if window.empty: continue
        
        # MFE Calculation
        max_h = window['high'].max()
        min_l = window['low'].min()
        
        # Time of peaks
        peak_h_row = window[window['high'] == max_h].iloc[0]
        peak_l_row = window[window['low'] == min_l].iloc[0]
        
        mfe_bull_pts = max(0, max_h - h_ref)
        mfe_bear_pts = max(0, l_ref - min_l)
        
        daily_stats.append({
            'datetime': row_ref['datetime'],
            'date': str(date_obj),
            'mfe_bull_pct': round(mfe_bull_pts / o_ref * 100, 4),
            'mfe_bear_pct': round(mfe_bear_pts / o_ref * 100, 4),
            'time_of_peak_h': peak_h_row['datetime'].strftime('%H:%M'),
            'time_of_peak_l': peak_l_row['datetime'].strftime('%H:%M')
        })
        
    if not daily_stats:
        return None

    stats_df = pd.DataFrame(daily_stats)
    
    # Process Grouping
    if grouping == 'D':
        return compute_dist_stats(stats_df)
    
    # Add grouping column
    if grouping == 'M':
        stats_df['group'] = stats_df['datetime'].dt.to_period('M').astype(str)
    elif grouping == 'Q':
        stats_df['group'] = stats_df['datetime'].dt.to_period('Q').astype(str)
    elif grouping == 'Y':
        stats_df['group'] = stats_df['datetime'].dt.to_period('Y').astype(str)
    else:
        return compute_dist_stats(stats_df)
        
    grouped_results = {}
    for group_name, group_data in stats_df.groupby('group'):
        grouped_results[group_name] = compute_dist_stats(group_data)
        
    return grouped_results

def compute_dist_stats(df: pd.DataFrame):
    percentiles = list(range(2, 100, 2))
    
    return {
        'bull_mfe_dist': {str(p): round(df['mfe_bull_pct'].quantile(p/100), 4) for p in percentiles},
        'bear_mfe_dist': {str(p): round(df['mfe_bear_pct'].quantile(p/100), 4) for p in percentiles},
        'time_dist_bull': df['time_of_peak_h'].value_counts().sort_index().to_dict(),
        'time_dist_bear': df['time_of_peak_l'].value_counts().sort_index().to_dict(),
        'median_peak_time_bull': df['time_of_peak_h'].mode()[0] if not df['time_of_peak_h'].empty else None,
        'median_peak_time_bear': df['time_of_peak_l'].mode()[0] if not df['time_of_peak_l'].empty else None,
        'count': len(df)
    }

def precompute_ny_levels(ticker: str, grouping='D'):
    print(f"Processing NY Levels for {ticker} (Grouping: {grouping})...")
    try:
        df = load_1m_data(ticker)
        stats = analyze_ny_levels(df, grouping)
        if stats:
            suffix = f"_{grouping}" if grouping != 'D' else ""
            output_file = DATA_DIR / f"{ticker}_ny_levels_stats{suffix}.json"
            with open(output_file, 'w') as f:
                json.dump(stats, f, indent=2)
            print(f"  Saved to {output_file}")
    except Exception as e:
        print(f"  Error: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--grouping", choices=['D', 'M', 'Q', 'Y'], default='D', help="Grouping period (Daily, Monthly, Quarterly, Yearly)")
    args = parser.parse_args()
    
    tickers = ["ES1", "NQ1", "CL1", "GC1", "RTY1", "YM1"]
    for t in tickers:
        precompute_ny_levels(t, args.grouping)
