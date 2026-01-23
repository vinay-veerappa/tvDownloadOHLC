
import pandas as pd
import json
import time
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# Import logic from service
import sys
import os
sys.path.append(os.getcwd())

from api.services.profiler_service import ProfilerService

def precompute_ticker(ticker="NQ1", days=10000):
    print(f"Loading data for {ticker} (Lookback: {days} days)...")
    
    print("Running analysis...")
    start = time.time()
    
    # Analyze from service
    result = ProfilerService.analyze_profiler_stats(ticker, days=days, force=True)
    
    if "error" in result:
        print(f"Error: {result['error']}")
        return

    new_sessions = result["sessions"]
    elapsed = time.time() - start
    print(f"Analyzed {len(new_sessions)} sessions in {elapsed:.2f}s")
    
    # If we are doing a partial update (days < 500), merge with existing JSON
    output_file = Path(f"data/{ticker}_profiler.json")
    if days < 1000 and output_file.exists():
        with open(output_file, 'r') as f:
            existing_sessions = json.load(f)
        
        # Merge logic: use new sessions for overlapping dates
        # Dictionary keyed by (date, session)
        session_map = { (s['date'], s['session']): s for s in existing_sessions }
        for s in new_sessions:
            session_map[(s['date'], s['session'])] = s
            
        final_sessions = list(session_map.values())
        final_sessions.sort(key=lambda x: x['start_ts'] if 'start_ts' in x else x['start_time'])
        print(f"Merged {len(new_sessions)} new sessions into existing {len(existing_sessions)} total sessions.")
    else:
        final_sessions = new_sessions

    # Enrich with Daily Data (High/Low/Open) from NQ1_daily_hod_lod.json
    try:
        daily_json_path = Path(f"data/{ticker}_daily_hod_lod.json")
        if daily_json_path.exists():
            with open(daily_json_path) as f:
                daily_data = json.load(f)
            
            enrich_count = 0
            for s in final_sessions:
                d = s.get('date')
                if d and d in daily_data:
                    day_info = daily_data[d]
                    s['daily_open'] = day_info.get('daily_open')
                    s['daily_high'] = day_info.get('daily_high')
                    s['daily_low'] = day_info.get('daily_low')
                    enrich_count += 1
            print(f"Enriched {enrich_count} sessions with daily stats.")
    except Exception as e:
        print(f"Enrichment Error: {e}")

    # Save to JSON
    with open(output_file, "w") as f:
        json.dump(final_sessions, f, indent=2)
        
    print(f"Saved to {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Precompute Profiler Stats")
    parser.add_argument("ticker", nargs="?", default="NQ1", help="Ticker (or 'ALL')")
    parser.add_argument("--days", type=int, default=10000, help="Number of days to analyze")
    args = parser.parse_args()
    
    tickers = ["NQ1", "ES1", "GC1", "CL1", "RTY1", "YM1"]
    
    if args.ticker.upper() == "ALL":
        for t in tickers:
            precompute_ticker(t, days=args.days)
    else:
        precompute_ticker(args.ticker, days=args.days)
