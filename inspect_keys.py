
import json
from pathlib import Path

path = Path("data/NQ1_daily_hod_lod.json")
with open(path, "r") as f:
    data = json.load(f)
    
print(f"Data type: {type(data)}")
if isinstance(data, dict):
    keys = list(data.keys())
    first_key = keys[0]
    print(f"Sample Date: {first_key}")
    print("Keys found:", list(data[first_key].keys()))
    print("Values:", data[first_key])
