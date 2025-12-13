

import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta
from api.services.data_loader import DATA_DIR
from api.services.session_service import SessionService
from collections import Counter
import sys

def calculate_mode(values, bucket_size=5):
    """Calculate mode of values bucketed by size."""
    if not values: return 0
    buckets = [int(v // bucket_size) * bucket_size for v in values]
    count = Counter(buckets)
    if not count: return 0
    # Return the bucket start with max count
    return count.most_common(1)[0][0]

def analyze():
    ticker = "NQ1"
    
    print(f"Loading data for {ticker}...")
    file_path = DATA_DIR / f"{ticker}_1m.parquet"
    if not file_path.exists():
        print("Data file not found")
        return

    df = pd.read_parquet(file_path)
    df = df.sort_index()
    if df.index.tz is None:
        df = df.tz_localize('UTC').tz_convert('US/Eastern')
    else:
        df = df.tz_convert('US/Eastern')
        
    print(f"Calculating sessions for {len(df)} rows...")
    all_sessions = SessionService.calculate_sessions(df)
    
    # Organize by Date
    sessions_by_date = {}
    levels_by_date = {}
    
    print(f"Organizing {len(all_sessions)} entries...")
    
    for entry in all_sessions:
        d = entry['date']
        sess = entry['session']
        
        # Store Levels
        if sess in ['PDH', 'PDL', 'PDMid', 'GlobexOpen', 'Open730', 'MidnightOpen']:
            if d not in levels_by_date: levels_by_date[d] = {}
            levels_by_date[d][sess] = entry.get('price')
            
        # Store Sessions (OHLC + Status needed? Status is calculated in ProfilerService, not SessionService)
        # SessionService only gives raw OHLC. We need ProfilerService logic for Status.
        # But for this script, let's just use raw OHLC relative to Open/Mid to infer simple status?
        # Constructing full status is complex.
        # Let's import ProfilerService instead if possible? No, circular deps risk.
        # Let's just calculate simple direction of London: Close > Open ? Long : Short
        elif sess in ['Asia', 'London', 'NY1', 'NY2']:
            if d not in sessions_by_date: sessions_by_date[d] = {}
            sessions_by_date[d][sess] = entry

    # Analysis: NY1 Hit Rate
    target_session = 'NY1'
    prev_session = 'London'
    
    print(f"\nAnalyzing hits during {target_session}...")
    print(f"Conditioning on {prev_session} direction (Green/Red)...")

    # Data Structure:
    # context_stats['All'] -> { 'PDH': { hits, total, times }, ... }
    # context_stats['Green'] -> ...
    # context_stats['Red'] -> ...
    
    context_keys = ['All', 'Green', 'Red'] 
    levels = ['PDH', 'PDL', 'GlobexOpen', 'MidnightOpen']
    
    stats = {
        ctx: { 
            lvl: {'hits': 0, 'total': 0, 'times': []} 
            for lvl in levels 
        } 
        for ctx in context_keys 
    }
    
    sorted_dates = sorted(sessions_by_date.keys())
    
    for date_str in sorted_dates:
        # Check sessions
        if target_session not in sessions_by_date[date_str]: continue
        if prev_session not in sessions_by_date[date_str]: continue
        if date_str not in levels_by_date: continue
        
        ny1 = sessions_by_date[date_str][target_session]
        london = sessions_by_date[date_str][prev_session]
        day_levels = levels_by_date[date_str]
        
        # Determine Context (London Direction)
        london_open = london.get('open', 0) if london.get('open') else london.get('mid') # fallback
        london_close = london.get('close')  # SessionService might not have close? It does in hourly but maybe not session sum?
        # SessionService calculates sessions with high/low/mid. It doesn't strictly store close in the summary list.
        # But we can infer close from next session open? Or just use raw price data.
        # Let's check `entry` keys in SessionService: date, session, start, end, high, low, mid.
        # Missing 'open' and 'close' in summary!
        # Wait, for 'Asia' it calculated 'open' for Globex.
        # We need to look up Open/Close manually or modify Service.
        # Quick fix: Look up approximate Open/Close using high/low time? No.
        # Using Index of NY1 Start is reliable approximation for London Close?
        # Let's use the DF lookup for accurate context.
        
        ny1_start = pd.Timestamp(ny1['start_time'])
        london_start = pd.Timestamp(london['start_time'])
        # London Open = price at start
        # London Close = price at end (or NY1 start)
        
        try:
            # Context Logic
            l_open_row = df.iloc[df.index.searchsorted(london_start)]
            l_close_row = df.iloc[df.index.searchsorted(ny1_start) - 1] # Last bar before NY1
            l_open = l_open_row['open']
            l_close = l_close_row['close']
            
            is_green = l_close > l_open
            context = 'Green' if is_green else 'Red'
            
        except:
            continue # Skip if data missing
            
        # Analyze Hit Rates
        ny1_end = pd.Timestamp(ny1['end_time'])
        session_slice = df.loc[ny1_start:ny1_end]
        if session_slice.empty: continue
        
        s_high = ny1['high']
        s_low = ny1['low']
        
        for level_name in levels:
            if level_name not in day_levels: continue
            
            lvl_price = day_levels[level_name]
            if lvl_price is None: continue
            
            # --- Update 'All' Context ---
            stats['All'][level_name]['total'] += 1
            is_hit = False
            hit_min = 0
            
            if s_low <= lvl_price <= s_high:
                # Find time
                hits = session_slice[(session_slice['low'] <= lvl_price) & (session_slice['high'] >= lvl_price)]
                if not hits.empty:
                    is_hit = True
                    first_hit = hits.index[0]
                    hit_min = (first_hit - ny1_start).total_seconds() / 60
            
            if is_hit:
                stats['All'][level_name]['hits'] += 1
                stats['All'][level_name]['times'].append(hit_min)
                
                # --- Update Specific Context ---
                stats[context][level_name]['total'] += 1
                stats[context][level_name]['hits'] += 1
                stats[context][level_name]['times'].append(hit_min)
            else:
                 stats[context][level_name]['total'] += 1
                

    # Report
    print(f"\n{'Context':<8} | {'Level':<12} | {'Rate':<8} | {'Median':<6} | {'Mode (5m)':<10}")
    print("-" * 65)
    
    for ctx in ['All', 'Green', 'Red']:
        print(f"{'':<8} | {'-'*12} | {'-'*8} | {'-'*6} | {'-'*10}")
        for lvl in levels:
            dat = stats[ctx][lvl]
            if dat['total'] < 10: continue # Skip noise
            
            rate = (dat['hits'] / dat['total']) * 100
            times = dat['times']
            median = np.median(times) if times else 0
            mode = calculate_mode(times, bucket_size=5)
            
            print(f"{ctx:<8} | {lvl:<12} | {rate:6.1f}% | {median:6.1f} | {mode}-{mode+5}m")

if __name__ == "__main__":
    analyze()
