
import json
from pathlib import Path

def check_file(name):
    p = Path(f"data/{name}")
    if not p.exists():
        print(f"MISSING: {name}")
        return

    try:
        with open(p, "r") as f:
            data = json.load(f)
        
        print(f"--- {name} ---")
        print(f"Type: {type(data)}")
        if isinstance(data, dict):
            keys = list(data.keys())
            print(f"Keys: {len(keys)}")
            print(f"Top keys: {keys[:5]}")
            
            # Check for 'daily' key specifically
            if 'daily' in data:
                daily_data = data['daily']
                print(f"--- 'daily' sub-keys ---")
                print(f"Count: {len(daily_data)}")
                d_keys = list(daily_data.keys())
                print(f"Sample keys: {d_keys[:3]}")
                if d_keys:
                    print(f"First item: {daily_data[d_keys[0]]}")
            
            # print first 3 items (top level)
            count = 0
            for k, v in data.items():
                print(f"  {k}: {v}")
                count += 1
                if count >= 3: break
        elif isinstance(data, list):
            print(f"List Length: {len(data)}")
            print(f"  First item: {data[0] if data else 'Empty'}")
            
    except Exception as e:
        print(f"ERROR reading {name}: {e}")

check_file("NQ1_hod_lod.json")
check_file("NQ1_level_touches.json")
check_file("NQ1_profiler.json")
