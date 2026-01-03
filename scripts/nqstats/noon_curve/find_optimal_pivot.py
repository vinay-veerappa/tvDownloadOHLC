
import pandas as pd
import numpy as np
import os
import pytz
from datetime import time, timedelta

# --- Configuration ---
TICKERS = ['GC1', 'CL1']
DATA_DIR = 'data'
START_YEAR = 2015
END_YEAR = 2025

# Define Full Trading Day for Commodities
# 18:00 (Prev Day) to 17:00 (Current Day)
DAY_START = time(18, 0)
DAY_END = time(16, 59)

def load_data(ticker):
    # (Same load_data as before)
    path = f"{DATA_DIR}/{ticker}_1m.parquet"
    if not os.path.exists(path):
        return None
    try:
        df = pd.read_parquet(path)
        if 'time' in df.columns:
            df['datetime'] = pd.to_datetime(df['time'], unit='s', utc=True)
            df.set_index('datetime', inplace=True)
        df = df.tz_convert('US/Eastern')
        return df
    except:
        return None

def analyze_distributions(ticker):
    df = load_data(ticker)
    if df is None: return None

    df = df[df.index.year >= START_YEAR]
    
    # Define Trading Day Strategy:
    # We assign "Trading Date" based on the end of the session.
    # If hour >= 18, it belongs to Date + 1.
    # If hour < 17, belongs to Date.
    
    df['TradingDate'] = df.index.date
    # Adjust for session start at 18:00 previous day
    # Shift times so 18:00 is "00:00" relative session time? 
    # Easier: Just iterate unique days if we can group effectively.
    
    # Let's create a custom grouper
    # Shift data back by 17 hours? No.
    # If time is > 17:00, add 1 day to date.
    
    # Vectorized adjustment
    # create a series of the index
    times = df.index
    # Logic: Session is 18:00 D-1 to 17:00 D.
    # Any time after 17:00 belongs to D+1
    # Actually, usually continuous futures are split. 
    # Let's just assume we want to analyze the 00:00 - 23:59 and see where highs occur first.
    # OR strictly follow the user's "Asia-London-NY" request.
    
    # Let's clean the data to just be "US/Eastern" days for simplicity of visualization, 
    # realizing that 18:00-24:00 is technically the start.
    
    # We'll stick to a simple 00:00 -> 23:59 view first to see distribution.
    
    daily_groups = df.groupby(df.index.date)
    
    high_times = []
    low_times = []
    
    for date, day_data in daily_groups:
        if len(day_data) < 100: continue
        
        # We want the FULL 24h high/low roughly
        # Or specifically the "Session" High/Low.
        # Let's look at 18:00 (prev) to 17:00 (curr).
        # But efficiently: just taking 00:00-23:00 is easier for histograms.
        
        idxmax = day_data['high'].idxmax()
        idxmin = day_data['low'].idxmin()
        
        high_times.append(idxmax.hour + idxmax.minute/60.0)
        low_times.append(idxmin.hour + idxmin.minute/60.0)
        
    return high_times, low_times

def test_pivots(ticker):
    df = load_data(ticker)
    if df is None: return []
    df = df[df.index.year >= START_YEAR]
    
    # We need to construct "Sessions" properly to test pivots.
    # Strategy: Group by Date (00:00-23:59).
    # Test Pivots: 8, 9, 10, 11, 12, 13.
    # "Opposite Side": High < Pivot < Low OR Low < Pivot < High.
    
    pivots_to_test = [8, 9, 10, 11, 12, 13, 14]
    pivot_results = {p: {'Opposite': 0, 'Total': 0} for p in pivots_to_test}
    
    daily_groups = df.groupby(df.index.date)
    
    for date, day_data in daily_groups:
        if len(day_data) < 60: continue
        
        # Consider the "Active" session 00:00 to 17:00 for this test? 
        # Or 08:00 to 17:00?
        # User said "Asia-London-NY". That implies starting earlier.
        # Let's Try: Start of Day (00:00) to 17:00.
        # Split at Pivot.
        
        data_slice = day_data.between_time(time(0,0), time(16,59))
        if data_slice.empty: continue
        
        h_time = data_slice['high'].idxmax()
        l_time = data_slice['low'].idxmin()
        
        h_hour = h_time.hour + h_time.minute/60.0
        l_hour = l_time.hour + l_time.minute/60.0
        
        for p in pivots_to_test:
            # Check if one is before P and one is after P
            h_side = 'AM' if h_hour < p else 'PM'
            l_side = 'AM' if l_hour < p else 'PM'
            
            if h_side != l_side:
                pivot_results[p]['Opposite'] += 1
            pivot_results[p]['Total'] += 1
            
    summary = []
    for p in pivots_to_test:
        total = pivot_results[p]['Total']
        if total > 0:
            rate = pivot_results[p]['Opposite'] / total
            summary.append({'Ticker': ticker, 'Pivot': p, 'Rate': rate, 'Total': total})
            
    return summary

def main():
    print("Analyzing Optimal Pivots (00:00 - 17:00 Session)...")
    final_res = []
    for t in TICKERS:
        res = test_pivots(t)
        final_res.extend(res)
        
    df = pd.DataFrame(final_res)
    print(df.sort_values(by=['Ticker', 'Rate'], ascending=False).to_string())
    
    # Save
    df.to_csv('scripts/nqstats/results/commodity_pivots.csv', index=False)

if __name__ == "__main__":
    main()
