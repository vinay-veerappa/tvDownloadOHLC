
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
            print(f"Top keys: {keys[:3]}")
    except Exception as e:
        print(f"ERROR reading {name}: {e}")

check_file("NQ1_daily_hod_lod.json")
