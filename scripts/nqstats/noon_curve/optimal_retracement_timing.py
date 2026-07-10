"""
Optimal Retracement Timing Analysis

Analyzes WHEN successful retracements occur and how deep they should be.

Key Questions:
1. What TIME do successful retracements happen? (10 AM, 11 AM, 12 PM?)
2. How DEEP should the retrace be? (20%, 30%, 40%?)
3. What's the optimal entry window for retracement entries?
4. Should we wait for price to RECOVER from the retrace before entering?

Goal: Find the sweet spot for retracement entries using median time analysis.
"""

import pandas as pd
import numpy as np
from datetime import time, datetime, timedelta
import pytz

# --- Configuration ---
TICKERS = ['NQ1', 'ES1']
DATA_DIR = 'data'
START_YEAR = 2020
END_YEAR = 2025

# Session Times (America/New_York)
SESSION_START = time(8, 0)
NOON = time(12, 0)
SESSION_END = time(16, 0)

def load_data(ticker):
    """Load 1-minute parquet data and convert to EST."""
    path = f"{DATA_DIR}/{ticker}_1m.parquet"
    
    try:
        df = pd.read_parquet(path)
        
        if 'time' in df.columns:
            df['datetime'] = pd.to_datetime(df['time'], unit='s', utc=True)
            df = df.set_index('datetime', inplace=False)
        
        df = df.tz_convert('America/New_York')
        
        print(f"✓ Loaded {ticker}: {len(df)} bars")
        return df
    except Exception as e:
        print(f"Error loading {ticker}: {e}")
        return None


def analyze_retracement_timing(ticker):
    """
    Analyze when and how retracements occur for winning vs losing setups.
    
    Focus:
    - Time of maximum retracement
    - Depth of retracement
    - Recovery timing (when price bounces back)
    - Success rate by retrace depth and timing
    """
    df = load_data(ticker)
    if df is None:
        return None
    
    df = df[(df.index.year >= START_YEAR) & (df.index.year <= END_YEAR)]
    
    print(f"\n{'='*80}")
    print(f"RETRACEMENT TIMING ANALYSIS: {ticker} ({START_YEAR}-{END_YEAR})")
    print(f"{'='*80}")
    
    daily_groups = df.groupby(df.index.date)
    results = []
    
    for date, day_data in daily_groups:
        # 1. AM Session (08:00-12:00)
        am_data = day_data.between_time(SESSION_START, NOON, inclusive='left')
        if len(am_data) < 60:
            continue
        
        am_high_price = am_data['high'].max()
        am_low_price = am_data['low'].min()
        am_high_idx = am_data['high'].idxmax()
        am_low_idx = am_data['low'].idxmin()
        am_range = am_high_price - am_low_price
        
        if am_range == 0:
            continue
        
        # Determine direction
        if am_high_idx > am_low_idx:
            direction = 'BULL'  # High made last, expect continuation up
            am_extreme = am_high_price
            am_extreme_time = am_high_idx
        elif am_low_idx > am_high_idx:
            direction = 'BEAR'  # Low made last, expect continuation down
            am_extreme = am_low_price
            am_extreme_time = am_low_idx
        else:
            continue
        
        # Time gap filter (120-240 minutes)
        time_gap_minutes = abs((am_high_idx - am_low_idx).total_seconds() / 60)
        if time_gap_minutes < 120 or time_gap_minutes > 240:
            continue  # Only analyze high-probability setups
        
        # 2. Post-Extreme Analysis (10:00-14:00 window)
        # Track retracement from the AM extreme
        post_extreme_start = max(am_extreme_time, day_data.index[day_data.index.time >= time(10, 0)][0])
        post_extreme_end = day_data.index[day_data.index.time <= time(14, 0)][-1]
        post_extreme_data = day_data[post_extreme_start:post_extreme_end]
        
        if len(post_extreme_data) == 0:
            continue
        
        # Track maximum retracement
        if direction == 'BULL':
            # For bullish, track how far price pulls back from AM high
            lowest_after_extreme = post_extreme_data['low'].min()
            lowest_after_extreme_time = post_extreme_data['low'].idxmin()
            retrace_points = am_high_price - lowest_after_extreme
            retrace_pct = (retrace_points / am_range) * 100  # % of AM range
            
            # Find recovery (back above 30% retrace level)
            target_recovery = am_high_price - (am_range * 0.30)
            recovery_data = post_extreme_data[post_extreme_data.index > lowest_after_extreme_time]
            recovery_time = None
            if len(recovery_data) > 0:
                recovery_bars = recovery_data[recovery_data['close'] > target_recovery]
                if len(recovery_bars) > 0:
                    recovery_time = recovery_bars.index[0]
            
        else:  # BEAR
            # For bearish, track how far price rallies from AM low
            highest_after_extreme = post_extreme_data['high'].max()
            highest_after_extreme_time = post_extreme_data['high'].idxmax()
            retrace_points = highest_after_extreme - am_low_price
            retrace_pct = (retrace_points / am_range) * 100
            
            # Find recovery (back below 30% retrace level)
            target_recovery = am_low_price + (am_range * 0.30)
            recovery_data = post_extreme_data[post_extreme_data.index > highest_after_extreme_time]
            recovery_time = None
            if len(recovery_data) > 0:
                recovery_bars = recovery_data[recovery_data['close'] < target_recovery]
                if len(recovery_bars) > 0:
                    recovery_time = recovery_bars.index[0]
        
        # 3. PM Outcome (12:00-16:00)
        pm_data = day_data.between_time(NOON, SESSION_END, inclusive='left')
        if len(pm_data) < 60:
            continue
        
        pm_high = pm_data['high'].max()
        pm_low = pm_data['low'].min()
        
        new_pm_high = pm_high > am_high_price
        new_pm_low = pm_low < am_low_price
        
        if new_pm_high and not new_pm_low:
            outcome = 'BULL'
        elif new_pm_low and not new_pm_high:
            outcome = 'BEAR'
        elif new_pm_high and new_pm_low:
            pm_high_time = pm_data['high'].idxmax()
            pm_low_time = pm_data['low'].idxmin()
            outcome = 'BULL' if pm_high_time < pm_low_time else 'BEAR'
        else:
            outcome = 'NONE'
        
        prediction_correct = (direction == outcome)
        
        # Calculate entry window states
        retrace_time = lowest_after_extreme_time if direction == 'BULL' else highest_after_extreme_time
        retrace_hour = retrace_time.hour + retrace_time.minute / 60.0
        
        # Categorize retrace depth
        if retrace_pct < 20:
            retrace_depth = 'SHALLOW (<20%)'
        elif retrace_pct < 38:
            retrace_depth = 'LIGHT (20-38%)'
        elif retrace_pct < 50:
            retrace_depth = 'MEDIUM (38-50%)'
        elif retrace_pct < 62:
            retrace_depth = 'DEEP (50-62%)'
        else:
            retrace_depth = 'VERY_DEEP (>62%)'
        
        # Categorize retrace time
        if retrace_hour < 10.5:
            retrace_time_bin = '10:00-10:30'
        elif retrace_hour < 11.0:
            retrace_time_bin = '10:30-11:00'
        elif retrace_hour < 11.5:
            retrace_time_bin = '11:00-11:30'
        elif retrace_hour < 12.0:
            retrace_time_bin = '11:30-12:00'
        elif retrace_hour < 12.5:
            retrace_time_bin = '12:00-12:30'
        elif retrace_hour < 13.0:
            retrace_time_bin = '12:30-13:00'
        elif retrace_hour < 13.5:
            retrace_time_bin = '13:00-13:30'
        else:
            retrace_time_bin = '13:30-14:00'
        
        # Recovery timing
        recovery_minutes = None
        if recovery_time:
            recovery_minutes = (recovery_time - retrace_time).total_seconds() / 60
        
        results.append({
            'Date': date,
            'Direction': direction,
            'Outcome': outcome,
            'Correct': prediction_correct,
            'AM_Extreme_Time': am_extreme_time.time(),
            'AM_Extreme_Hour': am_extreme_time.hour + am_extreme_time.minute / 60.0,
            'Retrace_Time': retrace_time.time(),
            'Retrace_Hour': retrace_hour,
            'Retrace_Time_Bin': retrace_time_bin,
            'Retrace_Pct': retrace_pct,
            'Retrace_Depth': retrace_depth,
            'Recovery_Time': recovery_time.time() if recovery_time else None,
            'Recovery_Minutes': recovery_minutes,
            'AM_Range': am_range,
            'Time_Gap_Minutes': time_gap_minutes,
        })
    
    return pd.DataFrame(results)


def print_analysis(df, ticker):
    """Print comprehensive retracement timing analysis."""
    if df is None or len(df) == 0:
        print(f"No data for {ticker}")
        return
    
    print(f"\n{'='*80}")
    print(f"RESULTS: {ticker}")
    print(f"{'='*80}")
    print(f"Sample Size: {len(df)} trading days (with 2-4 hour time gaps)")
    print(f"Period: {df['Date'].min()} to {df['Date'].max()}")
    
    total = len(df)
    correct = df['Correct'].sum()
    accuracy = (correct / total * 100) if total > 0 else 0
    print(f"\nBaseline Accuracy: {accuracy:.2f}% ({correct}/{total})")
    
    # ===== ANALYSIS 1: Accuracy by Retrace Depth =====
    print(f"\n{'─'*80}")
    print("ANALYSIS 1: ACCURACY BY RETRACEMENT DEPTH")
    print(f"{'─'*80}")
    
    depth_order = ['SHALLOW (<20%)', 'LIGHT (20-38%)', 'MEDIUM (38-50%)', 'DEEP (50-62%)', 'VERY_DEEP (>62%)']
    for depth in depth_order:
        subset = df[df['Retrace_Depth'] == depth]
        if len(subset) > 0:
            acc = (subset['Correct'].sum() / len(subset)) * 100
            pct_of_total = (len(subset) / total) * 100
            median_retrace = subset['Retrace_Pct'].median()
            marker = ' ⭐' if acc > 75 else ' ✓' if acc > 65 else ''
            print(f"  {depth:>20}: {acc:5.1f}% accuracy | {len(subset):4d} days ({pct_of_total:4.1f}%) | Median: {median_retrace:.1f}%{marker}")
    
    # ===== ANALYSIS 2: Accuracy by Retrace Timing =====
    print(f"\n{'─'*80}")
    print("ANALYSIS 2: ACCURACY BY RETRACEMENT TIMING")
    print(f"{'─'*80}")
    
    time_bin_order = ['10:00-10:30', '10:30-11:00', '11:00-11:30', '11:30-12:00', 
                      '12:00-12:30', '12:30-13:00', '13:00-13:30', '13:30-14:00']
    for time_bin in time_bin_order:
        subset = df[df['Retrace_Time_Bin'] == time_bin]
        if len(subset) > 0:
            acc = (subset['Correct'].sum() / len(subset)) * 100
            pct_of_total = (len(subset) / total) * 100
            median_depth = subset['Retrace_Pct'].median()
            marker = ' ⭐' if acc > 75 else ' ✓' if acc > 65 else ''
            print(f"  {time_bin}: {acc:5.1f}% accuracy | {len(subset):4d} days ({pct_of_total:4.1f}%) | Median depth: {median_depth:.1f}%{marker}")
    
    # ===== ANALYSIS 3: Combined - Depth + Timing Grid =====
    print(f"\n{'─'*80}")
    print("ANALYSIS 3: OPTIMAL ENTRY ZONES (Depth × Timing)")
    print(f"{'─'*80}")
    print(f"{'Time Window':<15} | {'Shallow':<8} | {'Light':<8} | {'Medium':<8} | {'Deep':<8}")
    print(f"{'─'*80}")
    
    for time_bin in ['10:00-11:00', '11:00-12:00', '12:00-13:00', '13:00-14:00']:
        # Combine bins
        if time_bin == '10:00-11:00':
            time_subset = df[df['Retrace_Time_Bin'].isin(['10:00-10:30', '10:30-11:00'])]
        elif time_bin == '11:00-12:00':
            time_subset = df[df['Retrace_Time_Bin'].isin(['11:00-11:30', '11:30-12:00'])]
        elif time_bin == '12:00-13:00':
            time_subset = df[df['Retrace_Time_Bin'].isin(['12:00-12:30', '12:30-13:00'])]
        else:
            time_subset = df[df['Retrace_Time_Bin'].isin(['13:00-13:30', '13:30-14:00'])]
        
        row = f"{time_bin:<15} |"
        
        # Shallow
        subset = time_subset[time_subset['Retrace_Depth'] == 'SHALLOW (<20%)']
        acc_str = f"{(subset['Correct'].sum() / len(subset) * 100):.0f}%({len(subset)})" if len(subset) > 0 else "-"
        row += f" {acc_str:>8} |"
        
        # Light
        subset = time_subset[time_subset['Retrace_Depth'] == 'LIGHT (20-38%)']
        acc_str = f"{(subset['Correct'].sum() / len(subset) * 100):.0f}%({len(subset)})" if len(subset) > 0 else "-"
        row += f" {acc_str:>8} |"
        
        # Medium
        subset = time_subset[time_subset['Retrace_Depth'] == 'MEDIUM (38-50%)']
        acc_str = f"{(subset['Correct'].sum() / len(subset) * 100):.0f}%({len(subset)})" if len(subset) > 0 else "-"
        row += f" {acc_str:>8} |"
        
        # Deep
        subset = time_subset[time_subset['Retrace_Depth'].isin(['DEEP (50-62%)', 'VERY_DEEP (>62%)'])]
        acc_str = f"{(subset['Correct'].sum() / len(subset) * 100):.0f}%({len(subset)})" if len(subset) > 0 else "-"
        row += f" {acc_str:>8}"
        
        print(row)
    
    # ===== ANALYSIS 4: Recovery Timing =====
    print(f"\n{'─'*80}")
    print("ANALYSIS 4: RECOVERY TIMING (Time to bounce back from retrace)")
    print(f"{'─'*80}")
    
    has_recovery = df[df['Recovery_Minutes'].notna()]
    print(f"Days with recovery: {len(has_recovery)} ({len(has_recovery)/total*100:.1f}%)")
    
    if len(has_recovery) > 0:
        print(f"\nRecovery time statistics:")
        print(f"  Median: {has_recovery['Recovery_Minutes'].median():.0f} minutes")
        print(f"  Mean: {has_recovery['Recovery_Minutes'].mean():.0f} minutes")
        print(f"  25th percentile: {has_recovery['Recovery_Minutes'].quantile(0.25):.0f} minutes")
        print(f"  75th percentile: {has_recovery['Recovery_Minutes'].quantile(0.75):.0f} minutes")
        
        # Accuracy by recovery speed
        fast_recovery = has_recovery[has_recovery['Recovery_Minutes'] <= 30]
        slow_recovery = has_recovery[has_recovery['Recovery_Minutes'] > 30]
        
        print(f"\nAccuracy by recovery speed:")
        if len(fast_recovery) > 0:
            acc = (fast_recovery['Correct'].sum() / len(fast_recovery)) * 100
            print(f"  Fast recovery (≤30 min): {acc:.1f}% ({len(fast_recovery)} days)")
        if len(slow_recovery) > 0:
            acc = (slow_recovery['Correct'].sum() / len(slow_recovery)) * 100
            print(f"  Slow recovery (>30 min): {acc:.1f}% ({len(slow_recovery)} days)")
    
    # ===== ANALYSIS 5: Directional Bias =====
    print(f"\n{'─'*80}")
    print("ANALYSIS 5: DIRECTIONAL BIAS (Bull vs Bear)")
    print(f"{'─'*80}")
    
    for direction in ['BULL', 'BEAR']:
        subset = df[df['Direction'] == direction]
        if len(subset) > 0:
            acc = (subset['Correct'].sum() / len(subset)) * 100
            median_depth = subset['Retrace_Pct'].median()
            median_time = subset['Retrace_Hour'].median()
            
            print(f"\n{direction} Setups: {acc:.1f}% accuracy ({len(subset)} days)")
            print(f"  Median retrace depth: {median_depth:.1f}%")
            print(f"  Median retrace time: {median_time:.1f} hours")
            
            # Best zones for this direction
            shallow = subset[subset['Retrace_Depth'].isin(['SHALLOW (<20%)', 'LIGHT (20-38%)'])]
            early = subset[subset['Retrace_Time_Bin'].isin(['10:00-10:30', '10:30-11:00', '11:00-11:30'])]
            
            if len(shallow) > 0:
                acc_shallow = (shallow['Correct'].sum() / len(shallow)) * 100
                print(f"  Shallow retraces (<38%): {acc_shallow:.1f}% accuracy ({len(shallow)} days)")
            
            if len(early) > 0:
                acc_early = (early['Correct'].sum() / len(early)) * 100
                print(f"  Early retraces (10-11:30 AM): {acc_early:.1f}% accuracy ({len(early)} days)")
    
    # ===== RECOMMENDATIONS =====
    print(f"\n{'='*80}")
    print("STRATEGY RECOMMENDATIONS")
    print(f"{'='*80}")
    
    # Find optimal zones
    shallow_early = df[
        (df['Retrace_Depth'].isin(['SHALLOW (<20%)', 'LIGHT (20-38%)'])) &
        (df['Retrace_Time_Bin'].isin(['10:00-10:30', '10:30-11:00', '11:00-11:30', '11:30-12:00']))
    ]
    
    if len(shallow_early) > 0:
        acc = (shallow_early['Correct'].sum() / len(shallow_early)) * 100
        median_retrace = shallow_early['Retrace_Pct'].median()
        median_time = shallow_early['Retrace_Hour'].median()
        
        print(f"\n🎯 OPTIMAL ENTRY ZONE:")
        print(f"   Condition: Shallow retraces (<38%) in 10:00-12:00 window")
        print(f"   Accuracy: {acc:.1f}%")
        print(f"   Sample size: {len(shallow_early)} days ({len(shallow_early)/total*100:.1f}% of all days)")
        print(f"   Median retrace depth: {median_retrace:.1f}%")
        print(f"   Median retrace time: {int(median_time)}:{int((median_time % 1) * 60):02d}")
    
    # Deep retraces (avoid)
    deep_late = df[
        (df['Retrace_Depth'].isin(['DEEP (50-62%)', 'VERY_DEEP (>62%)'])) |
        (df['Retrace_Time_Bin'].isin(['12:30-13:00', '13:00-13:30', '13:30-14:00']))
    ]
    
    if len(deep_late) > 0:
        acc = (deep_late['Correct'].sum() / len(deep_late)) * 100
        print(f"\n❌ AVOID ZONE:")
        print(f"   Condition: Deep retraces (>50%) OR late retraces (>12:30)")
        print(f"   Accuracy: {acc:.1f}%")
        print(f"   Sample size: {len(deep_late)} days")
    
    return df


def main():
    """Main analysis runner."""
    print("="*80)
    print("OPTIMAL RETRACEMENT TIMING ANALYSIS")
    print("="*80)
    print(f"Goal: Find when and how deep successful retracements occur")
    print(f"Period: {START_YEAR}-{END_YEAR}")
    print(f"Filter: Only days with 2-4 hour time gaps (high-probability setups)")
    
    for ticker in TICKERS:
        df = analyze_retracement_timing(ticker)
        
        if df is not None:
            result_df = print_analysis(df, ticker)
            
            # Save results
            output_path = f'scripts/nqstats/results/retrace_timing_{ticker}_{START_YEAR}_{END_YEAR}.csv'
            result_df.to_csv(output_path, index=False)
            print(f"\n✓ Saved detailed results: {output_path}")


if __name__ == "__main__":
    main()