
import pandas as pd
import glob
import os
import pytz
from datetime import time

# --- Configuration ---
# Tickers to verify
TICKERS = ['NQ1', 'ES1', 'YM1', 'RTY1', 'GC1', 'CL1']
DATA_DIR = 'data'
START_YEAR = 2015
END_YEAR = 2025 # Inclusive

# Session Definitions (US/Eastern)
SESSION_START = time(8, 0)
SESSION_END = time(16, 0)
NOON = time(12, 0)

def load_data(ticker):
    """Loads 1-minute Parquet data for a ticker."""
    path = f"{DATA_DIR}/{ticker}_1m.parquet"
    if not os.path.exists(path):
        print(f"Warning: {path} not found.")
        return None
    
    try:
        df = pd.read_parquet(path)
        # Standardize index
        if 'time' in df.columns:
            df['datetime'] = pd.to_datetime(df['time'], unit='s', utc=True)
            df.set_index('datetime', inplace=True)
        
        # Convert to US/Eastern
        df = df.tz_convert('US/Eastern')
        return df
    except Exception as e:
        print(f"Error loading {ticker}: {e}")
        return None

def verify_noon_curve(ticker):
    df = load_data(ticker)
    if df is None:
        return None

    # Filter year range
    df = df[df.index.year >= START_YEAR]
    df = df[df.index.year <= END_YEAR]

    # Resample to Daily to iterate days, but keep 1m resolution for High/Low timing
    # Group by Date
    daily_groups = df.groupby(df.index.date)
    
    results = []

    for date, day_data in daily_groups:
        # Filter for 08:00 - 16:00 ET
        session_data = day_data.between_time(SESSION_START, SESSION_END)
        
        if len(session_data) < 60: # minimal data check
            continue

        # Identify Session High and Low
        session_high_price = session_data['high'].max()
        session_low_price = session_data['low'].min()
        
        # Find Times of High and Low
        # Note: If multiple bars have the high, take the first one or logic? 
        # Usually statistics use the first occurrence or just any. We'll use idxmax.
        high_time = session_data['high'].idxmax()
        low_time = session_data['low'].idxmin()
        
        high_side = 'AM' if high_time.time() < NOON else 'PM'
        low_side = 'AM' if low_time.time() < NOON else 'PM'
        
        classification = ""
        if high_side != low_side:
            classification = "Opposite"
        elif high_side == 'AM' and low_side == 'AM':
            classification = "Same Side (AM)"
        elif high_side == 'PM' and low_side == 'PM':
            classification = "Same Side (PM)"
            
        results.append({
            'Date': date,
            'High_Time': high_time.time(),
            'Low_Time': low_time.time(),
            'Classification': classification
        })

    results_df = pd.DataFrame(results)
    
    if len(results_df) == 0:
         return pd.DataFrame()

    # Calculate Probabilities
    total_days = len(results_df)
    counts = results_df['Classification'].value_counts()
    probs = (counts / total_days)
    
    summary = pd.DataFrame({
        'Ticker': ticker,
        'Metric': probs.index,
        'Count': counts.values,
        'Probability': probs.values
    })
    
    return summary

def main():
    all_results = []
    print(f"Verifying Noon Curve for {TICKERS}...")
    
    for ticker in TICKERS:
        res = verify_noon_curve(ticker)
        if res is not None and not res.empty:
            all_results.append(res)
            print(f"Processed {ticker}")
        else:
            print(f"Skipping {ticker}")
            
    if all_results:
        final_df = pd.concat(all_results)
        print("\n--- Final Verification Results ---")
        print(final_df.to_string(index=False))
        
        # Save to CSV
        os.makedirs('scripts/nqstats/results', exist_ok=True)
        final_df.to_csv('scripts/nqstats/results/noon_curve_verification.csv', index=False)
    else:
        print("No results generated.")

if __name__ == "__main__":
    main()
