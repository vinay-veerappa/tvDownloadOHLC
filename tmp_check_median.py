"""Check JavaScript sort vs Python sort for median."""
import json, math

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

# Compute UNROUNDED low pcts (matching WebUI exactly)
l_pcts = []
for d in lt_dates:
    if d in raw:
        e = raw[d]
        opn = e.get("daily_open", 0)
        dl = e.get("daily_low", 0)
        if opn and opn > 0:
            l_pcts.append(((dl - opn) / opn) * 100)  # NOT rounded, matching WebUI

# Sort (JavaScript's sort with (a,b) => a-b is same as Python's sorted)
sorted_l = sorted(l_pcts)
print(f"Count: {len(sorted_l)}")
print(f"Sorted values:")
for i, v in enumerate(sorted_l):
    bin_start = math.floor(v / 0.1) * 0.1
    print(f"  [{i}] {v:.6f} → bin {round(bin_start, 1)}")

# WebUI: Math.floor(sorted.length / 2) = 17
mid = len(sorted_l) // 2  # = 17
print(f"\nMedian index: {mid}")
print(f"Median value: {sorted_l[mid]:.6f}")
print(f"Median bin: {round(math.floor(sorted_l[mid] / 0.1) * 0.1, 1)}")

# But wait — the WebUI shows -0.8 to -0.7%. That's bin -0.8.
# Let's check: is the WebUI using a different data source?
# The useDailyHodLod hook fetches BOTH adjusted and unadjusted and MERGES them.
# Adjusted times + unadjusted prices.
# But what about daily_high and daily_low? Those come from unadjusted.

# Let's check if the adjusted file has different daily_high/daily_low
adj = json.load(open(r'C:\Users\vinay\tvDownloadOHLC\data\NQ1_daily_hod_lod.json'))
print("\n=== ADJUSTED vs UNADJUSTED ===")
for d in lt_dates:
    if d in raw and d in adj:
        r = raw[d]
        a = adj[d]
        if r.get("daily_low") != a.get("daily_low") or r.get("daily_high") != a.get("daily_high"):
            print(f"  {d}: adjusted low={a.get('daily_low')} unadj low={r.get('daily_low')}")
            print(f"  {d}: adjusted high={a.get('daily_high')} unadj high={r.get('daily_high')}")