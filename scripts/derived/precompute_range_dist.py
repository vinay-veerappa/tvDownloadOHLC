"""
Pre-compute Price Range Distribution

Calculates the distribution of session highs/lows relative to the open.
This helps predict the most likely range for a session.
"""

import pandas as pd
import json
from datetime import datetime, timedelta
from pathlib import Path
from collections import Counter
import sys
import os

sys.path.append(os.getcwd())

# Session definitions (same as profiler)
SESSIONS = [
    {"name": "Asia", "start": "18:00", "end": "03:00"},
    {"name": "London", "start": "03:00", "end": "08:00"},
    {"name": "NY1", "start": "08:00", "end": "12:00"},
    {"name": "NY2", "start": "12:00", "end": "16:00"},
]

def precompute_range_distribution(ticker="NQ1", timeframe="1m"):
    from api.services.data_loader import DATA_DIR
    
    print(f"Loading {timeframe} data for {ticker}...")
    file_path = DATA_DIR / f"{ticker}_{timeframe}.parquet"
    
    if not file_path.exists():
        print(f"Error: {file_path} not found")
        return
    
    df = pd.read_parquet(file_path)
    df = df.sort_index()
    
    # Timezone handling
    if df.index.tz is None:
        df = df.tz_localize('UTC').tz_convert('US/Eastern')
    else:
        df = df.tz_convert('US/Eastern')
    
    df['date'] = df.index.date
    
    print("Processing sessions...")
    
    # Collect range data per session
    session_data = {s['name']: {'high_pcts': [], 'low_pcts': [], 'ranges': []} for s in SESSIONS}
    daily_data = {'high_pcts': [], 'low_pcts': [], 'ranges': []}
    
    # Get unique dates
    dates = sorted(set(df['date']))
    print(f"Processing {len(dates)} days...")
    
    for date in dates:
        day_str = date.strftime('%Y-%m-%d')
        
        try:
            # Daily range (18:00 prev day to 16:00 current day)
            prev_day = date - timedelta(days=1)
            day_start = pd.Timestamp(f"{prev_day} 18:00", tz='US/Eastern')
            day_end = pd.Timestamp(f"{day_str} 16:00", tz='US/Eastern')
            
            day_data = df.loc[day_start:day_end]
            
            if not day_data.empty and len(day_data) > 10:
                day_open = day_data.iloc[0]['open']
                day_high = day_data['high'].max()
                day_low = day_data['low'].min()
                
                if day_open > 0:
                    high_pct = ((day_high - day_open) / day_open) * 100
                    low_pct = ((day_low - day_open) / day_open) * 100
                    range_pct = ((day_high - day_low) / day_open) * 100
                    
                    daily_data['high_pcts'].append(round(high_pct, 1))
                    daily_data['low_pcts'].append(round(low_pct, 1))
                    daily_data['ranges'].append(round(range_pct, 1))
            
            # Per-session ranges
            for sess in SESSIONS:
                try:
                    sess_start = pd.Timestamp(f"{day_str} {sess['start']}", tz='US/Eastern')
                    
                    # Handle overnight sessions
                    if sess['name'] == 'Asia':
                        sess_start = pd.Timestamp(f"{prev_day} {sess['start']}", tz='US/Eastern')
                        sess_end = pd.Timestamp(f"{day_str} {sess['end']}", tz='US/Eastern')
                    else:
                        sess_end = pd.Timestamp(f"{day_str} {sess['end']}", tz='US/Eastern')
                    
                    sess_data = df.loc[sess_start:sess_end - timedelta(seconds=1)]
                    
                    if not sess_data.empty and len(sess_data) > 5:
                        sess_open = sess_data.iloc[0]['open']
                        sess_high = sess_data['high'].max()
                        sess_low = sess_data['low'].min()
                        
                        if sess_open > 0:
                            high_pct = ((sess_high - sess_open) / sess_open) * 100
                            low_pct = ((sess_low - sess_open) / sess_open) * 100
                            range_pct = ((sess_high - sess_low) / sess_open) * 100
                            
                            session_data[sess['name']]['high_pcts'].append(round(high_pct, 1))
                            session_data[sess['name']]['low_pcts'].append(round(low_pct, 1))
                            session_data[sess['name']]['ranges'].append(round(range_pct, 1))
                except Exception:
                    pass
                    
        except Exception:
            pass
    
    # Calculate stats and distributions
    def calc_dist(values, bucket_size=0.1):
        if not values:
            return {'median': None, 'mode': None, 'count': 0, 'distribution': {}}
        
        # Round to bucket
        bucketed = [round(v / bucket_size) * bucket_size for v in values]
        
        sorted_vals = sorted(values)
        mid = len(sorted_vals) // 2
        median = sorted_vals[mid]
        
        counts = Counter([round(v, 1) for v in bucketed])
        mode = counts.most_common(1)[0][0] if counts else None
        
        # Distribution (aggregate into 0.1% buckets)
        dist = {}
        for v in bucketed:
            k = f"{v:.1f}"
            dist[k] = dist.get(k, 0) + 1
        
        return {
            'median': round(median, 2),
            'mode': mode,
            'count': len(values),
            'distribution': dict(sorted(dist.items(), key=lambda x: float(x[0]))),
        }
    
    results = {
        'daily': {
            'high': calc_dist(daily_data['high_pcts']),
            'low': calc_dist(daily_data['low_pcts']),
            'range': calc_dist(daily_data['ranges']),
        },
        'sessions': {},
        'metadata': {
            'ticker': ticker,
            'generated_at': datetime.now().isoformat(),
        }
    }
    
    for sess_name, data in session_data.items():
        results['sessions'][sess_name] = {
            'high': calc_dist(data['high_pcts']),
            'low': calc_dist(data['low_pcts']),
            'range': calc_dist(data['ranges']),
        }
        print(f"  {sess_name}: {len(data['high_pcts'])} samples")
    
    # Save
    output_path = DATA_DIR / f"{ticker}_range_dist.json"
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nSaved to {output_path}")
    print(f"Daily High: Median={results['daily']['high']['median']}%, Mode={results['daily']['high']['mode']}%")
    print(f"Daily Low: Median={results['daily']['low']['median']}%, Mode={results['daily']['low']['mode']}%")

if __name__ == "__main__":
    import time
    start = time.time()
    
    import sys
    ticker = sys.argv[1] if len(sys.argv) > 1 else "NQ1"
    
    precompute_range_distribution(ticker)
    print(f"Completed in {time.time() - start:.2f}s")
