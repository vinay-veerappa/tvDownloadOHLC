
import pandas as pd
import numpy as np
import json
from pathlib import Path
from collections import Counter
import sys
import os

# Add parent directory to path to import services
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.data_loader import DATA_DIR
from services.session_service import SessionService
from datetime import timedelta, time

def calculate_mode(values, bucket_size=5):
    """Calculate mode of values bucketed by size."""
    if not values: return 0
    buckets = [int(v // bucket_size) * bucket_size for v in values]
    count = Counter(buckets)
    if not count: return 0
    return count.most_common(1)[0][0]

def precompute_level_stats(ticker="NQ1"):
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
    # Shift index to align Trading Day (18:00 previous day -> 17:00 current day)
    # Adding 6 hours makes 18:00 -> 00:00 (start of next day)
    df_shifted = df.copy()
    df_shifted.index = df.index + pd.Timedelta(hours=6)
    
    grouped = df.groupby(df_shifted.index.date)
    
    sorted_dates = sorted([d.strftime('%Y-%m-%d') for d in grouped.groups.keys()])
    
    for entry in all_sessions:
        d = entry['date']
        sess = entry['session']
        if sess in ['PDH', 'PDL', 'PDMid', 'GlobexOpen', 'Open730', 'MidnightOpen']:
            if d not in levels_by_date: levels_by_date[d] = {}
            levels_by_date[d][sess] = entry.get('price')
        elif sess in ['Asia', 'London', 'NY1', 'NY2']:
            if d not in sessions_by_date: sessions_by_date[d] = {}
            sessions_by_date[d][sess] = entry
            # Also store the session Mid as a level
            if entry.get('mid') is not None:
                if d not in levels_by_date: levels_by_date[d] = {}
                levels_by_date[d][f"{sess}Mid"] = entry.get('mid')

    target_session = 'NY1'
    prev_session = 'London'
    
    context_keys = ['All', 'Green', 'Red'] 
    levels = ['PDH', 'PDL', 'GlobexOpen', 'MidnightOpen', 'AsiaMid', 'LondonMid', 'NY1Mid']
    
    stats = {
        ctx: { 
            lvl: {'hits': 0, 'total': 0, 'times': [], 'rel_pcts': []} 
            for lvl in levels 
        } 
        for ctx in context_keys 
    }
    
    for date_obj, day_data in grouped:
        date_str = date_obj.strftime('%Y-%m-%d')
        
        if date_str not in sessions_by_date: continue
        if prev_session not in sessions_by_date[date_str]: continue
        if date_str not in levels_by_date: continue
        
        ny1 = sessions_by_date[date_str][target_session]
        london = sessions_by_date[date_str][prev_session]
        day_levels = levels_by_date[date_str]
        
        # Define Trading Day Boundaries (18:00 D-1 to 17:00 D)
        # date_obj is the "Current Day" (e.g. Wednesday)
        # So Trading Day starts Tuesday 18:00.
        
        trading_start = pd.Timestamp.combine(date_obj - timedelta(days=1), time(18, 0)).tz_localize('US/Eastern')
        trading_end = pd.Timestamp.combine(date_obj, time(17, 0)).tz_localize('US/Eastern')
        
        # Use full trading day for stats
        start_ts = trading_start
        
        # We need to map 'DailyOpen' (Frontend) to 'GlobexOpen' (Backend) if needed
        # Or just handle the keys.
        # Frontend expects: 'daily_open', 'midnight_open', 'open_0730', 'pdh', 'pdl', 'pdm'
        # Backend has: 'PDH', 'PDL', 'GlobexOpen', 'MidnightOpen', 'Open730', Mids...
        
        # Let's verify what keys are in 'levels'. We need to align them.
        # Current levels list: ['PDH', 'PDL', 'GlobexOpen', 'MidnightOpen', 'AsiaMid', ... ]
        # We should map them to the keys expected by frontend if they differ, or just ensure consistency.
        # Frontend 'daily-levels.tsx' uses lowercase keys mostly: 'daily_open', 'midnight_open'.
        # But 'stats' keys are Capitalized in the script?
        # Let's check `compare_reference` map: "pdh" -> "PDH".
        # So Frontend uses lowercase, Backend uses PascalCase.
        # NQ1_level_stats.json has PascalCase. 
        # Frontend likely tries to match? Or maybe Frontend uses PascalCase?
        # daily-levels.tsx: levelKey="daily_open".
        # If stats JSON has "GlobexOpen", frontend "daily_open" won't match.
        # We should Output keys that match Frontend: 'daily_open' etc. 
        # OR Update Frontend. 
        # EASIER: Output both or Map in script.
        
        level_map = {
            'PDH': 'pdh', 'PDL': 'pdl', 'PDMid': 'pdm',
            'GlobexOpen': 'daily_open', 
            'MidnightOpen': 'midnight_open', 
            'Open730': 'open_0730',
            'AsiaMid': 'asia_mid', 'LondonMid': 'london_mid', 'NY1Mid': 'ny1_mid', 'NY2Mid': 'ny2_mid'
        }
        
        # Context is based on NY Session (09:30-16:00)? Or Trading Day?
        # Usually Context (Red/Green) is based on "Prior Day Close vs Current Open". 
        # Or London Close vs NY Open? 
        # Code was using "London" vs "NY1".
        # Retain that logic for Context.
        
        try:
             ny1_st_time = pd.Timestamp(ny1['start_time'])
             london_st = pd.Timestamp(london['start_time'])
             l_open_idx = df.index.searchsorted(london_st)
             l_close_idx = df.index.searchsorted(ny1_st_time) - 1
             
             if l_open_idx < len(df) and l_close_idx >= 0:
                 l_open = df.iloc[l_open_idx]['open']
                 l_close = df.iloc[l_close_idx]['close']
                 context = 'Green' if l_close > l_open else 'Red'
             else:
                 context = 'Red' # Fallback
        except:
             context = 'Red'

        session_slice = df.loc[trading_start:trading_end]
        if session_slice.empty: continue
        
        s_high = session_slice['high'].max()
        s_low = session_slice['low'].min()
        
        # Open price for relative %: Daily Open seems best (18:00)
        try:
            d_open_row = df.iloc[df.index.searchsorted(trading_start)]
            base_open = d_open_row['open']
        except:
            if 'GlobexOpen' in day_levels: base_open = day_levels['GlobexOpen']
            else: continue

        for src_level, out_key in level_map.items():
            if src_level not in day_levels: continue
            lvl_price = day_levels[src_level]
            if lvl_price is None: continue
            
            # Ensure Level Key exists in stats
            if out_key not in stats['All']:
                for c in context_keys:
                    stats[c][out_key] = {'hits': 0, 'total': 0, 'times': [], 'rel_pcts': []}

            rel_pct = ((lvl_price - base_open) / base_open) * 100
            
            stats['All'][out_key]['total'] += 1
            stats['All'][out_key]['rel_pcts'].append(rel_pct)
            stats[context][out_key]['total'] += 1
            stats[context][out_key]['rel_pcts'].append(rel_pct)
            
            # --- Valid Window Filter ---
            # Don't count hits before the level exists.
            # Daily Open (Globex): 18:00.
            # Midnight: 00:00.
            # AsiaMid: 02:00 (End of Asia).
            # LondonMid: 07:00.
            # NY1Mid: 12:00.
            # NY2Mid: 16:00.
            
            valid_start = trading_start # Default
            
            if src_level == 'MidnightOpen':
                 valid_start = pd.Timestamp.combine(date_obj, time(0,1)).tz_localize('US/Eastern')
            elif src_level == 'Open730':
                 valid_start = pd.Timestamp.combine(date_obj, time(7,31)).tz_localize('US/Eastern')
            elif src_level == 'AsiaMid':
                 valid_start = pd.Timestamp.combine(date_obj, time(2,1)).tz_localize('US/Eastern')
            elif src_level == 'LondonMid':
                 valid_start = pd.Timestamp.combine(date_obj, time(7,1)).tz_localize('US/Eastern')
            elif src_level == 'NY1Mid': # Post 12:00
                 valid_start = pd.Timestamp.combine(date_obj, time(12,1)).tz_localize('US/Eastern')
            elif src_level == 'NY2Mid':
                 valid_start = pd.Timestamp.combine(date_obj, time(16,1)).tz_localize('US/Eastern')
            elif src_level == 'GlobexOpen':
                 # Don't count the open candle itself
                 valid_start = trading_start + timedelta(minutes=1)
            
            # Filter slice
            valid_slice = session_slice.loc[valid_start:]
            
            if valid_slice.empty: continue
            
            # Check hits
            # Since we have high/low of the full day, quick check first
            # But high/low of full day might include invalid times.
            # Must check valid_slice high/low
            v_high = valid_slice['high'].max()
            v_low = valid_slice['low'].min()
            
            if v_low <= lvl_price <= v_high:
                hits = valid_slice[(valid_slice['low'] <= lvl_price) & (valid_slice['high'] >= lvl_price)]
                if not hits.empty:
                    first_hit = hits.index[0]
                    # Calculate minutes from TRADING START (18:00)
                    hit_min = (first_hit - trading_start).total_seconds() / 60
                    
                    stats['All'][out_key]['hits'] += 1
                    stats['All'][out_key]['times'].append(hit_min)
                    
                    stats[context][out_key]['hits'] += 1
                    stats[context][out_key]['times'].append(hit_min)

    # Process Final JSON
    # print(f"DEBUG: Final Stats for PDH (All): {stats['All']['PDH']}")
    output = {}
    # Process Final JSON
    # print(f"DEBUG: Final Stats for PDH (All): {stats['All']['PDH']}")
    output = {}
    for ctx in context_keys:
        output[ctx] = {}
        # Iterate over all keys present in stats[ctx], not just the initial list
        for lvl in stats[ctx].keys():
            dat = stats[ctx][lvl]
            if dat['total'] == 0:
                output[ctx][lvl] = {
                    "rate": 0, 
                    "median": 0, 
                    "mode": 0, 
                    "avg_rel": 0,
                    "count": 0
                }
                continue
                
            rate = round((dat['hits'] / dat['total']) * 100, 1)
            times = dat['times']
            median = round(float(np.median(times)), 1) if times else 0
            mode = calculate_mode(times, bucket_size=5)
            
            # Average Relative % (Median is safer for outliers)
            if 'rel_pcts' in dat and dat['rel_pcts']:
                avg_rel = round(float(np.median(dat['rel_pcts'])), 3)
            else:
                avg_rel = 0
            
            output[ctx][lvl] = {
                "rate": rate,
                "median": median,
                "mode": mode,
                "avg_rel": avg_rel, # Median relative % distance
                "count": dat['total'],
                "hits": dat['hits'],
                "times": dat['times']
            }

    # Save
    out_path = DATA_DIR / f"{ticker}_level_stats.json"
    with open(out_path, 'w') as f:
        json.dump(output, f, indent=2)
        
    print(f"Saved stats to {out_path}")

if __name__ == "__main__":
    precompute_level_stats()
