"""
Debug: Retrace Zone Calculation Anomaly Investigation

Goal: Manually verify Hit_Retrace_Zone calculation for sample days
to determine if it's inverted or if it's a legitimate (counterintuitive) finding.
"""

import pandas as pd
import numpy as np
from datetime import time, datetime
import pytz
from pathlib import Path

# === Configuration ===
TICKERS = ['NQ1', 'ES1']
DATA_DIR = Path('data')
RESULTS_DIR = Path('scripts/nqstats/results')

SESSION_START = time(8, 0)
NOON = time(12, 0)
SESSION_END = time(16, 0)
ENTRY_START = time(12, 0)
ENTRY_END = time(13, 30)

def load_data(ticker):
    """Load 1-minute parquet data and convert to EST."""
    path = DATA_DIR / f"{ticker}_1m.parquet"
    try:
        df = pd.read_parquet(path)
        if 'time' in df.columns:
            df['datetime'] = pd.to_datetime(df['time'], unit='s', utc=True)
            df = df.set_index('datetime', inplace=False)
        df = df.tz_convert('America/New_York')
        return df
    except Exception as e:
        print(f"Error loading {ticker}: {e}")
        return None

def debug_retrace_calculation():
    """
    Sample specific days and manually verify the retrace zone calculation.
    """
    print(f"\n{'='*100}")
    print("RETRACE ZONE CALCULATION DEBUG")
    print(f"{'='*100}\n")
    
    for ticker in TICKERS:
        print(f"\n{'─'*100}")
        print(f"TICKER: {ticker}")
        print(f"{'─'*100}\n")
        
        # Load the deep analysis CSV (already has Hit_Retrace_Zone calculated)
        csv_path = RESULTS_DIR / f"deep_analysis_{ticker}_2020_2025.csv"
        df_analysis = pd.read_csv(csv_path)
        
        # Convert Date to datetime
        df_analysis['Date'] = pd.to_datetime(df_analysis['Date'])
        
        # Separate YES and NO cases
        yes_cases = df_analysis[df_analysis['Hit_Retrace_Zone'] == True].head(3)
        no_cases = df_analysis[df_analysis['Hit_Retrace_Zone'] == False].head(3)
        
        print("Sample days where Hit_Retrace_Zone = YES:")
        print(yes_cases[['Date', 'Expected_Dir', 'Prediction_Correct', 'Hit_Retrace_Zone', 'Entry_vs_Midpoint', 'AM_Range']].to_string(index=False))
        print(f"  Accuracy in these cases: {yes_cases['Prediction_Correct'].mean()*100:.1f}%\n")
        
        print("Sample days where Hit_Retrace_Zone = NO:")
        print(no_cases[['Date', 'Expected_Dir', 'Prediction_Correct', 'Hit_Retrace_Zone', 'Entry_vs_Midpoint', 'AM_Range']].to_string(index=False))
        print(f"  Accuracy in these cases: {no_cases['Prediction_Correct'].mean()*100:.1f}%\n")
        
        # Now load raw data and manually verify a sample day
        df_raw = load_data(ticker)
        if df_raw is None:
            continue
        
        sample_date = yes_cases.iloc[0]['Date']
        print(f"\n{'─'*100}")
        print(f"MANUAL VERIFICATION: {sample_date.date()} (Hit_Retrace_Zone = YES case)")
        print(f"{'─'*100}\n")
        
        day_data = df_raw[df_raw.index.date == sample_date.date()]
        
        # AM Session analysis
        am_data = day_data.between_time(SESSION_START, NOON, inclusive='left')
        
        if len(am_data) > 0:
            am_high_price = am_data['high'].max()
            am_low_price = am_data['low'].min()
            am_high_idx = am_data['high'].idxmax()
            am_low_idx = am_data['low'].idxmin()
            
            # Determine last extreme
            if am_high_idx > am_low_idx:
                last_extreme = 'HIGH'
                expected_dir = 'BULL'
            else:
                last_extreme = 'LOW'
                expected_dir = 'BEAR'
            
            print(f"AM Session (08:00-12:00):")
            print(f"  High:  {am_high_price:.2f} @ {am_high_idx.strftime('%H:%M:%S')}")
            print(f"  Low:   {am_low_price:.2f} @ {am_low_idx.strftime('%H:%M:%S')}")
            print(f"  Range: {(am_high_price - am_low_price):.2f} points")
            print(f"  Last extreme: {last_extreme} (expected direction: {expected_dir})\n")
            
            # Entry Window
            entry_data = day_data.between_time(ENTRY_START, ENTRY_END, inclusive='both')
            
            if len(entry_data) > 0:
                entry_low = entry_data['low'].min()
                entry_high = entry_data['high'].max()
                entry_close = entry_data['close'].iloc[-1]
                
                print(f"Entry Window (12:00-13:30):")
                print(f"  High:  {entry_high:.2f}")
                print(f"  Low:   {entry_low:.2f}")
                print(f"  Close: {entry_close:.2f}")
                
                # 50% retracement levels
                if expected_dir == 'BULL':
                    retrace_50 = am_high_price - (am_high_price - am_low_price) * 0.5
                    print(f"\n  Expected BULL setup: checking if price retraced to 50% level")
                    print(f"  50% retrace level: {retrace_50:.2f}")
                    print(f"  Entry low was: {entry_low:.2f}")
                    hit = entry_low <= retrace_50
                    print(f"  entry_low <= retrace_50: {entry_low:.2f} <= {retrace_50:.2f} = {hit}")
                else:
                    retrace_50 = am_low_price + (am_high_price - am_low_price) * 0.5
                    print(f"\nExpected BEAR setup: checking if price retraced to 50% level")
                    print(f"  50% retrace level: {retrace_50:.2f}")
                    print(f"  Entry high was: {entry_high:.2f}")
                    hit = entry_high >= retrace_50
                    print(f"  entry_high >= retrace_50: {entry_high:.2f} >= {retrace_50:.2f} = {hit}")
                
                print(f"\n  Hit_Retrace_Zone: {hit}")
                
                # PM Session
                pm_data = day_data.between_time(NOON, SESSION_END, inclusive='left')
                
                if len(pm_data) > 0:
                    pm_high = pm_data['high'].max()
                    pm_low = pm_data['low'].min()
                    
                    new_pm_high = pm_high > am_high_price
                    new_pm_low = pm_low < am_low_price
                    
                    if new_pm_high and not new_pm_low:
                        actual_pm_dir = 'BULL'
                    elif new_pm_low and not new_pm_high:
                        actual_pm_dir = 'BEAR'
                    elif new_pm_high and new_pm_low:
                        pm_high_time = pm_data['high'].idxmax()
                        pm_low_time = pm_data['low'].idxmin()
                        actual_pm_dir = 'BULL' if pm_high_time < pm_low_time else 'BEAR'
                    else:
                        actual_pm_dir = 'NONE'
                    
                    prediction_correct = (expected_dir == actual_pm_dir)
                    
                    print(f"\nPM Session (12:00-16:00) Outcome:")
                    print(f"  High:  {pm_high:.2f} (new high vs AM? {new_pm_high})")
                    print(f"  Low:   {pm_low:.2f} (new low vs AM? {new_pm_low})")
                    print(f"  Actual direction: {actual_pm_dir}")
                    print(f"  Prediction correct? {prediction_correct} ({expected_dir} vs {actual_pm_dir})")

def print_aggregate_stats():
    """Print aggregate stats showing the anomaly."""
    print(f"\n\n{'='*100}")
    print("AGGREGATE STATISTICS: Hit_Retrace_Zone vs Prediction_Correct")
    print(f"{'='*100}\n")
    
    for ticker in TICKERS:
        csv_path = RESULTS_DIR / f"deep_analysis_{ticker}_2020_2025.csv"
        df = pd.read_csv(csv_path)
        
        # Convert boolean strings to actual booleans
        df['Hit_Retrace_Zone'] = df['Hit_Retrace_Zone'].astype(str).str.lower().isin(['true', '1', 'yes'])
        df['Prediction_Correct'] = df['Prediction_Correct'].astype(str).str.lower().isin(['true', '1', 'yes'])
        
        print(f"{ticker}:")
        for hit in [True, False]:
            subset = df[df['Hit_Retrace_Zone'] == hit]
            acc = (subset['Prediction_Correct'].sum() / len(subset)) * 100
            status = 'YES' if hit else 'NO'
            print(f"  Hit_Retrace_Zone = {status}: {acc:5.1f}% accuracy ({len(subset):4d} days)")
        print()

if __name__ == "__main__":
    print_aggregate_stats()
    debug_retrace_calculation()