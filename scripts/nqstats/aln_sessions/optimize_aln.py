
import pandas as pd
import numpy as np
import os
import pytz
from datetime import time, timedelta

# --- Configuration ---
TICKERS = ['GC1', 'CL1']
DATA_DIR = 'data'
START_YEAR = 2015

def load_data(ticker):
    path = f"{DATA_DIR}/{ticker}_1m.parquet"
    if not os.path.exists(path): return None
    df = pd.read_parquet(path)
    if 'time' in df.columns:
        df['datetime'] = pd.to_datetime(df['time'], unit='s', utc=True)
        df.set_index('datetime', inplace=True)
    df = df.tz_convert('US/Eastern')
    return df[df.index.year >= START_YEAR]

def get_session_ranges(day_data, asia_start, asia_end, lon_start, lon_end, ny_start, ny_end):
    # This is tricky because Asia starts previous day.
    # We will assume 'day_data' covers the full needed range.
    # Actually, iterate days from the full DF is safer.
    pass

def test_aln_config(df, config_name, t_asia_start, t_asia_end, t_lon_start, t_lon_end, t_ny_start, t_ny_end):
    """
    Calculates LPEU/LPED win rates for a specific time configuration.
    """
    # Group by date based on NY End time
    # This might lose the Asia part if we strictly group by date.
    # We need a rolling window or careful indexing.
    # Simpler: Index by Finding NY Sessions, then look back.
    
    # 1. Identify NY Sessions
    #    Day defined by NY End (16:00 usually, or config).
    
    # Efficient approach: Ensure DF has all minutes.
    # Iterating days is slow but robust.
    
    dates = df.index.date
    unique_dates = np.unique(dates)
    
    lpeu_wins = 0
    lpeu_total = 0
    lped_wins = 0
    lped_total = 0
    
    # We need to grab data relative to the "Trading Day"
    # Asia Start is on Day-1 usually.
    
    # Convert times to hours for easier comparison if needed, but between_time is best.
    # To handle Day-1, we can just iterate unique dates and grab the time slice:
    #   (Date-1 AsiaStart) to (Date NYEnd)
    
    # We'll skip the first day to ensure we have previous data
    
    for i in range(1, len(unique_dates)):
        curr_date = unique_dates[i]
        prev_date = unique_dates[i-1]
        
        # Check if dates are consecutive? 
        if (curr_date - prev_date).days > 3: continue # Skip gaps > weekend
        
        # Define timestamps
        # Asia Start (Prev Date)
        ts_asia_start = pd.Timestamp.combine(prev_date, t_asia_start).tz_localize('US/Eastern')
        # ... logic to handle wrapping if Asia Start is late (e.g. 20:00)
        
        # Let's simplify:
        # Standard ALN: Asia 20:00 (D-1) -> 02:00 (D) | Lon 02:00 -> 08:00 | NY 08:00 -> 16:00
        
        # Construct timestamps
        try:
            asia_s = pd.Timestamp.combine(prev_date, t_asia_start).tz_localize('US/Eastern')
            asia_e = pd.Timestamp.combine(curr_date, t_asia_end).tz_localize('US/Eastern')
            lon_s = pd.Timestamp.combine(curr_date, t_lon_start).tz_localize('US/Eastern')
            lon_e = pd.Timestamp.combine(curr_date, t_lon_end).tz_localize('US/Eastern')
            ny_s = pd.Timestamp.combine(curr_date, t_ny_start).tz_localize('US/Eastern')
            ny_e = pd.Timestamp.combine(curr_date, t_ny_end).tz_localize('US/Eastern')
        except:
            continue
            
        # Extract data slices
        # We need a robust way to get slice.
        # Use truncate or loc
        
        # Optimization: Pre-calculate High/Low for these windows?
        # Too complex for this prompt. Slow iteration is fine for 2 tickers * 10 years.
        
        asia_slice = df.loc[asia_s:asia_e]
        lon_slice = df.loc[lon_s:lon_e]
        ny_slice = df.loc[ny_s:ny_e]
        
        if asia_slice.empty or lon_slice.empty or ny_slice.empty: continue
        
        a_high = asia_slice['high'].max()
        a_low = asia_slice['low'].min()
        
        l_high = lon_slice['high'].max()
        l_low = lon_slice['low'].min()
        
        n_high = ny_slice['high'].max()
        n_low = ny_slice['low'].min()
        
        # Classification
        # LPEU: London breaks Asia High, but NOT Asia Low
        if l_high > a_high and l_low > a_low:
            lpeu_total += 1
            # Win if NY breaks London High
            if n_high > l_high:
                lpeu_wins += 1
                
        # LPED: London breaks Asia Low, but NOT Asia High
        if l_low < a_low and l_high < a_high:
            lped_total += 1
            # Win if NY breaks London Low
            if n_low < l_low:
                lped_wins += 1

    lpeu_rate = lpeu_wins / lpeu_total if lpeu_total > 0 else 0
    lped_rate = lped_wins / lped_total if lped_total > 0 else 0
    avg_rate = (lpeu_rate + lped_rate) / 2
    
    return {
        'Config': config_name,
        'LPEU_Rate': lpeu_rate,
        'LPEU_Count': lpeu_total,
        'LPED_Rate': lped_rate,
        'LPED_Count': lped_total,
        'Avg_Win': avg_rate
    }

def main():
    configs = [
        {
            'name': 'Standard (20-02-08)',
            'as': time(20,0), 'ae': time(2,0),
            'ls': time(2,0), 'le': time(8,0),
            'ns': time(8,0), 'ne': time(16,0)
        },
        {
            'name': 'Early London (19-01-07)', # Gold often earlier?
            'as': time(19,0), 'ae': time(1,0),
            'ls': time(1,0), 'le': time(7,0),
            'ns': time(7,0), 'ne': time(15,0) # NY also earlier?
        },
        {
            'name': 'Late London (21-03-09)', # Maybe real London open matter?
            'as': time(21,0), 'ae': time(3,0),
            'ls': time(3,0), 'le': time(9,0),
            'ns': time(9,0), 'ne': time(16,0)
        },
        {
            'name': 'Gold Specific (18-02-08)', # Deep Asia
            'as': time(18,0), 'ae': time(2,0),
            'ls': time(2,0), 'le': time(8,0),
            'ns': time(8,0), 'ne': time(16,0)
        }
    ]

    for ticker in TICKERS:
        print(f"\n--- Optimizing ALN for {ticker} ---")
        df = load_data(ticker)
        if df is None: continue
        
        results = []
        for cfg in configs:
            print(f"Testing {cfg['name']}...")
            res = test_aln_config(
                df, cfg['name'],
                cfg['as'], cfg['ae'],
                cfg['ls'], cfg['le'],
                cfg['ns'], cfg['ne']
            )
            # Add ticker
            res['Ticker'] = ticker
            results.append(res)
            
        res_df = pd.DataFrame(results)
        print(res_df.sort_values('Avg_Win', ascending=False).to_string())

if __name__ == "__main__":
    main()
