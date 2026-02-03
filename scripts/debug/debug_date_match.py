
import json
from pathlib import Path

def get_keys(name, is_list=False):
    p = Path(f"data/{name}")
    if not p.exists():
        print(f"MISSING: {name}")
        return set()
    
    with open(p, "r") as f:
        data = json.load(f)
        
    if is_list:
        keys = set()
        for item in data:
            if 'date' in item:
                keys.add(item['date'])
        print(f"{name}: {len(keys)} unique dates (from list)")
        return keys
    else:
        keys = set(data.keys())
        print(f"{name}: {len(keys)} keys")
        return keys

keys_prof = get_keys("NQ1_profiler.json", is_list=True)
keys_hl = get_keys("NQ1_hod_lod.json")
keys_touch = get_keys("NQ1_level_touches.json")

print(f"Profiler Dates sample: {list(keys_prof)[:3]}")
print(f"HOD/LOD Keys sample: {list(keys_hl)[:3]}")

common_hl = keys_prof.intersection(keys_hl)
print(f"Intersection (Profiler & HOD/LOD): {len(common_hl)}")

common_touch = keys_prof.intersection(keys_touch)
print(f"Intersection (Profiler & Touches): {len(common_touch)}")
