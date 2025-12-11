
import pandas as pd
import json
import numpy as np
from pathlib import Path
import sys
import os
from collections import Counter
from datetime import datetime, timedelta

# Add project root to path
sys.path.append(os.getcwd())

from api.services.data_loader import DATA_DIR


import pandas as pd
import json
import numpy as np
from pathlib import Path
import sys
import os
from collections import Counter
from datetime import datetime, timedelta

# Add project root to path
sys.path.append(os.getcwd())

from api.services.data_loader import DATA_DIR

SESSIONS = [
    {"name": "Asia", "start": "18:00", "end": "03:00"},
    {"name": "London", "start": "03:00", "end": "08:00"},
    {"name": "NY1", "start": "08:00", "end": "12:00"},
    {"name": "NY2", "start": "12:00", "end": "16:00"},
]

def get_stats_from_buckets(buckets):
    """Calculate median and mode from bucket counts."""
    if not buckets:
        return 0, 0, 0
    
    # Parse keys to floats
    data = []
    for k, v in buckets.items():
        try:
            val = float(k)
            data.append((val, v))
        except ValueError:
            continue
            
    data.sort(key=lambda x: x[0])
    
    total_count = sum(count for _, count in data)
    
    # Mode
    mode_val = max(data, key=lambda x: x[1])[0]
    
    # Median
    cum_count = 0
    median_val = 0
    for val, count in data:
        cum_count += count
        if cum_count >= total_count / 2:
            median_val = val
            break
            
    return round(median_val, 2), round(mode_val, 1), total_count

def load_local_stats(ticker="NQ1"):
    print(f"Loading local data for {ticker}...")
    file_path = Path("data") / f"{ticker}_1m.parquet" 
    if not file_path.exists():
         file_path = DATA_DIR / f"{ticker}_1m.parquet"
    
    if not file_path.exists():
        print(f"Error: {file_path} not found")
        return None

    df = pd.read_parquet(file_path)
    df = df.sort_index()

    if df.index.tz is None:
        df = df.tz_localize('UTC').tz_convert('US/Eastern')
    else:
        df = df.tz_convert('US/Eastern')

    df['date'] = df.index.date

    daily_highs = []
    daily_lows = []
    daily_ranges = []
    daily_dates = [] 
    
    dates = sorted(set(df['date']))
    print(f"Processing local data ({len(dates)} days)...")

    for date in dates:
        day_str = date.strftime('%Y-%m-%d')
        prev_day = date - timedelta(days=1)
        
        try:
            day_start = pd.Timestamp(f"{prev_day} 18:00", tz='US/Eastern')
            day_end = pd.Timestamp(f"{day_str} 16:00", tz='US/Eastern')
            day_data = df.loc[day_start:day_end]
            
            if not day_data.empty and len(day_data) > 10:
                day_open = day_data.iloc[0]['open']
                day_high = day_data['high'].max()
                day_low = day_data['low'].min()
                
                if day_open > 0:
                    daily_highs.append(((day_high - day_open) / day_open) * 100)
                    daily_lows.append(((day_low - day_open) / day_open) * 100)
                    daily_dates.append(date) # Track date
        except:
            pass
            
    return {
        'high': daily_highs,
        'low': daily_lows, 
        'dates': daily_dates
    }

def calc_list_stats(values):
    if not values: return 0, 0, 0
    med = np.median(values)
    bucketed = [round(v, 1) for v in values]
    counts = Counter(bucketed)
    mode = counts.most_common(1)[0][0] if counts else 0
    return round(med, 2), round(mode, 1), len(values)

def find_best_fit(local_data, target_count, target_high, target_low):
    """Find sliding window that best matches the Reference stats."""
    highs = local_data['high']
    lows = local_data['low']
    dates = local_data['dates']
    n = len(highs)
    
    window_size = target_count
    
    if n < window_size:
        print(f"Error: Local data ({n}) is smaller than Reference count ({window_size})")
        return

    print(f"\nSearching for best fit window (Size: {window_size}) across {n} days...")
    print(f"Targets: High Med={target_high}, Low Med={target_low}")
    
    best_error = float('inf')
    best_window = None
    best_stats = None
    
    # Sliding window
    for i in range(n - window_size + 1):
        h_subset = highs[i : i+window_size]
        l_subset = lows[i : i+window_size]
        
        h_med = np.median(h_subset)
        l_med = np.median(l_subset)
        
        # Weighted error? Equal weight.
        # Check absolute difference
        err = abs(h_med - target_high) + abs(l_med - target_low)
        
        if err < best_error:
            best_error = err
            best_window = (i, i+window_size)
            best_stats = (h_med, l_med)
            
    if best_window:
        s, e = best_window
        print(f"\n>>> BEST FIT FOUND <<<")
        print(f"Window: {dates[s]} to {dates[e-1]}")
        print(f"Stats: High Med={best_stats[0]:.3f} (Err {abs(best_stats[0]-target_high):.3f})")
        print(f"       Low Med ={best_stats[1]:.3f} (Err {abs(best_stats[1]-target_low):.3f})")
        print(f"Total Error: {best_error:.4f}")
        
        # Check alignment at the end
        days_diff = (dates[-1] - dates[e-1]).days
        print(f"This window ends {days_diff} days before the last local data ({dates[-1]}).")



def analyze_period(df, start_date, end_date, ref_high_med, ref_low_med, label):
    """Analyze stats for a specific period."""
    # Filter
    mask = (df.index >= start_date) & (df.index <= end_date)
    sub = df[mask]
    
    if sub.empty:
        print(f"\nNo data for {label} ({start_date} to {end_date})")
        return

    # Stats
    # Re-calculate PCTs for subset? 
    # Yes, we need high/low pcts for this subset.
    # Note: df already has 'open' > 0 filtered in load function? 
    # No, load function returns dict. 
    # We should change load function to return DF for Flexible analysis.
    pass

def load_daily_df(ticker="NQ1"):
    file_path = Path("data") / f"{ticker}_1D.parquet" 
    if not file_path.exists():
         file_path = DATA_DIR / f"{ticker}_1D.parquet"
    
    if not file_path.exists():
        print("1D Parquet not found.")
        return None

    df = pd.read_parquet(file_path)
    # Filter bad data
    df = df[df['open'] > 0]
    return df

def main():
    # 1. Load Reference
    ref_path = Path("docs/ReferenceAll.json")
    if not ref_path.exists():
        print("ReferenceAll.json not found")
        return

    with open(ref_path) as f:
        ref_data = json.load(f)

    # Get targets
    ref_high_bucket = ref_data['distributions']['daily']['high']
    ref_low_bucket = ref_data['distributions']['daily']['low']
    target_count = ref_data['meta']['count']
    
    r_high_med, _, _ = get_stats_from_buckets(ref_high_bucket)
    r_low_med, _, _ = get_stats_from_buckets(ref_low_bucket)

    print(f"Reference Target: Count={target_count}, HighMed={r_high_med}, LowMed={r_low_med}")

    # 2. Load 1D DF
    df = load_daily_df("NQ1")
    if df is None: return

    # Scenarios
    scenarios = [
        ("2008-Start", "2008-01-01", "2025-12-31"),
        ("2005-2024", "2005-01-01", "2024-12-31"),
        ("Full History", "1990-01-01", "2025-12-31")
    ]

    print("\n" + "="*80)
    print(f"{'SCENARIO':<15} | {'COUNT':<6} | {'HIGH MED':<8} {'ERR':<6} | {'LOW MED':<8} {'ERR':<6}")
    print("="*80)

    for label, start, end in scenarios:
        s_date = pd.Timestamp(start, tz=df.index.tz)
        e_date = pd.Timestamp(end, tz=df.index.tz)
        
        mask = (df.index >= s_date) & (df.index <= e_date)
        sub = df[mask]
        
        if sub.empty: continue
        
        h_pct = ((sub['high'] - sub['open']) / sub['open']) * 100
        l_pct = ((sub['low'] - sub['open']) / sub['open']) * 100
        
        h_med = np.median(h_pct)
        l_med = np.median(l_pct)
        
        h_err = abs(h_med - r_high_med)
        l_err = abs(l_med - r_low_med)
        
        print(f"{label:<15} | {len(sub):<6} | {h_med:<8.2f} {h_err:<6.2f} | {l_med:<8.2f} {l_err:<6.2f}")

    # 3. Yearly Counts (for 2005-2024 scenario)
    print("\n" + "="*40)
    print(f"Yearly Trading Days (2005-2024)")
    print("="*40)
    
    s_date = pd.Timestamp("2005-01-01", tz=df.index.tz)
    e_date = pd.Timestamp("2024-12-31", tz=df.index.tz)
    sub = df[(df.index >= s_date) & (df.index <= e_date)]
    
    # Group by year
    years = sub.groupby(sub.index.year).size()
    for year, count in years.items():
        print(f"{year}: {count}")
    
    print("-" * 40)
    print(f"Total: {years.sum()}")

if __name__ == "__main__":
    main()
