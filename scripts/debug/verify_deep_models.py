import json
from pathlib import Path
from collections import Counter
import requests

URL = 'http://localhost:8000/stats/filtered-price-model'

def analyze_ticker(ticker):
    prof_path = Path('data') / f'{ticker}_profiler.json'
    if not prof_path.exists(): return
    
    with open(prof_path, 'r') as f: data = json.load(f)
    
    days = {}
    for entry in data:
        d = entry['date']
        if d not in days: days[d] = {}
        sess = entry['session']
        status = entry['status']
        broken = entry.get('broken', False)
        days[d][sess] = {'status': status, 'broken': broken}
    
    # We want to support sequential models
    # Phase 1: Asia only (4 combos)
    # Phase 2: Asia + Lon (16 combos)
    # Phase 3: Asia + Lon + NY1 (64 combos)
    # We will ignore 'Broken' for the model combinations if count is too low,
    # but the user explicitly asked for Broken.
    # Let's see if the counts are high enough for Broken filters.
    
    def get_c(filters, broken_filters):
        payload = {'ticker': ticker, 'target_session': 'Daily', 'filters': filters, 'broken_filters': broken_filters, 'bucket_minutes': 5}
        try:
            res = requests.post(URL, json=payload, timeout=5)
            return res.json().get('count', 0)
        except: return 0

    print(f"\n--- Analysis for {ticker} ---")
    
    # The user's specific test case
    c1 = get_c({'Asia': 'Long True'}, {'Asia': 'Broken'})
    c2 = get_c({'Asia': 'Long True', 'London': 'Long False'}, {'Asia': 'Broken', 'London': 'Broken'})
    c3 = get_c({'Asia': 'Long True', 'London': 'Long False', 'NY1': 'Long True'}, {'Asia': 'Broken', 'London': 'Broken'})
    c4 = get_c({'Asia': 'Long True', 'London': 'Long False', 'NY1': 'Long False'}, {'Asia': 'Broken', 'London': 'Broken'})
    
    print(f"1. Asia=LTB: {c1} days")
    print(f"2. Asia=LTB + Lon=LFB: {c2} days")
    print(f"3. Asia=LTB + Lon=LFB + NY1=LT: {c3} days")
    print(f"4. Asia=LTB + Lon=LFB + NY1=LF: {c4} days")

analyze_ticker('NQ1')
analyze_ticker('ES1')
