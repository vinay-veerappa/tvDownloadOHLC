import requests
import json
from datetime import datetime

def check_api_data():
    url = "http://localhost:8000/api/sessions/ES1?range_type=hourly"
    print(f"Fetching {url}...")
    try:
        res = requests.get(url)
        res.raise_for_status()
        data = res.json()
        
        print(f"Received {len(data)} periods.")
        
        hourly = [d for d in data if d['type'] == '1H']
        three_hour = [d for d in data if d['type'] == '3H']
        
        print(f"\n1H Periods: {len(hourly)}")
        print(f"3H Periods: {len(three_hour)}")
        
        if not hourly or not three_hour:
            print("Missing data.")
            return

        # Sort by start_time
        hourly.sort(key=lambda x: x['start_time'])
        three_hour.sort(key=lambda x: x['start_time'])
        
        # Check first few items
        print("\n--- First 3 1H items ---")
        for x in hourly[:3]:
            print(f"{x['start_time']} -> {x['end_time']}")
            
        print("\n--- First 3 3H items ---")
        for x in three_hour[:3]:
            print(f"{x['start_time']} -> {x['end_time']}")

        # Align and Compare ALL bins
        print(f"\nScanning {len(three_hour)} 3H bins for mismatches...")
        mismatches = 0
        for th in three_hour:
            start_3h = th['start_time']
            # Find 1H bin with same start time
            # Optimization: create a lookup map
            h_map = {h['start_time']: h for h in hourly}
            
            match_1h = h_map.get(start_3h)
            
            if match_1h:
                y1 = match_1h['start_time'][:4]
                y3 = th['start_time'][:4]
                if y1 != y3:
                    print(f"❌ MISMATCH at {start_3h}: 1H={y1}, 3H={y3}")
                    mismatches += 1
            else:
                 # It's okay if 1H doesn't exist (maybe data starts mid-bin)
                 pass
                 
        if mismatches == 0:
            print("✅ No year mismatches found in any aligned bins.")
        else:
            print(f"❌ Found {mismatches} mismatches.")

        # Also print last items to confirm range
        print("\n--- Last items ---")
        print(f"1H Last: {hourly[-1]['start_time']}")
        print(f"3H Last: {three_hour[-1]['start_time']}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_api_data()
