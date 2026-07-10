"""
Validate "Last Extreme" Hypothesis for Noon Curve Strategy

This script tests the strategy's core assumption:
"When the AM high forms AFTER the AM low, does price make a new high in PM?"

Research Question:
- If amHighBar > amLowBar (high formed last) → Does PM make new high? (Bullish)
- If amLowBar > amHighBar (low formed last) → Does PM make new low? (Bearish)

This is DIFFERENT from the validated noon curve hypothesis (72% opposite sides).
We need to measure if this assumption has predictive power.
"""

import pandas as pd
import os
from datetime import time

# --- Configuration ---
TICKERS = ['NQ1', 'ES1']  # Start with main futures
DATA_DIR = 'data'
START_YEAR = 2015
END_YEAR = 2025

# Session Definitions (US/Eastern)
SESSION_START = time(8, 0)
NOON = time(12, 0)
SESSION_END = time(16, 0)

def load_data(ticker):
    """Load 1-minute parquet data for a ticker."""
    path = f"{DATA_DIR}/{ticker}_1m.parquet"
    if not os.path.exists(path):
        print(f"Warning: {path} not found.")
        return None
    
    try:
        df = pd.read_parquet(path)
        if 'time' in df.columns:
            df['datetime'] = pd.to_datetime(df['time'], unit='s', utc=True)
            df = df.set_index('datetime', inplace=False)
        
        df = df.tz_convert('US/Eastern')
        return df
    except Exception as e:
        print(f"Error loading {ticker}: {e}")
        return None


def validate_last_extreme_hypothesis(ticker):
    """
    Test if 'last extreme in AM' predicts PM direction.
    
    Returns:
        DataFrame with results for each day:
        - Date
        - AM_High, AM_Low (prices)
        - AM_High_Time, AM_Low_Time (when they formed)
        - Last_Extreme ('HIGH' or 'LOW')
        - PM_High, PM_Low (PM session extremes)
        - New_PM_High (bool: PM high > AM high?)
        - New_PM_Low (bool: PM low < AM low?)
        - Prediction_Correct (did last extreme predict PM direction?)
    """
    df = load_data(ticker)
    if df is None:
        return None
    
    # Filter year range
    df = df[(df.index.year >= START_YEAR) & (df.index.year <= END_YEAR)]
    
    daily_groups = df.groupby(df.index.date)
    
    results = []
    
    for date, day_data in daily_groups:
        # Separate AM and PM sessions
        am_data = day_data.between_time(SESSION_START, NOON, inclusive='left')
        pm_data = day_data.between_time(NOON, SESSION_END, inclusive='left')
        
        if len(am_data) < 60 or len(pm_data) < 60:
            continue  # Skip incomplete sessions
        
        # AM Session Extremes
        am_high = am_data['high'].max()
        am_low = am_data['low'].min()
        am_high_time = am_data['high'].idxmax().time()
        am_low_time = am_data['low'].idxmin().time()
        
        # Determine which formed last (strategy's logic)
        am_high_idx = am_data['high'].idxmax()
        am_low_idx = am_data['low'].idxmin()
        
        if am_high_idx > am_low_idx:
            last_extreme = 'HIGH'  # Strategy expects bullish PM
            expected_direction = 'BULL'
        elif am_low_idx > am_high_idx:
            last_extreme = 'LOW'  # Strategy expects bearish PM
            expected_direction = 'BEAR'
        else:
            last_extreme = 'EQUAL'  # Same bar (doji-like)
            expected_direction = 'NEUTRAL'
        
        # PM Session Extremes
        pm_high = pm_data['high'].max()
        pm_low = pm_data['low'].min()
        
        # Did PM make new extremes?
        new_pm_high = pm_high > am_high
        new_pm_low = pm_low < am_low
        
        # Determine actual PM direction (which extreme broke first/more significantly)
        actual_pm_direction = None
        if new_pm_high and not new_pm_low:
            actual_pm_direction = 'BULL'  # Only high broke
        elif new_pm_low and not new_pm_high:
            actual_pm_direction = 'BEAR'  # Only low broke
        elif new_pm_high and new_pm_low:
            # Both broke - which one happened first?
            pm_high_time = pm_data['high'].idxmax()
            pm_low_time = pm_data['low'].idxmin()
            actual_pm_direction = 'BULL' if pm_high_time < pm_low_time else 'BEAR'
        else:
            actual_pm_direction = 'NONE'  # Neither broke (same side AM)
        
        # Was the prediction correct?
        prediction_correct = (expected_direction == actual_pm_direction)
        
        # Additional metrics: time gaps
        time_gap_high_to_low = None
        time_gap_low_to_high = None
        
        if am_high_idx > am_low_idx:
            time_gap_low_to_high = (am_high_idx - am_low_idx).total_seconds() / 60  # minutes
        else:
            time_gap_high_to_low = (am_low_idx - am_high_idx).total_seconds() / 60
        
        results.append({
            'Date': date,
            'AM_High': am_high,
            'AM_Low': am_low,
            'AM_High_Time': am_high_time,
            'AM_Low_Time': am_low_time,
            'Last_Extreme': last_extreme,
            'Expected_Dir': expected_direction,
            'PM_High': pm_high,
            'PM_Low': pm_low,
            'New_PM_High': new_pm_high,
            'New_PM_Low': new_pm_low,
            'Actual_PM_Dir': actual_pm_direction,
            'Prediction_Correct': prediction_correct,
            'Time_Gap_Minutes': time_gap_high_to_low or time_gap_low_to_high or 0
        })
    
    return pd.DataFrame(results)


def analyze_results(df, ticker):
    """Analyze validation results and print summary statistics."""
    if df is None or len(df) == 0:
        print(f"No data for {ticker}")
        return
    
    print(f"\n{'='*70}")
    print(f"LAST EXTREME HYPOTHESIS VALIDATION: {ticker}")
    print(f"{'='*70}")
    print(f"Sample Size: {len(df)} trading days")
    print(f"Period: {df['Date'].min()} to {df['Date'].max()}")
    
    # Filter out EQUAL cases (rare)
    df_valid = df[df['Expected_Dir'] != 'NEUTRAL'].copy()
    
    print(f"\n--- OVERALL ACCURACY ---")
    total = len(df_valid)
    correct = df_valid['Prediction_Correct'].sum()
    accuracy = (correct / total * 100) if total > 0 else 0
    print(f"Prediction Accuracy: {accuracy:.2f}% ({correct}/{total})")
    
    if accuracy < 55:
        print("⛔ HYPOTHESIS FAILS: Accuracy is near random (50%). No predictive edge.")
    elif accuracy < 60:
        print("⚠️  HYPOTHESIS WEAK: Slight edge but not tradable without confluence.")
    elif accuracy < 65:
        print("✅ HYPOTHESIS VALID: Moderate edge. Consider adding filters.")
    else:
        print("🎯 HYPOTHESIS STRONG: High edge. Strategy assumption is sound.")
    
    # Break down by last extreme type
    print(f"\n--- BREAKDOWN BY LAST EXTREME ---")
    
    # When HIGH formed last (bullish setup)
    bull_setups = df_valid[df_valid['Expected_Dir'] == 'BULL']
    bull_correct = bull_setups['Prediction_Correct'].sum()
    bull_accuracy = (bull_correct / len(bull_setups) * 100) if len(bull_setups) > 0 else 0
    print(f"HIGH Formed Last (Bullish Setup):")
    print(f"  Count: {len(bull_setups)}")
    print(f"  Correct: {bull_correct} ({bull_accuracy:.2f}%)")
    
    # When LOW formed last (bearish setup)
    bear_setups = df_valid[df_valid['Expected_Dir'] == 'BEAR']
    bear_correct = bear_setups['Prediction_Correct'].sum()
    bear_accuracy = (bear_correct / len(bear_setups) * 100) if len(bear_setups) > 0 else 0
    print(f"LOW Formed Last (Bearish Setup):")
    print(f"  Count: {len(bear_setups)}")
    print(f"  Correct: {bear_correct} ({bear_accuracy:.2f}%)")
    
    # Actual PM behavior distribution
    print(f"\n--- ACTUAL PM SESSION BEHAVIOR ---")
    pm_dist = df_valid['Actual_PM_Dir'].value_counts()
    for direction, count in pm_dist.items():
        pct = (count / len(df_valid)) * 100
        print(f"  {direction}: {count} ({pct:.1f}%)")
    
    # Time gap analysis (does timing matter?)
    print(f"\n--- TIME GAP ANALYSIS ---")
    print("Does the TIME between low and high formation affect accuracy?")
    
    # Bin by time gap
    df_valid['Time_Bin'] = pd.cut(
        df_valid['Time_Gap_Minutes'],
        bins=[0, 30, 60, 120, 240],
        labels=['<30min', '30-60min', '1-2hrs', '2-4hrs']
    )
    
    for bin_label in ['<30min', '30-60min', '1-2hrs', '2-4hrs']:
        subset = df_valid[df_valid['Time_Bin'] == bin_label]
        if len(subset) > 0:
            acc = (subset['Prediction_Correct'].sum() / len(subset)) * 100
            print(f"  Time Gap {bin_label}: {acc:.1f}% accuracy ({len(subset)} days)")
    
    # Compare to Noon Curve baseline
    print(f"\n--- COMPARISON TO NOON CURVE BASELINE ---")
    opposite_sides = df_valid[
        (df_valid['New_PM_High'] & ~df_valid['New_PM_Low']) |
        (~df_valid['New_PM_High'] & df_valid['New_PM_Low'])
    ]
    same_side_am = df_valid[
        ~df_valid['New_PM_High'] & ~df_valid['New_PM_Low']
    ]
    
    opp_pct = (len(opposite_sides) / len(df_valid)) * 100
    same_pct = (len(same_side_am) / len(df_valid)) * 100
    
    print(f"Opposite Sides (One breaks): {opp_pct:.1f}%")
    print(f"Same Side AM (Neither breaks): {same_pct:.1f}%")
    print(f"Research Expectation: 72-75% opposite, 22% same side AM")
    
    return df_valid


def main():
    all_results = {}
    
    for ticker in TICKERS:
        print(f"\nProcessing {ticker}...")
        df = validate_last_extreme_hypothesis(ticker)
        if df is not None and len(df) > 0:
            all_results[ticker] = analyze_results(df, ticker)
    
    # Save detailed results
    print(f"\n{'='*70}")
    print("SAVING RESULTS...")
    print(f"{'='*70}")
    
    os.makedirs('scripts/nqstats/results', exist_ok=True)
    
    for ticker, df in all_results.items():
        if df is not None:
            output_file = f'scripts/nqstats/results/last_extreme_validation_{ticker}.csv'
            df.to_csv(output_file, index=False)
            print(f"Saved: {output_file}")


if __name__ == "__main__":
    main()