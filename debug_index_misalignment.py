"""Verify the index misalignment between adjusted and unadjusted daily HOD/LOD data."""
import json
from pathlib import Path

_DATA = Path(__file__).parent / "data"

adj = json.load(open(_DATA / "NQ1_daily_hod_lod.json"))
unadj = json.load(open(_DATA / "NQ1_daily_hod_lod_unadjusted.json"))
adj_dates = sorted(adj.keys())
unadj_dates = sorted(unadj.keys())
print(f"Adjusted dates: {len(adj_dates)}")
print(f"Unadjusted dates: {len(unadj_dates)}")

# Find 2020-04-09 in both
target = "2020-04-09"
adj_idx = adj_dates.index(target) if target in adj_dates else -1
unadj_idx = unadj_dates.index(target) if target in unadj_dates else -1
print(f"\n{target}: adj_idx={adj_idx}, unadj_idx={unadj_idx}")

# What does the unadjusted data have at the ADJUSTED index?
# This is what the WebUI merge does: it uses adj dates but unadj prices
if adj_idx >= 0 and adj_idx < len(unadj_dates):
    mismatch_date = unadj_dates[adj_idx]
    rec = unadj[mismatch_date]
    print(f"\nUnadjusted date at adj_idx={adj_idx}: {mismatch_date}")
    print(f"  open={rec.get('daily_open')}, high={rec.get('daily_high')}, low={rec.get('daily_low')}")

# Check how many dates differ
adj_set = set(adj_dates)
unadj_set = set(unadj_dates)
only_adj = adj_set - unadj_set
only_unadj = unadj_set - adj_set
print(f"\nDates only in adjusted: {len(only_adj)}")
print(f"Dates only in unadjusted: {len(only_unadj)}")
print(f"Dates in both: {len(adj_set & unadj_set)}")

if only_adj:
    print(f"  First 5 adj-only: {sorted(only_adj)[:5]}")
if only_unadj:
    print(f"  First 5 unadj-only: {sorted(only_unadj)[:5]}")

# Show the misalignment for the first 10 dates
print(f"\n--- First 10 dates: index alignment ---")
print(f"{'Idx':<6} {'Adj Date':<12} {'Unadj Date':<12} {'Match':<8}")
for i in range(min(10, len(adj_dates), len(unadj_dates))):
    match = "YES" if adj_dates[i] == unadj_dates[i] else "NO"
    print(f"{i:<6} {adj_dates[i]:<12} {unadj_dates[i]:<12} {match:<8}")

# Find where they first diverge
for i in range(min(len(adj_dates), len(unadj_dates))):
    if adj_dates[i] != unadj_dates[i]:
        print(f"\nFirst divergence at index {i}:")
        print(f"  Adj[{i}] = {adj_dates[i]}")
        print(f"  Unadj[{i}] = {unadj_dates[i]}")
        break
else:
    if len(adj_dates) == len(unadj_dates):
        print("\nNo divergence found — arrays are identical")
    else:
        shorter = min(len(adj_dates), len(unadj_dates))
        print(f"\nArrays match up to index {shorter-1}, but have different lengths")