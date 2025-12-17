import json
from collections import defaultdict

# Load profiler data
with open('data/NQ1_profiler.json', 'r') as f:
    data = json.load(f)

# Group by date
by_date = defaultdict(list)
for s in data:
    by_date[s['date']].append(s)

print(f"Total days: {len(by_date)}")
print(f"Days with 4 sessions: {sum(1 for d in by_date.values() if len(d) >= 4)}")

# Find daily HOD/LOD
hod_times = []
lod_times = []

for date, sessions in by_date.items():
    if len(sessions) < 2:
        continue
    
    max_h = max(s['range_high'] for s in sessions)
    min_l = min(s['range_low'] for s in sessions)
    
    for s in sessions:
        if s['range_high'] == max_h and s.get('high_time'):
            hod_times.append(s['high_time'])
            break
    
    for s in sessions:
        if s['range_low'] == min_l and s.get('low_time'):
            lod_times.append(s['low_time'])
            break

print(f"\nHOD times collected: {len(hod_times)}")
print(f"LOD times collected: {len(lod_times)}")

# Show sample times
print("\nSample HOD times:", hod_times[:10])
print("Sample LOD times:", lod_times[:10])

# Time distribution (by hour)
hod_hours = defaultdict(int)
lod_hours = defaultdict(int)

for t in hod_times:
    try:
        h = int(t.split(':')[0])
        hod_hours[h] += 1
    except:
        pass

for t in lod_times:
    try:
        h = int(t.split(':')[0])
        lod_hours[h] += 1
    except:
        pass

print("\nHOD by hour:")
for h in sorted(hod_hours.keys()):
    pct = 100 * hod_hours[h] / len(hod_times) if hod_times else 0
    print(f"  {h:02d}:00 - {hod_hours[h]:4d} ({pct:.1f}%)")

print("\nLOD by hour:")
for h in sorted(lod_hours.keys()):
    pct = 100 * lod_hours[h] / len(lod_times) if lod_times else 0
    print(f"  {h:02d}:00 - {lod_hours[h]:4d} ({pct:.1f}%)")

