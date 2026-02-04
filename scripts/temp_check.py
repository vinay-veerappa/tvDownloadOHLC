import json

# Load unadjusted data
with open('data/NQ1_daily_hod_lod_unadjusted.json', 'r') as f:
    data = json.load(f)

dates = sorted(data.keys())
print(f"Total dates in JSON: {len(dates)}")
print(f"Date range: {dates[0]} to {dates[-1]}")
print(f"\nLast 10 dates:")
for d in dates[-10:]:
    entry = data[d]
    o = entry.get('daily_open')
    h = entry.get('daily_high') or entry.get('hod_price')
    l = entry.get('daily_low') or entry.get('lod_price')
    if o and o > 0:
        h_pct = round((h - o) / o * 100, 2)
        l_pct = round((l - o) / o * 100, 2)
    else:
        h_pct = l_pct = 'N/A'
    print(f"  {d}: open={o}, high={h}, low={l}, h_pct={h_pct}, l_pct={l_pct}")
