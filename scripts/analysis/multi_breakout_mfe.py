"""
Multi-Breakout MFE Tracking
Tracks EVERY breakout's MFE, not just the max per day.

Logic:
1. Wait for price to break OR boundary
2. Track extension until price returns inside OR
3. Record the peak MFE and time for that breakout
4. Repeat for each new breakout
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import time
import pytz

DATA_PATH = 'data/NQ1_1m.parquet'
START_DATE = '2025-12-21'
END_DATE = '2026-01-14'
CUTOFF_TIME = time(12, 0)
OR_TIME = time(9, 30)
NY_TZ = pytz.timezone('America/New_York')

def load_data():
    df = pd.read_parquet(DATA_PATH)
    df.index = pd.to_datetime(df.index)
    if df.index.tz is None:
        df.index = df.index.tz_localize('UTC').tz_convert(NY_TZ)
    else:
        df.index = df.index.tz_convert(NY_TZ)
    df = df[(df.index.date >= pd.to_datetime(START_DATE).date()) & 
            (df.index.date <= pd.to_datetime(END_DATE).date())]
    return df

def calculate_multi_breakout_mfe(df):
    """
    Track EVERY breakout's MFE and time.
    A breakout starts when price crosses OR boundary.
    A breakout ends when price returns inside OR (or hits cutoff).
    """
    all_breakouts = []
    
    for date in df.index.normalize().unique():
        day_data = df[df.index.normalize() == date]
        
        # Get OR
        or_bars = day_data[day_data.index.time == OR_TIME]
        if len(or_bars) == 0:
            continue
        or_bar = or_bars.iloc[0]
        or_high = or_bar['high']
        or_low = or_bar['low']
        
        # Session data (after OR, up to cutoff)
        session = day_data[(day_data.index.time > OR_TIME) & 
                          (day_data.index.time <= CUTOFF_TIME)]
        
        if len(session) == 0:
            continue
        
        # State machine for tracking breakouts
        in_bull_breakout = False
        in_bear_breakout = False
        bull_breakout_mfe = 0.0
        bear_breakout_mfe = 0.0
        bull_breakout_start_time = 0
        bear_breakout_start_time = 0
        bull_peak_time = 0
        bear_peak_time = 0
        
        for idx, row in session.iterrows():
            mins_since_or = (idx.hour * 60 + idx.minute) - (9 * 60 + 30)
            
            # Check for bullish extension (high > OR high)
            ext_above = (row['high'] - or_high) / or_high * 100
            # Check for bearish extension (low < OR low)
            ext_below = (or_low - row['low']) / or_low * 100
            
            # Is price currently inside OR?
            price_inside_or = row['low'] >= or_low and row['high'] <= or_high
            
            # BULL BREAKOUT LOGIC
            if ext_above > 0:  # Price above OR high
                if not in_bull_breakout:
                    # Start new breakout
                    in_bull_breakout = True
                    bull_breakout_mfe = ext_above
                    bull_breakout_start_time = mins_since_or
                    bull_peak_time = mins_since_or
                else:
                    # Continue breakout, update if new max
                    if ext_above > bull_breakout_mfe:
                        bull_breakout_mfe = ext_above
                        bull_peak_time = mins_since_or
            elif in_bull_breakout and row['high'] <= or_high:
                # Breakout ended - price returned to OR
                all_breakouts.append({
                    'date': date.date(),
                    'direction': 'BULL',
                    'mfe': bull_breakout_mfe,
                    'start_time': bull_breakout_start_time,
                    'peak_time': bull_peak_time,
                    'end_time': mins_since_or
                })
                in_bull_breakout = False
                bull_breakout_mfe = 0.0
            
            # BEAR BREAKOUT LOGIC
            if ext_below > 0:  # Price below OR low
                if not in_bear_breakout:
                    # Start new breakout
                    in_bear_breakout = True
                    bear_breakout_mfe = ext_below
                    bear_breakout_start_time = mins_since_or
                    bear_peak_time = mins_since_or
                else:
                    # Continue breakout, update if new max
                    if ext_below > bear_breakout_mfe:
                        bear_breakout_mfe = ext_below
                        bear_peak_time = mins_since_or
            elif in_bear_breakout and row['low'] >= or_low:
                # Breakout ended - price returned to OR
                all_breakouts.append({
                    'date': date.date(),
                    'direction': 'BEAR',
                    'mfe': bear_breakout_mfe,
                    'start_time': bear_breakout_start_time,
                    'peak_time': bear_peak_time,
                    'end_time': mins_since_or
                })
                in_bear_breakout = False
                bear_breakout_mfe = 0.0
        
        # Close any open breakouts at cutoff
        if in_bull_breakout:
            all_breakouts.append({
                'date': date.date(),
                'direction': 'BULL',
                'mfe': bull_breakout_mfe,
                'start_time': bull_breakout_start_time,
                'peak_time': bull_peak_time,
                'end_time': 150  # Cutoff
            })
        if in_bear_breakout:
            all_breakouts.append({
                'date': date.date(),
                'direction': 'BEAR',
                'mfe': bear_breakout_mfe,
                'start_time': bear_breakout_start_time,
                'peak_time': bear_peak_time,
                'end_time': 150  # Cutoff
            })
    
    return pd.DataFrame(all_breakouts)

def plot_multi_breakout_time_distribution(breakouts_df, output_path='multi_breakout_time_dist.png'):
    """Plot time distribution using ALL breakout peak times."""
    fig, ax = plt.subplots(figsize=(14, 6))
    
    # Filter by direction
    bull_times = breakouts_df[breakouts_df['direction'] == 'BULL']['peak_time']
    bear_times = breakouts_df[breakouts_df['direction'] == 'BEAR']['peak_time']
    
    # 5-minute bins from minute 1 to 155
    bin_edges = list(range(1, 160, 5))
    
    bull_counts = []
    bear_counts = []
    for i in range(len(bin_edges) - 1):
        bin_start = bin_edges[i]
        bin_end = bin_edges[i + 1]
        bull_in_bin = ((bull_times >= bin_start) & (bull_times < bin_end)).sum()
        bear_in_bin = ((bear_times >= bin_start) & (bear_times < bin_end)).sum()
        bull_counts.append(bull_in_bin)
        bear_counts.append(bear_in_bin)
    
    x = np.arange(len(bin_edges) - 1)
    
    ax.bar(x, bull_counts, width=0.8, color='green', alpha=0.7, label=f'Bull ({len(bull_times)} breakouts)')
    ax.bar(x, [-c for c in bear_counts], width=0.8, color='red', alpha=0.7, label=f'Bear ({len(bear_times)} breakouts)')
    
    # Time labels
    x_labels = []
    for b in bin_edges[:-1]:
        hour = 9 + (30 + b) // 60
        minute = (30 + b) % 60
        x_labels.append(f"{hour:02d}:{minute:02d}")
    
    ax.set_xticks(x[::6])
    ax.set_xticklabels([x_labels[i] for i in range(0, len(x_labels), 6)], rotation=45)
    ax.axhline(0, color='white', linewidth=0.5)
    ax.set_xlabel('Peak Time (EST)')
    ax.set_ylabel('Breakout Count')
    ax.set_title(f'Multi-Breakout Time Distribution\n{len(bull_times)} Bull + {len(bear_times)} Bear = {len(breakouts_df)} Total Breakouts')
    ax.legend()
    ax.set_facecolor('black')
    fig.patch.set_facecolor('black')
    ax.tick_params(colors='white')
    ax.xaxis.label.set_color('white')
    ax.yaxis.label.set_color('white')
    ax.title.set_color('white')
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, facecolor='black')
    plt.close()
    print(f"Saved multi-breakout time distribution to {output_path}")

def main():
    print("="*60)
    print("Multi-Breakout MFE Analysis")
    print(f"Date Range: {START_DATE} to {END_DATE}")
    print("="*60)
    
    df = load_data()
    print(f"Loaded {len(df)} bars")
    
    breakouts = calculate_multi_breakout_mfe(df)
    print(f"\nFound {len(breakouts)} total breakouts")
    print(f"  Bull breakouts: {len(breakouts[breakouts['direction'] == 'BULL'])}")
    print(f"  Bear breakouts: {len(breakouts[breakouts['direction'] == 'BEAR'])}")
    
    print("\n" + "="*60)
    print("All Breakouts:")
    print("="*60)
    print(breakouts.to_string())
    
    # Stats
    print("\n" + "="*60)
    print("Summary Statistics:")
    print("="*60)
    bull = breakouts[breakouts['direction'] == 'BULL']
    bear = breakouts[breakouts['direction'] == 'BEAR']
    print(f"Bull MFE - Mean: {bull['mfe'].mean():.3f}%, Median: {bull['mfe'].median():.3f}%")
    print(f"Bear MFE - Mean: {bear['mfe'].mean():.3f}%, Median: {bear['mfe'].median():.3f}%")
    print(f"Bull Peak Time - Mean: {bull['peak_time'].mean():.1f}m, Median: {bull['peak_time'].median():.1f}m")
    print(f"Bear Peak Time - Mean: {bear['peak_time'].mean():.1f}m, Median: {bear['peak_time'].median():.1f}m")
    
    # Generate plots
    output_dir = 'docs/PackTrading/DailyNYlevels/verification'
    import os
    os.makedirs(output_dir, exist_ok=True)
    
    plot_multi_breakout_time_distribution(breakouts, f'{output_dir}/multi_breakout_time_dist.png')
    breakouts.to_csv(f'{output_dir}/multi_breakout_results.csv', index=False)
    print(f"\nSaved results to {output_dir}/")

if __name__ == "__main__":
    main()
