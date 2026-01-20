"""
MFE/Time Distribution Analysis Script
Replicates the DailyNYLevelsV2.pine indicator logic in Python for verification.

Date Range: Dec 21, 2025 to Jan 14, 2026 (matching TradingView)
Cutoff: 12:00 PM EST
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, time
import pytz

# Configuration
DATA_PATH = 'data/NQ1_1m.parquet'
START_DATE = '2025-12-21'
END_DATE = '2026-01-14'
CUTOFF_TIME = time(12, 0)  # 12:00 PM EST
OR_TIME = time(9, 30)  # Opening Range time
NY_TZ = pytz.timezone('America/New_York')

def load_data():
    """Load NQ 1-minute data and filter to date range."""
    df = pd.read_parquet(DATA_PATH)
    
    # Ensure datetime index
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    
    # Localize to NY timezone if needed
    if df.index.tz is None:
        df.index = df.index.tz_localize('UTC').tz_convert(NY_TZ)
    else:
        df.index = df.index.tz_convert(NY_TZ)
    
    # Filter to date range
    df = df[(df.index.date >= pd.to_datetime(START_DATE).date()) & 
            (df.index.date <= pd.to_datetime(END_DATE).date())]
    
    print(f"Loaded {len(df)} bars from {df.index.min()} to {df.index.max()}")
    return df

def get_trading_days(df):
    """Get unique trading days."""
    return df.index.date
    
def calculate_daily_mfe(df):
    """
    Calculate MFE and peak times for each trading day.
    Replicates the PineScript indicator logic.
    """
    results = []
    
    # Group by date
    for date in df.index.normalize().unique():
        day_data = df[df.index.normalize() == date]
        
        # Find 09:30 bar (Opening Range)
        or_bars = day_data[day_data.index.time == OR_TIME]
        if len(or_bars) == 0:
            continue
            
        or_bar = or_bars.iloc[0]
        or_high = or_bar['high']
        or_low = or_bar['low']
        
        # Filter to 09:31 - 12:00 (after OR, before cutoff)
        session_data = day_data[(day_data.index.time > OR_TIME) & 
                                 (day_data.index.time <= CUTOFF_TIME)]
        
        if len(session_data) == 0:
            continue
        
        # Calculate MFE for each bar
        daily_mfe_bull = 0.0
        daily_mfe_bear = 0.0
        daily_peak_time_bull = 0
        daily_peak_time_bear = 0
        
        for idx, row in session_data.iterrows():
            # Extension above OR high (as percentage)
            cur_ext_above = (row['high'] - or_high) / or_high * 100
            # Extension below OR low (as percentage)
            cur_ext_below = (or_low - row['low']) / or_low * 100
            
            # Minutes since 09:30
            minutes_since_or = (idx.hour * 60 + idx.minute) - (9 * 60 + 30)
            
            # Track max extension above OR (only if positive)
            if cur_ext_above > 0 and cur_ext_above > daily_mfe_bull:
                daily_mfe_bull = cur_ext_above
                daily_peak_time_bull = minutes_since_or
            
            # Track max extension below OR (only if positive)
            if cur_ext_below > 0 and cur_ext_below > daily_mfe_bear:
                daily_mfe_bear = cur_ext_below
                daily_peak_time_bear = minutes_since_or
        
        results.append({
            'date': date.date(),
            'or_high': or_high,
            'or_low': or_low,
            'mfe_bull': daily_mfe_bull,
            'mfe_bear': daily_mfe_bear,
            'peak_time_bull': daily_peak_time_bull,
            'peak_time_bear': daily_peak_time_bear
        })
    
    return pd.DataFrame(results)

def plot_mfe_histogram(df_results, output_path='mfe_histogram.png'):
    """Plot MFE distribution histogram (matching indicator style)."""
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Bin size 0.04% as in indicator
    bin_size = 0.04
    max_mfe = max(df_results['mfe_bull'].max(), df_results['mfe_bear'].max())
    bins = np.arange(0, max_mfe + bin_size, bin_size)
    
    # Create histogram data
    bull_counts, _ = np.histogram(df_results['mfe_bull'], bins=bins)
    bear_counts, _ = np.histogram(df_results['mfe_bear'], bins=bins)
    
    # Plot
    bar_width = bin_size * 0.4
    x = bins[:-1]
    
    ax.barh(x, bull_counts, height=bar_width, color='green', alpha=0.7, label='Bull (Above OR)')
    ax.barh(x, -bear_counts, height=bar_width, color='red', alpha=0.7, label='Bear (Below OR)')
    
    # Add percentile lines
    for pct in [20, 50, 80]:
        bull_pct = np.percentile(df_results['mfe_bull'], pct)
        bear_pct = np.percentile(df_results['mfe_bear'], pct)
        ax.axhline(bull_pct, color='white', linestyle='--', alpha=0.5)
        ax.axhline(bear_pct, color='white', linestyle='--', alpha=0.5)
    
    # Stats
    avg_bull = df_results['mfe_bull'].mean()
    avg_bear = df_results['mfe_bear'].mean()
    
    ax.set_xlabel('Count')
    ax.set_ylabel('MFE (%)')
    ax.set_title(f'MFE Distribution - {len(df_results)} Days\n'
                 f'Bull AVG: {avg_bull:.2f}% | Bear AVG: {avg_bear:.2f}%')
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
    print(f"Saved MFE histogram to {output_path}")

def plot_time_distribution(df_results, output_path='time_distribution.png'):
    """Plot time distribution histogram (matching indicator style)."""
    fig, ax = plt.subplots(figsize=(14, 6))
    
    # 5-minute bins from minute 1 to 155
    bin_edges = list(range(1, 160, 5))  # 1-5, 6-10, ... 151-155
    
    # Count peaks in each bin
    bull_counts = []
    bear_counts = []
    
    for i in range(len(bin_edges) - 1):
        bin_start = bin_edges[i]
        bin_end = bin_edges[i + 1]
        
        bull_in_bin = ((df_results['peak_time_bull'] >= bin_start) & 
                       (df_results['peak_time_bull'] < bin_end)).sum()
        bear_in_bin = ((df_results['peak_time_bear'] >= bin_start) & 
                       (df_results['peak_time_bear'] < bin_end)).sum()
        
        bull_counts.append(bull_in_bin)
        bear_counts.append(bear_in_bin)
    
    # Convert to time labels
    x_labels = []
    for b in bin_edges[:-1]:
        hour = 9 + (30 + b) // 60
        minute = (30 + b) % 60
        x_labels.append(f"{hour:02d}:{minute:02d}")
    
    x = np.arange(len(x_labels))
    bar_width = 0.35
    
    # Plot mirrored histogram (bull up, bear down)
    ax.bar(x, bull_counts, width=bar_width * 2, color='green', alpha=0.7, label='Bull Peak Times')
    ax.bar(x, [-c for c in bear_counts], width=bar_width * 2, color='red', alpha=0.7, label='Bear Peak Times')
    
    # Add AVG and Median lines
    avg_bull = df_results['peak_time_bull'].mean()
    med_bull = df_results['peak_time_bull'].median()
    avg_bear = df_results['peak_time_bear'].mean()
    med_bear = df_results['peak_time_bear'].median()
    
    # Convert to x position
    avg_bull_x = (avg_bull - 1) / 5
    med_bull_x = (med_bull - 1) / 5
    avg_bear_x = (avg_bear - 1) / 5
    med_bear_x = (med_bear - 1) / 5
    
    ax.axvline(avg_bull_x, color='yellow', linestyle='--', alpha=0.8, label=f'Bull AVG ({int(avg_bull)}m)')
    ax.axvline(med_bull_x, color='cyan', linestyle='--', alpha=0.8, label=f'Bull MED ({int(med_bull)}m)')
    ax.axvline(avg_bear_x, color='yellow', linestyle=':', alpha=0.8, label=f'Bear AVG ({int(avg_bear)}m)')
    ax.axvline(med_bear_x, color='cyan', linestyle=':', alpha=0.8, label=f'Bear MED ({int(med_bear)}m)')
    
    # Formatting
    ax.set_xticks(x[::6])  # Show every 6th label (30 min intervals)
    ax.set_xticklabels([x_labels[i] for i in range(0, len(x_labels), 6)], rotation=45)
    ax.axhline(0, color='white', linewidth=0.5)
    ax.set_xlabel('Time (EST)')
    ax.set_ylabel('Count')
    ax.set_title(f'MFE Time Distribution - {len(df_results)} Days\n'
                 f'Bull AVG: {int(avg_bull)}m | Bear AVG: {int(avg_bear)}m')
    ax.legend(loc='upper right', fontsize=8)
    ax.set_facecolor('black')
    fig.patch.set_facecolor('black')
    ax.tick_params(colors='white')
    ax.xaxis.label.set_color('white')
    ax.yaxis.label.set_color('white')
    ax.title.set_color('white')
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, facecolor='black')
    plt.close()
    print(f"Saved time distribution to {output_path}")

def main():
    print("="*60)
    print("MFE/Time Distribution Analysis")
    print(f"Date Range: {START_DATE} to {END_DATE}")
    print(f"Cutoff Time: {CUTOFF_TIME}")
    print("="*60)
    
    # Load data
    df = load_data()
    
    # Calculate daily MFE
    results = calculate_daily_mfe(df)
    print(f"\nProcessed {len(results)} trading days")
    
    # Show results table
    print("\n" + "="*60)
    print("Daily MFE Results:")
    print("="*60)
    print(results.to_string())
    
    # Summary stats
    print("\n" + "="*60)
    print("Summary Statistics:")
    print("="*60)
    print(f"Bull MFE - Mean: {results['mfe_bull'].mean():.3f}%, Median: {results['mfe_bull'].median():.3f}%")
    print(f"Bear MFE - Mean: {results['mfe_bear'].mean():.3f}%, Median: {results['mfe_bear'].median():.3f}%")
    print(f"Bull Peak Time - Mean: {results['peak_time_bull'].mean():.1f}m, Median: {results['peak_time_bull'].median():.1f}m")
    print(f"Bear Peak Time - Mean: {results['peak_time_bear'].mean():.1f}m, Median: {results['peak_time_bear'].median():.1f}m")
    
    # Generate plots
    output_dir = 'docs/PackTrading/DailyNYlevels/verification'
    import os
    os.makedirs(output_dir, exist_ok=True)
    
    plot_mfe_histogram(results, f'{output_dir}/mfe_histogram_{START_DATE}_to_{END_DATE}.png')
    plot_time_distribution(results, f'{output_dir}/time_distribution_{START_DATE}_to_{END_DATE}.png')
    
    # Save results to CSV
    results.to_csv(f'{output_dir}/mfe_results_{START_DATE}_to_{END_DATE}.csv', index=False)
    print(f"\nSaved results to {output_dir}/")

if __name__ == "__main__":
    main()
