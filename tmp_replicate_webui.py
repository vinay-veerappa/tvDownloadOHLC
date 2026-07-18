"""Replicate WebUI's exact medianBin and modeBin logic."""
import json, math
from collections import defaultdict

raw = json.load(open(r'C:\Users\vinay\tvDownloadOHLC\data\NQ1_daily_hod_lod_unadjusted.json'))

# LF|LF → NY1 Long True dates
import sys
sys.path.insert(0, r'C:\Users\vinay\tvDownloadOHLC')
from scripts.testing.features.profiler.data import load_profiler
from scripts.testing.core.filter_engine import FilterEngine

sessions = load_profiler('NQ1')
engine = FilterEngine(sessions)
filters = {"Asia": "Long False", "London": "Long False"}
broken_filters = {}
dates = engine.apply("NY1", filters, broken_filters, "Any")

by_date = {}
for s in sessions:
    d = s.get("date")
    sn = s.get("session")
    if d and sn:
        by_date.setdefault(d, {})[sn] = s

lt_dates = [d for d in dates if by_date.get(d, {}).get("NY1", {}).get("status") == "Long True"]
print(f"Long True dates: {len(lt_dates)}")

# Compute percentages using WebUI's exact logic
# WebUI: ((daily_high - daily_open) / daily_open) * 100 (NOT rounded!)
h_pcts_raw = []
l_pcts_raw = []
for d in lt_dates:
    if d in raw:
        e = raw[d]
        opn = e.get("daily_open", 0)
        dh = e.get("daily_high", 0)
        dl = e.get("daily_low", 0)
        if opn and opn > 0:
            h_pcts_raw.append(((dh - opn) / opn) * 100)  # NOT rounded
            l_pcts_raw.append(((dl - opn) / opn) * 100)  # NOT rounded

print(f"\nHigh pcts (NOT rounded): {sorted(h_pcts_raw)}")
print(f"Low pcts (NOT rounded): {sorted(l_pcts_raw)}")

# WebUI medianBin: sort, take midIndex, floor to bin
sorted_h = sorted(h_pcts_raw)
sorted_l = sorted(l_pcts_raw)
h_mid = sorted_h[len(sorted_h) // 2]
l_mid = sorted_l[len(sorted_l) // 2]
h_med_bin = math.floor(h_mid / 0.1) * 0.1
l_med_bin = math.floor(l_mid / 0.1) * 0.1
print(f"\nHigh median value: {h_mid} → bin: {round(h_med_bin, 1)}")
print(f"Low median value: {l_mid} → bin: {round(l_med_bin, 1)}")

# WebUI modeBin: build histogram, sort by count desc, pick first
h_buckets = defaultdict(int)
l_buckets = defaultdict(int)
for v in h_pcts_raw:
    bucket = round(math.floor(v / 0.1) * 0.1, 1)
    h_buckets[bucket] += 1
for v in l_pcts_raw:
    bucket = round(math.floor(v / 0.1) * 0.1, 1)
    l_buckets[bucket] += 1

# Sort by count descending (WebUI sorts Object.entries by count)
h_sorted = sorted(h_buckets.items(), key=lambda x: -x[1])
l_sorted = sorted(l_buckets.items(), key=lambda x: -x[1])
print(f"\nHigh mode bins (sorted by count): {h_sorted[:5]}")
print(f"Low mode bins (sorted by count): {l_sorted[:5]}")
print(f"\nHigh mode: {h_sorted[0][0]} (count={h_sorted[0][1]})")
print(f"Low mode: {l_sorted[0][0]} (count={l_sorted[0][1]})")

# Compare with rounded values
h_pcts_rounded = [round(v, 2) for v in h_pcts_raw]
l_pcts_rounded = [round(v, 2) for v in l_pcts_raw]
print(f"\nHigh pcts (rounded to 2 decimals): {sorted(h_pcts_rounded)}")
print(f"Low pcts (rounded to 2 decimals): {sorted(l_pcts_rounded)}")