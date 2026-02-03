
import json
from pathlib import Path

p = Path("data/NQ1_level_touches.json")
if p.exists():
    with open(p, 'r') as f:
        data = json.load(f)
        # partial view
        keys = list(data.keys())[:2]
        print(f"Sample Keys: {keys}")
        for k in keys:
            print(f"Entry {k}: {data[k].keys()}")
            # print sample level
            first_lvl = list(data[k].keys())[0]
            print(f"  Level '{first_lvl}': {data[k][first_lvl]}")
else:
    print("File not found")
