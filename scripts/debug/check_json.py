import json
with open('data/NQ1_level_touches.json', 'r') as f:
    d = json.load(f)
    print("Type:", type(d))
    if isinstance(d, dict) and len(d) > 0:
        first_key = list(d.keys())[0]
        print(f"Date: {first_key}")
        print("Data:", json.dumps(d[first_key], indent=2))
    else:
        print("Empty or invalid format")
