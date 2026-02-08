import json
import os

profiler_path = r"c:\Users\vinay\tvDownloadOHLC\data\NQ1_profiler.json"

if os.path.exists(profiler_path):
    with open(profiler_path, 'r') as f:
        data = json.load(f)
        
    print(f"Total Records: {len(data)}")
    
    # Check 'broken' values for London sessions
    london_broken = [row.get('broken') for row in data if row.get('session') == 'London']
    
    # Get unique values and counts
    from collections import Counter
    counts = Counter(london_broken)
    print("\nLondon 'broken' field values:")
    for k, v in counts.items():
        print(f"'{k}': {v}")
        
    # Check a sample record with broken != None
    for row in data:
        if row.get('session') == 'London' and row.get('broken') not in [None, "None", ""]:
            print("\nSample Broken Record:")
            print(row)
            break
else:
    print("File not found")
