"""
Compare Two MFE Tracking Approaches:
1. Peak MFE per breakout (current implementation)
2. Every bar's extension (hypothesized reference behavior)

This will help determine which matches the reference indicator.
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

def approach_1_peak_mfe_per_breakout(df):
    """Current implementation: Track peak MFE per breakout."""
    all_mfe_bull = []
    all_mfe_bear = []
    all_time_bull = []
    all_time_bear = []
    
    for date in df.index.normalize().unique():
        day_data = df[df.index.normalize() == date]
        or_bars = day_data[day_data.index.time == OR_TIME]
        if len(or_bars) == 0:
            continue
        or_bar = or_bars.iloc[0]
        or_high = or_bar['high']
        or_low = or_bar['low']
        
        session = day_data[(day_data.index.time > OR_TIME) & 
                          (day_data.index.time <= CUTOFF_TIME)]
        
        in_bull = False
        in_bear = False
        cur_bull_mfe = 0.0
        cur_bear_mfe = 0.0
        cur_bull_time = 0
        cur_bear_time = 0
        
        for idx, row in session.iterrows():
            mins = (idx.hour * 60 + idx.minute) - (9 * 60 + 30)
            ext_above = (row['high'] - or_high) / or_high * 100
            ext_below = (or_low - row['low']) / or_low * 100
            
            # Bull breakout
            if ext_above > 0:
                if not in_bull:
                    in_bull = True
                    cur_bull_mfe = ext_above
                    cur_bull_time = mins
                elif ext_above > cur_bull_mfe:
                    cur_bull_mfe = ext_above
                    cur_bull_time = mins
            
            # End bull when close < OR low
            if in_bull and row['close'] < or_low:
                all_mfe_bull.append(cur_bull_mfe)
                all_time_bull.append(cur_bull_time)
                in_bull = False
                cur_bull_mfe = 0
            
            # Bear breakout
            if ext_below > 0:
                if not in_bear:
                    in_bear = True
                    cur_bear_mfe = ext_below
                    cur_bear_time = mins
                elif ext_below > cur_bear_mfe:
                    cur_bear_mfe = ext_below
                    cur_bear_time = mins
            
            # End bear when close > OR high
            if in_bear and row['close'] > or_high:
                all_mfe_bear.append(cur_bear_mfe)
                all_time_bear.append(cur_bear_time)
                in_bear = False
                cur_bear_mfe = 0
        
        # Close at cutoff
        if in_bull and cur_bull_mfe > 0:
            all_mfe_bull.append(cur_bull_mfe)
            all_time_bull.append(cur_bull_time)
        if in_bear and cur_bear_mfe > 0:
            all_mfe_bear.append(cur_bear_mfe)
            all_time_bear.append(cur_bear_time)
    
    return all_mfe_bull, all_mfe_bear, all_time_bull, all_time_bear

def approach_2_every_bar_extension(df):
    """Hypothesized reference: Track EVERY bar's extension."""
    all_ext_bull = []
    all_ext_bear = []
    all_time_bull = []
    all_time_bear = []
    
    for date in df.index.normalize().unique():
        day_data = df[df.index.normalize() == date]
        or_bars = day_data[day_data.index.time == OR_TIME]
        if len(or_bars) == 0:
            continue
        or_bar = or_bars.iloc[0]
        or_high = or_bar['high']
        or_low = or_bar['low']
        
        session = day_data[(day_data.index.time > OR_TIME) & 
                          (day_data.index.time <= CUTOFF_TIME)]
        
        for idx, row in session.iterrows():
            mins = (idx.hour * 60 + idx.minute) - (9 * 60 + 30)
            
            # Every bar that extends above OR high
            if row['high'] > or_high:
                ext = (row['high'] - or_high) / or_high * 100
                all_ext_bull.append(ext)
                all_time_bull.append(mins)
            
            # Every bar that extends below OR low
            if row['low'] < or_low:
                ext = (or_low - row['low']) / or_low * 100
                all_ext_bear.append(ext)
                all_time_bear.append(mins)
    
    return all_ext_bull, all_ext_bear, all_time_bull, all_time_bear

def plot_comparison(a1_bull, a1_bear, a2_bull, a2_bear, output_path):
    """Compare the two approaches side by side."""
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    
    # MFE Histograms
    bin_size = 0.04
    max_val = max(max(a1_bull + a1_bear), max(a2_bull + a2_bear)) if a1_bull and a2_bull else 1
    bins = np.arange(0, max_val + bin_size, bin_size)
    
    # Approach 1 - Peak MFE
    ax = axes[0, 0]
    ax.hist(a1_bull, bins=bins, orientation='horizontal', color='green', alpha=0.7, label=f'Bull ({len(a1_bull)})')
    ax.hist(a1_bear, bins=bins, orientation='horizontal', color='red', alpha=0.7, label=f'Bear ({len(a1_bear)})')
    ax.set_title(f'Approach 1: Peak MFE per Breakout\n{len(a1_bull)} Bull + {len(a1_bear)} Bear')
    ax.set_xlabel('Count')
    ax.set_ylabel('MFE %')
    ax.axhline(np.mean(a1_bull) if a1_bull else 0, color='lime', linestyle='--', label=f'Bull AVG: {np.mean(a1_bull):.3f}%' if a1_bull else 'N/A')
    ax.axhline(np.mean(a1_bear) if a1_bear else 0, color='salmon', linestyle='--', label=f'Bear AVG: {np.mean(a1_bear):.3f}%' if a1_bear else 'N/A')
    ax.legend(fontsize=8)
    ax.set_facecolor('black')
    ax.tick_params(colors='white')
    
    # Approach 2 - Every Bar
    ax = axes[0, 1]
    ax.hist(a2_bull, bins=bins, orientation='horizontal', color='green', alpha=0.7, label=f'Bull ({len(a2_bull)})')
    ax.hist(a2_bear, bins=bins, orientation='horizontal', color='red', alpha=0.7, label=f'Bear ({len(a2_bear)})')
    ax.set_title(f'Approach 2: Every Bar Extension\n{len(a2_bull)} Bull + {len(a2_bear)} Bear')
    ax.set_xlabel('Count')
    ax.set_ylabel('MFE %')
    ax.axhline(np.mean(a2_bull) if a2_bull else 0, color='lime', linestyle='--', label=f'Bull AVG: {np.mean(a2_bull):.3f}%' if a2_bull else 'N/A')
    ax.axhline(np.mean(a2_bear) if a2_bear else 0, color='salmon', linestyle='--', label=f'Bear AVG: {np.mean(a2_bear):.3f}%' if a2_bear else 'N/A')
    ax.legend(fontsize=8)
    ax.set_facecolor('black')
    ax.tick_params(colors='white')
    
    # Summary stats
    ax = axes[1, 0]
    ax.axis('off')
    stats_text = f"""
APPROACH 1: Peak MFE per Breakout
---------------------------------
Bull: {len(a1_bull)} samples
  Mean: {np.mean(a1_bull):.4f}%
  Median: {np.median(a1_bull):.4f}%
Bear: {len(a1_bear)} samples
  Mean: {np.mean(a1_bear):.4f}%
  Median: {np.median(a1_bear):.4f}%

APPROACH 2: Every Bar Extension
---------------------------------
Bull: {len(a2_bull)} samples
  Mean: {np.mean(a2_bull):.4f}%
  Median: {np.median(a2_bull):.4f}%
Bear: {len(a2_bear)} samples
  Mean: {np.mean(a2_bear):.4f}%
  Median: {np.median(a2_bear):.4f}%
"""
    ax.text(0.1, 0.5, stats_text, fontsize=12, family='monospace', 
            transform=ax.transAxes, verticalalignment='center', color='white')
    ax.set_facecolor('black')
    
    # Ratio comparison
    ax = axes[1, 1]
    ax.axis('off')
    ratio_text = f"""
DATA POINT RATIO:
Approach 2 has {len(a2_bull)/max(len(a1_bull),1):.1f}x more bull samples
Approach 2 has {len(a2_bear)/max(len(a1_bear),1):.1f}x more bear samples

If reference indicator shows denser histogram,
Approach 2 (every bar) is likely the correct method.
"""
    ax.text(0.1, 0.5, ratio_text, fontsize=12, family='monospace',
            transform=ax.transAxes, verticalalignment='center', color='white')
    ax.set_facecolor('black')
    
    fig.patch.set_facecolor('black')
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, facecolor='black')
    plt.close()
    print(f"Saved comparison to {output_path}")

def main():
    print("="*60)
    print("Comparing MFE Tracking Approaches")
    print("="*60)
    
    df = load_data()
    print(f"Loaded {len(df)} bars")
    
    print("\nApproach 1: Peak MFE per breakout...")
    a1_bull, a1_bear, a1_t_bull, a1_t_bear = approach_1_peak_mfe_per_breakout(df)
    print(f"  Bull samples: {len(a1_bull)}, Bear samples: {len(a1_bear)}")
    
    print("\nApproach 2: Every bar extension...")
    a2_bull, a2_bear, a2_t_bull, a2_t_bear = approach_2_every_bar_extension(df)
    print(f"  Bull samples: {len(a2_bull)}, Bear samples: {len(a2_bear)}")
    
    print("\n" + "="*60)
    print("Statistics Comparison:")
    print("="*60)
    print(f"Approach 1 (Peak MFE):")
    print(f"  Bull - Mean: {np.mean(a1_bull):.4f}%, Median: {np.median(a1_bull):.4f}%")
    print(f"  Bear - Mean: {np.mean(a1_bear):.4f}%, Median: {np.median(a1_bear):.4f}%")
    print(f"\nApproach 2 (Every Bar):")
    print(f"  Bull - Mean: {np.mean(a2_bull):.4f}%, Median: {np.median(a2_bull):.4f}%")
    print(f"  Bear - Mean: {np.mean(a2_bear):.4f}%, Median: {np.median(a2_bear):.4f}%")
    
    output_dir = 'docs/PackTrading/DailyNYlevels/verification'
    import os
    os.makedirs(output_dir, exist_ok=True)
    
    plot_comparison(a1_bull, a1_bear, a2_bull, a2_bear, 
                   f'{output_dir}/approach_comparison.png')

if __name__ == "__main__":
    main()
