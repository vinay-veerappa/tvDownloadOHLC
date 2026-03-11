"""
Deep Analysis: Time Gap Impact on "Last Extreme" Hypothesis

This script replicates the EXACT Pine Script logic and analyzes why win rates differ.

Key Investigation Areas:
1. Time gap calculation (actual time vs bar index)
2. Entry window timing (12:00-13:30 EST) impact
3. AM extreme formation patterns
4. News event timing (8:30 AM EST) correlation
5. Comparison with backtest data range

CRITICAL: Parquet data is UTC, convert to America/New_York (EST/EDT)
"""

import pandas as pd
import numpy as np
from datetime import time, datetime, timedelta
import pytz

# --- Configuration ---
TICKERS = ['NQ1', 'ES1']
DATA_DIR = 'data'
START_YEAR = 2020  # Match Pine Script backtest window
END_YEAR = 2025

# Session Times (America/New_York timezone)
SESSION_START = time(8, 0)
NOON = time(12, 0)
SESSION_END = time(16, 0)
ENTRY_START = time(12, 0)
ENTRY_END = time(13, 30)

# News time (major economic releases)
NEWS_TIME = time(8, 30)

def load_data(ticker):
    """Load 1-minute parquet data and convert to EST."""
    path = f"{DATA_DIR}/{ticker}_1m.parquet"
    
    try:
        df = pd.read_parquet(path)
        
        # Handle time column
        if 'time' in df.columns:
            df['datetime'] = pd.to_datetime(df['time'], unit='s', utc=True)
            df.set_index('datetime', inplace=True)
        
        # CRITICAL: Convert UTC to America/New_York (handles EST/EDT automatically)
        df = df.tz_convert('America/New_York')
        
        print(f"✓ Loaded {ticker}: {len(df)} bars")
        print(f"  Timezone: {df.index.tz}")
        print(f"  Date range: {df.index.min().date()} to {df.index.max().date()}")
        
        return df
    except Exception as e:
        print(f"Error loading {ticker}: {e}")
        return None


def analyze_time_gaps_deep(ticker):
    """
    Deep analysis of time gap patterns and their impact on prediction accuracy.
    
    Investigates:
    - Actual time gaps (in minutes) vs bar index gaps
    - Entry window state (what price is doing at 12:00-13:30)
    - News event correlation (8:30 AM events)
    - Time-of-day patterns for AM extremes
    """
    df = load_data(ticker)
    if df is None:
        return None
    
    # Filter year range (match Pine Script backtest)
    df = df[(df.index.year >= START_YEAR) & (df.index.year <= END_YEAR)]
    
    print(f"\n{'='*80}")
    print(f"DEEP ANALYSIS: {ticker} ({START_YEAR}-{END_YEAR})")
    print(f"{'='*80}")
    print(f"Total bars: {len(df):,}")
    print(f"Trading days: {len(np.unique(df.index.date)):,}")
    
    daily_groups = df.groupby(df.index.date)
    
    results = []
    
    for date, day_data in daily_groups:
        # 1. AM Session (08:00-12:00)
        am_data = day_data.between_time(SESSION_START, NOON, inclusive='left')
        if len(am_data) < 60:
            continue
        
        # Track AM extremes with ACTUAL timestamps
        am_high_price = am_data['high'].max()
        am_low_price = am_data['low'].min()
        am_high_idx = am_data['high'].idxmax()
        am_low_idx = am_data['low'].idxmin()
        
        # Calculate ACTUAL time gap (in minutes)
        time_gap_minutes = abs((am_high_idx - am_low_idx).total_seconds() / 60)
        
        # Determine last extreme
        if am_high_idx > am_low_idx:
            last_extreme = 'HIGH'
            expected_dir = 'BULL'
        elif am_low_idx > am_high_idx:
            last_extreme = 'LOW'
            expected_dir = 'BEAR'
        else:
            continue  # Skip equal timestamps
        
        # 2. Entry Window State (12:00-13:30)
        entry_data = day_data.between_time(ENTRY_START, ENTRY_END, inclusive='both')
        
        if len(entry_data) == 0:
            continue
        
        # What was happening at entry window?
        entry_open = entry_data['open'].iloc[0] if len(entry_data) > 0 else np.nan
        entry_close = entry_data['close'].iloc[-1] if len(entry_data) > 0 else np.nan
        entry_high = entry_data['high'].max() if len(entry_data) > 0 else np.nan
        entry_low = entry_data['low'].min() if len(entry_data) > 0 else np.nan
        
        # Was price above/below AM midpoint at entry window?
        am_midpoint = (am_high_price + am_low_price) / 2.0
        entry_vs_mid = 'ABOVE' if entry_close > am_midpoint else 'BELOW' if entry_close < am_midpoint else 'ON'
        
        # Did price AVOID retracing to 50% during entry window? (Strong setup indicator)
        # FIXED: Inverted logic - True means STRONG (price did NOT retrace), not weak
        retrace_50_long = am_high_price - (am_high_price - am_low_price) * 0.5
        retrace_50_short = am_low_price + (am_high_price - am_low_price) * 0.5
        
        hit_retrace_zone = False
        if expected_dir == 'BULL':
            # Strong BULL setup = entry low stayed ABOVE 50% retrace (did NOT retrace deeply)
            hit_retrace_zone = entry_low > retrace_50_long
        else:
            # Strong BEAR setup = entry high stayed BELOW 50% retrace (did NOT retrace deeply)
            hit_retrace_zone = entry_high < retrace_50_short
        
        # 3. PM Session (12:00-16:00)
        pm_data = day_data.between_time(NOON, SESSION_END, inclusive='left')
        if len(pm_data) < 60:
            continue
        
        pm_high = pm_data['high'].max()
        pm_low = pm_data['low'].min()
        
        # Determine actual PM direction
        new_pm_high = pm_high > am_high_price
        new_pm_low = pm_low < am_low_price
        
        if new_pm_high and not new_pm_low:
            actual_pm_dir = 'BULL'
        elif new_pm_low and not new_pm_high:
            actual_pm_dir = 'BEAR'
        elif new_pm_high and new_pm_low:
            # Both broke - which first?
            pm_high_time = pm_data['high'].idxmax()
            pm_low_time = pm_data['low'].idxmin()
            actual_pm_dir = 'BULL' if pm_high_time < pm_low_time else 'BEAR'
        else:
            actual_pm_dir = 'NONE'
        
        prediction_correct = (expected_dir == actual_pm_dir)
        
        # 4. News Event Detection (8:30 AM)
        # Check if AM extreme formed within 30 minutes of 8:30 AM news
        news_window_start = datetime.combine(date, time(8, 25))
        news_window_end = datetime.combine(date, time(9, 0))
        
        # Make timezone-aware
        ny_tz = pytz.timezone('America/New_York')
        news_window_start = ny_tz.localize(news_window_start)
        news_window_end = ny_tz.localize(news_window_end)
        
        high_during_news = news_window_start <= am_high_idx <= news_window_end
        low_during_news = news_window_start <= am_low_idx <= news_window_end
        
        # 5. Time of day for extremes
        am_high_hour = am_high_idx.hour + am_high_idx.minute / 60.0
        am_low_hour = am_low_idx.hour + am_low_idx.minute / 60.0
        
        # 6. AM Range characteristics
        am_range = am_high_price - am_low_price
        am_range_pct = (am_range / am_high_price) * 100 if am_high_price != 0 else 0
        
        # 7. Classification bins
        time_bin = None
        if time_gap_minutes < 30:
            time_bin = '<30min'
        elif time_gap_minutes < 60:
            time_bin = '30-60min'
        elif time_gap_minutes < 120:
            time_bin = '1-2hrs'
        elif time_gap_minutes < 240:
            time_bin = '2-4hrs'
        else:
            time_bin = '>4hrs'
        
        results.append({
            'Date': date,
            'AM_High_Time': am_high_idx.time(),
            'AM_Low_Time': am_low_idx.time(),
            'AM_High_Hour': am_high_hour,
            'AM_Low_Hour': am_low_hour,
            'Last_Extreme': last_extreme,
            'Expected_Dir': expected_dir,
            'Actual_PM_Dir': actual_pm_dir,
            'Prediction_Correct': prediction_correct,
            'Time_Gap_Minutes': time_gap_minutes,
            'Time_Bin': time_bin,
            'High_During_News': high_during_news,
            'Low_During_News': low_during_news,
            'Either_During_News': high_during_news or low_during_news,
            'Entry_Close': entry_close,
            'Entry_vs_Midpoint': entry_vs_mid,
            'Hit_Retrace_Zone': hit_retrace_zone,
            'AM_Range': am_range,
            'AM_Range_Pct': am_range_pct,
            'New_PM_High': new_pm_high,
            'New_PM_Low': new_pm_low,
        })
    
    return pd.DataFrame(results)


def print_deep_analysis(df, ticker):
    """Print comprehensive analysis results."""
    if df is None or len(df) == 0:
        print(f"No data for {ticker}")
        return
    
    print(f"\n{'='*80}")
    print(f"RESULTS: {ticker}")
    print(f"{'='*80}")
    print(f"Sample Size: {len(df)} trading days")
    print(f"Period: {df['Date'].min()} to {df['Date'].max()}")
    
    # Overall accuracy
    total = len(df)
    correct = df['Prediction_Correct'].sum()
    accuracy = (correct / total * 100) if total > 0 else 0
    print(f"\nOVERALL ACCURACY: {accuracy:.2f}% ({correct}/{total})")
    
    # ===== INVESTIGATION 1: Time Gap Distribution =====
    print(f"\n{'─'*80}")
    print("INVESTIGATION 1: TIME GAP DISTRIBUTION")
    print(f"{'─'*80}")
    
    time_bin_order = ['<30min', '30-60min', '1-2hrs', '2-4hrs', '>4hrs']
    for bin_label in time_bin_order:
        subset = df[df['Time_Bin'] == bin_label]
        if len(subset) > 0:
            acc = (subset['Prediction_Correct'].sum() / len(subset)) * 100
            pct_of_total = (len(subset) / total) * 100
            print(f"  {bin_label:>10}: {acc:5.1f}% accuracy | {len(subset):4d} days ({pct_of_total:4.1f}% of total)")
    
    # ===== INVESTIGATION 2: News Event Impact =====
    print(f"\n{'─'*80}")
    print("INVESTIGATION 2: NEWS EVENT CORRELATION (8:30 AM ±5min)")
    print(f"{'─'*80}")
    
    news_subset = df[df['Either_During_News']]
    no_news_subset = df[~df['Either_During_News']]
    
    news_acc = (news_subset['Prediction_Correct'].sum() / len(news_subset) * 100) if len(news_subset) > 0 else 0
    no_news_acc = (no_news_subset['Prediction_Correct'].sum() / len(no_news_subset) * 100) if len(no_news_subset) > 0 else 0
    
    print(f"  Extreme during news window: {news_acc:5.1f}% accuracy ({len(news_subset):4d} days)")
    print(f"  No news window extreme:     {no_news_acc:5.1f}% accuracy ({len(no_news_subset):4d} days)")
    print(f"  Difference: {news_acc - no_news_acc:+5.1f}%")
    
    # ===== INVESTIGATION 3: Entry Window State =====
    print(f"\n{'─'*80}")
    print("INVESTIGATION 3: ENTRY WINDOW STATE (12:00-13:30)")
    print(f"{'─'*80}")
    
    for pos in ['ABOVE', 'BELOW']:
        subset = df[df['Entry_vs_Midpoint'] == pos]
        if len(subset) > 0:
            acc = (subset['Prediction_Correct'].sum() / len(subset)) * 100
            print(f"  Entry close {pos} midpoint: {acc:5.1f}% accuracy ({len(subset):4d} days)")
    
    print(f"\nDid price AVOID retracing to 50% (strong setup)?")
    for hit in [True, False]:
        subset = df[df['Hit_Retrace_Zone'] == hit]
        if len(subset) > 0:
            acc = (subset['Prediction_Correct'].sum() / len(subset)) * 100
            status = 'STRONG' if hit else 'WEAK (retracted)'
            print(f"  Strong setup (no deep retrace) = {status}: {acc:5.1f}% accuracy ({len(subset):4d} days)")
    
    # ===== INVESTIGATION 4: Time-of-Day Patterns =====
    print(f"\n{'─'*80}")
    print("INVESTIGATION 4: TIME-OF-DAY PATTERNS FOR AM EXTREMES")
    print(f"{'─'*80}")
    
    # Bin by hour ranges
    def hour_bin(hour):
        if hour < 8.5:
            return '08:00-08:30'
        elif hour < 9.0:
            return '08:30-09:00'
        elif hour < 9.5:
            return '09:00-09:30'
        elif hour < 10.0:
            return '09:30-10:00'
        elif hour < 10.5:
            return '10:00-10:30'
        elif hour < 11.0:
            return '10:30-11:00'
        elif hour < 11.5:
            return '11:00-11:30'
        else:
            return '11:30-12:00'
    
    df['High_Hour_Bin'] = df['AM_High_Hour'].apply(hour_bin)
    df['Low_Hour_Bin'] = df['AM_Low_Hour'].apply(hour_bin)
    
    print("\nHIGH formed in time window:")
    high_dist = df['High_Hour_Bin'].value_counts().sort_index()
    for window, count in high_dist.items():
        pct = (count / total) * 100
        print(f"  {window}: {count:4d} days ({pct:4.1f}%)")
    
    print("\nLOW formed in time window:")
    low_dist = df['Low_Hour_Bin'].value_counts().sort_index()
    for window, count in low_dist.items():
        pct = (count / total) * 100
        print(f"  {window}: {count:4d} days ({pct:4.1f}%)")
    
    # ===== INVESTIGATION 5: Directional Bias =====
    print(f"\n{'─'*80}")
    print("INVESTIGATION 5: DIRECTIONAL BIAS BREAKDOWN")
    print(f"{'─'*80}")
    
    for direction in ['BULL', 'BEAR']:
        subset = df[df['Expected_Dir'] == direction]
        if len(subset) > 0:
            acc = (subset['Prediction_Correct'].sum() / len(subset)) * 100
            print(f"\n{direction} Setups: {acc:5.1f}% accuracy ({len(subset):4d} days)")
            
            # Break down by time gap
            print(f"  By time gap:")
            for bin_label in time_bin_order:
                bin_subset = subset[subset['Time_Bin'] == bin_label]
                if len(bin_subset) > 0:
                    bin_acc = (bin_subset['Prediction_Correct'].sum() / len(bin_subset)) * 100
                    print(f"    {bin_label:>10}: {bin_acc:5.1f}% ({len(bin_subset):3d} days)")
    
    # ===== INVESTIGATION 6: PM Outcome Distribution =====
    print(f"\n{'─'*80}")
    print("INVESTIGATION 6: PM SESSION OUTCOME DISTRIBUTION")
    print(f"{'─'*80}")
    
    pm_dist = df['Actual_PM_Dir'].value_counts()
    for outcome, count in pm_dist.items():
        pct = (count / total) * 100
        print(f"  {outcome:>4}: {count:4d} days ({pct:5.1f}%)")
    
    # ===== INVESTIGATION 7: Optimal Time Gap Window =====
    print(f"\n{'─'*80}")
    print("INVESTIGATION 7: OPTIMAL TIME GAP WINDOW")
    print(f"{'─'*80}")
    
    # Test different thresholds
    thresholds = [
        (60, 180),   # 1-3 hours
        (90, 210),   # 1.5-3.5 hours
        (120, 240),  # 2-4 hours (current recommendation)
        (150, 270),  # 2.5-4.5 hours
        (180, 300),  # 3-5 hours
    ]
    
    best_acc = 0
    best_threshold = None
    
    for min_gap, max_gap in thresholds:
        subset = df[(df['Time_Gap_Minutes'] >= min_gap) & (df['Time_Gap_Minutes'] <= max_gap)]
        if len(subset) > 0:
            acc = (subset['Prediction_Correct'].sum() / len(subset)) * 100
            pct_of_total = (len(subset) / total) * 100
            marker = ' ← CURRENT' if (min_gap == 120 and max_gap == 240) else ''
            print(f"  {min_gap:3d}-{max_gap:3d} min: {acc:5.1f}% accuracy | {len(subset):4d} days ({pct_of_total:4.1f}%){marker}")
            
            if acc > best_acc:
                best_acc = acc
                best_threshold = (min_gap, max_gap)
    
    print(f"\n  BEST THRESHOLD: {best_threshold[0]}-{best_threshold[1]} minutes ({best_acc:.1f}% accuracy)")
    
    return df


def compare_with_validation_csv(ticker):
    """Compare results with the validation CSV we generated earlier."""
    csv_path = f'scripts/nqstats/results/last_extreme_validation_{ticker}.csv'
    
    try:
        csv_df = pd.read_csv(csv_path)
        print(f"\n{'='*80}")
        print(f"COMPARISON WITH VALIDATION CSV: {ticker}")
        print(f"{'='*80}")
        print(f"CSV Sample Size: {len(csv_df)} days")
        print(f"CSV Date Range: {csv_df['Date'].min()} to {csv_df['Date'].max()}")
        
        # Check accuracy by time bin
        csv_df['Time_Bin'] = pd.cut(
            csv_df['Time_Gap_Minutes'],
            bins=[0, 30, 60, 120, 240, 1000],
            labels=['<30min', '30-60min', '1-2hrs', '2-4hrs', '>4hrs']
        )
        
        # Normalize Prediction_Correct robustly (handles bool, int, and string encodings)
        def to_bool(v):
            if isinstance(v, (bool, np.bool_)):
                return bool(v)
            if isinstance(v, (int, np.integer, float, np.floating)):
                return bool(v)
            if isinstance(v, str):
                return v.strip().lower() in {'true', '1', 'yes', 'y'}
            return False

        csv_df['Prediction_Correct_Bool'] = csv_df['Prediction_Correct'].apply(to_bool)

        print(f"\nAccuracy by time bin (from CSV):")
        for bin_label in ['<30min', '30-60min', '1-2hrs', '2-4hrs', '>4hrs']:
            subset = csv_df[csv_df['Time_Bin'] == bin_label]
            if len(subset) > 0:
                correct = subset['Prediction_Correct_Bool'].sum()
                acc = (correct / len(subset)) * 100
                print(f"  {bin_label:>10}: {acc:5.1f}% ({len(subset):4d} days)")
        
    except FileNotFoundError:
        print(f"\nValidation CSV not found: {csv_path}")


def main():
    """Main analysis runner."""
    print("="*80)
    print("DEEP ANALYSIS: TIME GAP IMPACT ON NOON CURVE HYPOTHESIS")
    print("="*80)
    print(f"Backtest Period: {START_YEAR}-{END_YEAR}")
    print(f"Timezone: America/New_York (EST/EDT auto-handled)")
    print(f"Data Source: Parquet files (UTC → EST conversion)")
    
    for ticker in TICKERS:
        # Run deep analysis
        df = analyze_time_gaps_deep(ticker)
        
        if df is not None:
            # Print results
            result_df = print_deep_analysis(df, ticker)
            
            # Save detailed results
            output_path = f'scripts/nqstats/results/deep_analysis_{ticker}_{START_YEAR}_{END_YEAR}.csv'
            result_df.to_csv(output_path, index=False)
            print(f"\n✓ Saved detailed results: {output_path}")
            
            # Compare with validation CSV
            compare_with_validation_csv(ticker)


if __name__ == "__main__":
    main()
