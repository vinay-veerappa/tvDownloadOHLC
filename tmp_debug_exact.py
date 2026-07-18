"""Debug: replicate WebUI's exact medianBin and modeBin with unrounded values."""
import json, math, sys
from collections import defaultdict
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

# Use unadjusted daily_hod_lod
raw = json.load(open(r'C:\Users\vinay\tvDownloadOHLC\data\NQ1_daily_hod_lod_unadjusted.json'))

# Compute UNROUNDED pcts using daily_high/daily_low (matching WebUI RangeDistribution)
h_pcts = []
l_pcts = []
for d in lt_dates:
    if d in raw:
        e = raw[d]
        opn = e.get("daily_open", 0)
        dh = e.get("daily_high", 0)
        dl = e.get("daily_low", 0)
        if opn and opn > 0:
            h_pcts.append(((dh - opn) / opn) * 100)  # NOT rounded
            l_pcts.append(((dl - opn) / opn) * 100)  # NOT rounded

print(f"\nCount: {len(h_pcts)}")

# WebUI medianBin: sort, take Math.floor(sorted.length / 2), floor to bin
sorted_h = sorted(h_pcts)
sorted_l = sorted(l_pcts)
h_mid_idx = len(sorted_h) // 2  # = 17
l_mid_idx = len(sorted_l) // 2  # = 17
h_median_val = sorted_h[h_mid_idx]
l_median_val = sorted_l[l_mid_idx]
h_med_bin = math.floor(h_median_val / 0.1) * 0.1
l_med_bin = math.floor(l_median_val / 0.1) * 0.1

print(f"\n=== HIGH ===")
print(f"Sorted high values (index {h_mid_idx} = median):")
for i, v in enumerate(sorted_h):
    b = round(math.floor(v / 0.1) * 0.1, 1)
    marker = " ← MEDIAN" if i == h_mid_idx else ""
    print(f"  [{i:2d}] {v:.6f} → bin {b}{marker}")
print(f"Median value: {h_median_val:.6f} → bin {round(h_med_bin, 1)}")
print(f"WebUI shows: 0.7 to 0.8% (bin 0.7)")

print(f"\n=== LOW ===")
print(f"Sorted low values (index {l_mid_idx} = median):")
for i, v in enumerate(sorted_l):
    b = round(math.floor(v / 0.1) * 0.1, 1)
    marker = " ← MEDIAN" if i == l_mid_idx else ""
    print(f"  [{i:2d}] {v:.6f} → bin {b}{marker}")
print(f"Median value: {l_median_val:.6f} → bin {round(l_med_bin, 1)}")
print(f"WebUI shows: -0.8 to -0.7% (bin -0.8)")

# WebUI modeBin: build histogram, sort by count desc, pick first
h_buckets = defaultdict(int)
l_buckets = defaultdict(int)
for v in h_pcts:
    bucket = round(math.floor(v / 0.1) * 0.1, 1)
    h_buckets[bucket] += 1
for v in l_pcts:
    bucket = round(math.floor(v / 0.1) * 0.1, 1)
    l_buckets[bucket] += 1

# JS sort: Object.entries().sort((a,b) => b[1] - a[1]) — stable sort, keeps insertion order on ties
h_sorted = sorted(h_buckets.items(), key=lambda x: -x[1])
l_sorted = sorted(l_buckets.items(), key=lambda x: -x[1])

print(f"\n=== HIGH MODE ===")
print(f"Top 5 buckets (sorted by count desc):")
for b, c in h_sorted[:5]:
    print(f"  bin {b}: count={c}")
print(f"Mode: {h_sorted[0][0]} (bin {h_sorted[0][0]} → range {h_sorted[0][0]} to {h_sorted[0][0]+0.1}%)")
print(f"WebUI shows: 0.5 to 0.6% (bin 0.5)")

print(f"\n=== LOW MODE ===")
print(f"Top 5 buckets (sorted by count desc):")
for b, c in l_sorted[:5]:
    print(f"  bin {b}: count={c}")
print(f"Mode: {l_sorted[0][0]} (bin {l_sorted[0][0]} → range {l_sorted[0][0]} to {l_sorted[0][0]+0.1}%)")
print(f"WebUI shows: -0.3 to -0.2% (bin -0.3)")