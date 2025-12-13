
import sys
import os
import pandas as pd
import json
sys.path.append(os.getcwd())

from api.services.profiler_service import ProfilerService

def debug_api_logic():
    # Simulate the payload received by the API
    payload = {
        "ticker": "NQ1",
        "target_session": "NY1",
        "filters": {"London": "Long True"},
        "broken_filters": {},
        "intra_state": "Any"
    }

    ticker = payload.get("ticker", "NQ1")
    target_session = payload.get("target_session", "NY1")
    filters = payload.get("filters", {})
    broken_filters = payload.get("broken_filters", {})
    intra_state = payload.get("intra_state", "Any")
    
    print(f"Calling ProfilerService.get_filtered_stats with:")
    print(f"Ticker: {ticker}")
    print(f"Target Session: {target_session}")
    print(f"Filters: {filters}")
    
    result = ProfilerService.get_filtered_stats(
        ticker, target_session, filters, broken_filters, intra_state
    )
    
    if "error" in result:
        print(f"Error: {result['error']}")
    else:
        print(f"Success! Matched Dates Count: {result.get('count')}")
        print(f"First 5 Matched Dates: {result.get('matched_dates')[:5]}")

if __name__ == "__main__":
    debug_api_logic()
