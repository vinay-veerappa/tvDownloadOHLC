import argparse
import json
import requests
import sys
import os
import pandas as pd
from datetime import datetime
import pytz

# Add project root to sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)


import sys
from pathlib import Path

# Add project root to sys.path dynamically
_current_dir = Path(__file__).resolve().parent
while _current_dir.name and _current_dir.name != "scripts":
    _current_dir = _current_dir.parent
if _current_dir.name == "scripts":
    _root_dir = str(_current_dir.parent)
    if _root_dir not in sys.path:
        sys.path.insert(0, _root_dir)

from scripts.utils.fused_data_loader import load_fused_data
from scripts.libs_py.nqstats.engine import NQStatsEngine

def get_current_session_info(now_et):
    """Determine target session and relevant preceding sessions based on current ET time."""
    t = now_et.time()
    
    # Session Windows (Approximate logic for context)
    # Asia: 18:00 - 02:30
    # London: 02:30 - 07:30
    # NY1: 07:30 - 11:30
    # NY2: 11:30 - 17:00
    
    if t >= datetime.strptime("18:00", "%H:%M").time() or t < datetime.strptime("02:30", "%H:%M").time():
        return "Asia", [] # Target: Asia, Filters: None (start of day)
    elif t < datetime.strptime("07:30", "%H:%M").time():
        return "London", ["asiabox_status"]
    elif t < datetime.strptime("11:30", "%H:%M").time():
        return "NY1", ["asiabox_status", "londonbox_status"]
    elif t < datetime.strptime("17:00", "%H:%M").time():
        return "NY2", ["asiabox_status", "londonbox_status", "ny1box_status"]
    else:
        return "Post-Market", ["asiabox_status", "londonbox_status", "ny1box_status", "ny2box_status"]

def main():
    parser = argparse.ArgumentParser(description="Live Profiler Context Dashboard")
    parser.add_argument("--ticker", type=str, default="NQ1", help="Ticker (default: NQ1)")
    parser.add_argument("--api-url", type=str, default="http://127.0.0.1:8000/stats/filtered-stats", help="Profiler API URL")
    args = parser.parse_args()

    # 1. Load data and get latest status
    print(f"🔄 Syncing live data for {args.ticker}...")
    df = load_fused_data(args.ticker)
    if df is None or df.empty:
        print("❌ Could not load data.")
        return

    # Use NStatsEngine to figure out what just happened
    engine = NQStatsEngine(df, ticker=args.ticker)
    latest = engine.get_latest_status()
    
    now_et = datetime.now(pytz.timezone('US/Eastern'))
    current_session, filter_keys = get_current_session_info(now_et)
    
    # Get context for the current session (Yesterday's NY context for today's Asia)
    # We find the row index for today's data, and look one row back if in Asia
    # Using 'prev_ny1_status' etc from the engine now.
    
    # Locate today's row (-1 or similar)
    curr_date_row = engine.stats.tail(1).iloc[0]
    
    # 2. Extract Context (Transition Matrix)
    # When in Asia, we filter by Prev NY1, Prev NY2
    filters = {}
    broken_filters = {}
    
    if current_session == 'Asia':
        prev_ny1 = str(curr_date_row.get('prev_ny1_status', 'None'))
        prev_ny2 = str(curr_date_row.get('prev_ny2_status', 'None'))
        
        if prev_ny1 != 'None': filters['Prev NY1'] = prev_ny1
        if prev_ny2 != 'None': filters['Prev NY2'] = prev_ny2
        
        # Broken status check for previous day's sessions
        if curr_date_row.get('prev_ny1_broken'): broken_filters['Prev NY1'] = "Broken"
        if curr_date_row.get('prev_ny2_broken'): broken_filters['Prev NY2'] = "Broken"
        
    elif current_session == 'London':
        # London context: Asia status (today) + Prev NY2
        curr_asia = str(curr_date_row.get('asiabox_status', 'None'))
        prev_ny2 = str(curr_date_row.get('prev_ny2_status', 'None'))
        
        if curr_asia != 'None': filters['Asia'] = curr_asia
        if prev_ny2 != 'None': filters['Prev NY2'] = prev_ny2
        
    elif current_session in ['NY1', 'NY2']:
        # NY context: Asia status + London status
        curr_asia = str(curr_date_row.get('asiabox_status', 'None'))
        curr_lon = str(curr_date_row.get('londonbox_status', 'None'))
        
        if curr_asia != 'None': filters['Asia'] = curr_asia
        if curr_lon != 'None': filters['London'] = curr_lon

    # Extract current session's intra-session state
    # e.g. if we are in London and it's already Long True, we use intra_state='Long'
    current_status = str(curr_date_row.get(f'{current_session.lower()}box_status', 'None'))
    intra_state = 'Any'
    if 'Long' in current_status: intra_state = 'Long'
    elif 'Short' in current_status: intra_state = 'Short'

    print(f"\n[Context] Current Session: {current_session} | Status: {current_status}")
    print(f"[Filters] {filters} | Intra-State: {intra_state}")

    # 3. Call API
    print("\n--- API Statistical Update ---")
    try:
        combinations_url = f"http://127.0.0.1:8000/api/profiler/combinations?ticker={args.ticker}&target_session={current_session}&intra_state={intra_state}"
        # Filter dict goes in POST? No, my MCP tool said GET with parameters.
        # Actually my GET took Dict as optional. Let's build query string properly or send JSON.
        # Fastapi usually takes dict in query as JSON strings or repeated keys.
        
        # Let's use the MCP Data Bridge directly since we are an agent, 
        # but here we are in a script, so we use requests.
        # My FastAPI endpoint for combinations uses query params.
        
        # Updated request with filters
        import json
        filters_json = json.dumps(filters)
        broken_json = json.dumps(broken_filters)
        
        final_url = f"{combinations_url}&filters={filters_json}&broken_filters={broken_json}"
        response = requests.get(final_url)
        stats = response.json()
        
        if 'error' in stats:
            print(f"API Error: {stats['error']}")
            return

        print(f"Matched Dates: {len(stats.get('dates', []))}")
        dist = stats.get('distribution', {})
        print("\nSession Outcomes (Transition Probabilities):")
        total = stats.get('count', 0)
        for outcome, count in dist.items():
            prob = (count / total * 100) if total > 0 else 0
            print(f"  {outcome:12}: {prob:5.1f}% ({count})")
            
        print("\n--- Analysis Complete ---")
        
    except Exception as e:
        print(f"API Connection Failed: {e}")

    print(f"\n==================================================")
    print(f"📊 LIVE INSTITUTIONAL PROFILER: {args.ticker}")
    print(f"Current Time (ET): {now_et.strftime('%H:%M:%S')}")
    print(f"Target Session:    {target_session}")
    print(f"Detected Status:   {filters}")
    print(f"Detected Broken:   {broken_filters}")
    print(f"==================================================")

    # 4. Query the API
    payload = {
        "ticker": args.ticker,
        "target_session": target_session,
        "filters": filters,
        "broken_filters": broken_filters,
        "intra_state": "Any"
    }

    try:
        response = requests.post(args.api_url, json=payload, timeout=5)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"\n❌ API Error: {e}")
        print("   Make sure the FastAPI server is running: python api/main.py")
        return

    count = data.get("count", 0)
    dist = data.get("distribution", {})
    
    if count == 0:
        print("\n⚠️ No historical matches for this specific combination.")
        return

    print(f"\n[ HISTORICAL OUTCOMES FOR THIS CONTEXT ]")
    print(f"Sample Size: {count} matching days\n")
    
    # Order: Long True, Long False, Short True, Short False, None
    order = ["Long True", "Long False", "Short True", "Short False", "None"]
    for status in order:
        hits = dist.get(status, 0)
        prob = (hits / count) * 100
        bar = "█" * int(prob / 5)
        print(f"{status:12}: {prob:5.1f}% ({hits:3} hits) {bar}")

    range_stats = data.get("range_stats", {})
    if range_stats:
        print(f"\n[ RANGE EXPECTANCY ]")
        h_med = range_stats.get("high_pct", {}).get("median")
        l_med = range_stats.get("low_pct", {}).get("median")
        print(f"High % Median: {h_med:+6.2f}%")
        print(f"Low  % Median: {l_med:+6.2f}%")

    print(f"\n[ LATEST LEVELS ]")
    print(f"Asia Mid:   {latest.get('asia_mid', 0):.2f}")
    print(f"London Mid: {latest.get('london_mid', 0):.2f}")
    print(f"NY1 Mid:    {latest.get('ny1_mid', 0):.2f}")
    print(f"P12 (Settle): {latest.get('p12', 0):.2f}")

    print("\n" + "="*50)

if __name__ == "__main__":
    main()
