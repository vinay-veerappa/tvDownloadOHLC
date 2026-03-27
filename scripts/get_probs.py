import json
import pandas as pd
from datetime import datetime, time
from collections import defaultdict

PROFILER_FILE = "c:/Users/vinay/tvDownloadOHLC/data/NQ1_profiler.json"

def calculate_probabilities(filters):
    with open(PROFILER_FILE) as f:
        data = json.load(f)
    
    # Group sessions by date
    days = defaultdict(dict)
    for row in data:
        date = row['date']
        session = row['session']
        days[date][session] = row

    # Target: NY1/NY2 probabilities
    matches_ny1 = []
    matches_ny2 = []
    for date, sessions in days.items():
        if not all(k in sessions for k in ['Asia', 'London', 'NY1']):
            continue
            
        # Extract features for filtering
        asia_status = sessions['Asia']['status']
        lon_status = sessions['London']['status']
        # Manual ALN logic
        asia_h, asia_l = sessions['Asia']['range_high'], sessions['Asia']['range_low']
        lon_h, lon_l = sessions['London']['range_high'], sessions['London']['range_low']
        aln = "Wait"
        if lon_h > asia_h and lon_l < asia_l: aln = "LEA"
        elif lon_h > asia_h and lon_l >= asia_l: aln = "LPEU"
        elif lon_l < asia_l and lon_h <= asia_h: aln = "LPED"
        elif lon_h <= asia_h and lon_l >= asia_l: aln = "AEL"

        # Match against filters
        is_match = True
        for k, v in filters.items():
            if k == 'aln' and aln != v: is_match = False
            if k == 'asia_status' and asia_status != v: is_match = False
            if k == 'lon_status' and lon_status != v: is_match = False
            
        if is_match:
            matches_ny1.append(sessions['NY1']['status'])
            if 'NY2' in sessions:
                matches_ny2.append(sessions['NY2']['status'])
            
    if not matches_ny1:
        return None, None, 0
        
    probs_ny1 = (pd.Series(matches_ny1).value_counts() / len(matches_ny1) * 100).to_dict()
    probs_ny2 = (pd.Series(matches_ny2).value_counts() / len(matches_ny2) * 100).to_dict() if matches_ny2 else {}
    return probs_ny1, probs_ny2, len(matches_ny1)

if __name__ == "__main__":
    current_filters = {
        'aln': 'LPED',
        'asia_status': 'Long False',
        'lon_status': 'Short True'
    }
    
    probs_ny1, probs_ny2, count = calculate_probabilities(current_filters)
    print(json.dumps({"count": count, "ny1": probs_ny1, "ny2": probs_ny2}, indent=2))
