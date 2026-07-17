"""Calculate combinatorics of profiler context space and test feasibility."""
import sys
from pathlib import Path
_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import json
from collections import defaultdict

DATA = _REPO / "data"

# Load profiler data
with open(DATA / "NQ1_profiler.json") as f:
    sessions = json.load(f)

# Build pivot
pivot = {}
for s in sessions:
    d = s.get("date")
    sess = s.get("session")
    if d and sess:
        if d not in pivot:
            pivot[d] = {}
        pivot[d][sess] = s
dates = sorted(pivot.keys())

# All possible statuses (excluding None for context — None means "not yet happened")
ALL_STATUSES = ["Long True", "Long False", "Short True", "Short False"]

# ── Count actual unique context keys in the data ──
asia_keys = set()
london_keys = set()
ny1_keys = set()
ny2_keys = set()

for i, curr_date in enumerate(dates):
    if i == 0:
        continue
    prev_date = dates[i - 1]

    curr = pivot.get(curr_date, {})
    prev = pivot.get(prev_date, {})

    # Asia: prev NY1 + prev NY2
    p_ny1 = prev.get("NY1", {}).get("status", "")
    p_ny2 = prev.get("NY2", {}).get("status", "")
    if p_ny1 in ALL_STATUSES and p_ny2 in ALL_STATUSES:
        asia_keys.add(f"{p_ny1}|{p_ny2}")

    # London: curr Asia + prev NY2
    c_asia = curr.get("Asia", {}).get("status", "")
    if c_asia in ALL_STATUSES and p_ny2 in ALL_STATUSES:
        london_keys.add(f"{c_asia}|{p_ny2}")

    # NY1: curr Asia + curr London
    c_lon = curr.get("London", {}).get("status", "")
    if c_asia in ALL_STATUSES and c_lon in ALL_STATUSES:
        ny1_keys.add(f"{c_asia}|{c_lon}")

    # NY2: curr Asia + curr London + curr NY1
    c_ny1 = curr.get("NY1", {}).get("status", "")
    if c_asia in ALL_STATUSES and c_lon in ALL_STATUSES and c_ny1 in ALL_STATUSES:
        ny2_keys.add(f"{c_asia}|{c_lon}|{c_ny1}")

print("=" * 60)
print("COMBINATORICS: Profiler Context Space")
print("=" * 60)

print(f"\nTheoretical maximum (4 statuses per session):")
print(f"  Asia:   4 x 4 = 16  (prev NY1 x prev NY2)")
print(f"  London: 4 x 4 = 16  (curr Asia x prev NY2)")
print(f"  NY1:    4 x 4 = 16  (curr Asia x curr London)")
print(f"  NY2:    4 x 4 x 4 = 64  (curr Asia x curr London x curr NY1)")
print(f"  TOTAL:  112 unique context keys")

print(f"\nActually observed in {len(dates)} trading days:")
print(f"  Asia:   {len(asia_keys)} keys  (theoretical max: 16)")
print(f"  London: {len(london_keys)} keys  (theoretical max: 16)")
print(f"  NY1:    {len(ny1_keys)} keys  (theoretical max: 16)")
print(f"  NY2:    {len(ny2_keys)} keys  (theoretical max: 64)")
print(f"  TOTAL:  {len(asia_keys) + len(london_keys) + len(ny1_keys) + len(ny2_keys)} keys")

# ── Sample size distribution ──
print(f"\n{'='*60}")
print("SAMPLE SIZE DISTRIBUTION (how many days per context key)")
print(f"{'='*60}")

def count_samples(target_session, context_keys):
    """Count how many historical days match each context key."""
    counts = defaultdict(int)
    for i, curr_date in enumerate(dates):
        if i == 0:
            continue
        prev_date = dates[i - 1]
        curr = pivot.get(curr_date, {})
        prev = pivot.get(prev_date, {})

        if target_session == "Asia":
            p_ny1 = prev.get("NY1", {}).get("status", "")
            p_ny2 = prev.get("NY2", {}).get("status", "")
            if p_ny1 in ALL_STATUSES and p_ny2 in ALL_STATUSES:
                key = f"{p_ny1}|{p_ny2}"
                if curr.get("Asia", {}).get("status") in ALL_STATUSES:
                    counts[key] += 1
        elif target_session == "London":
            c_asia = curr.get("Asia", {}).get("status", "")
            p_ny2 = prev.get("NY2", {}).get("status", "")
            if c_asia in ALL_STATUSES and p_ny2 in ALL_STATUSES:
                key = f"{c_asia}|{p_ny2}"
                if curr.get("London", {}).get("status") in ALL_STATUSES:
                    counts[key] += 1
        elif target_session == "NY1":
            c_asia = curr.get("Asia", {}).get("status", "")
            c_lon = curr.get("London", {}).get("status", "")
            if c_asia in ALL_STATUSES and c_lon in ALL_STATUSES:
                key = f"{c_asia}|{c_lon}"
                if curr.get("NY1", {}).get("status") in ALL_STATUSES:
                    counts[key] += 1
        elif target_session == "NY2":
            c_asia = curr.get("Asia", {}).get("status", "")
            c_lon = curr.get("London", {}).get("status", "")
            c_ny1 = curr.get("NY1", {}).get("status", "")
            if c_asia in ALL_STATUSES and c_lon in ALL_STATUSES and c_ny1 in ALL_STATUSES:
                key = f"{c_asia}|{c_lon}|{c_ny1}"
                if curr.get("NY2", {}).get("status") in ALL_STATUSES:
                    counts[key] += 1
    return counts

for sess in ["Asia", "London", "NY1", "NY2"]:
    counts = count_samples(sess, None)
    vals = sorted(counts.values())
    if vals:
        print(f"\n  {sess}: {len(counts)} keys, samples range {vals[0]}-{vals[-1]}")
        print(f"    p10={vals[len(vals)//10]}, p50={vals[len(vals)//2]}, p90={vals[len(vals)*9//10]}")
        # Show smallest and largest
        sorted_items = sorted(counts.items(), key=lambda x: x[1])
        print(f"    Smallest: {sorted_items[0][0]} -> {sorted_items[0][1]} samples")
        print(f"    Largest:  {sorted_items[-1][0]} -> {sorted_items[-1][1]} samples")

# ── What would the precomputed file look like? ──
print(f"\n{'='*60}")
print("ESTIMATED PRECOMPUTED FILE SIZE")
print(f"{'='*60}")

# Each context key entry: ~200 bytes (key + probs + price_stats + broken_rates + hod_lod_times)
total_keys = len(asia_keys) + len(london_keys) + len(ny1_keys) + len(ny2_keys)
est_size = total_keys * 250  # bytes per entry, generous
print(f"  {total_keys} context keys x ~250 bytes = ~{est_size/1024:.0f} KB")
print(f"  Compare to current: profiler.json (14,049 KB) + level_touches.json (52,118 KB)")
print(f"  That's a {66000/est_size*1024:.0f}x reduction in data loaded per call!")

# ── What about broken filter? ──
print(f"\n{'='*60}")
print("BROKEN FILTER: Does it need separate keys?")
print(f"{'='*60}")
print("  The broken filter is ASYMMETRIC:")
print("    - If live is NOT broken -> match any historical (both broken and held)")
print("    - If live IS broken -> historical MUST also be broken")
print("  So we need TWO lookup tables per context key:")
print("    - broken_filter=False: all matching days (status match only)")
print("    - broken_filter=True:  only days where context sessions were ALSO broken")
print("  This doubles the keys: {total_keys * 2} total entries")
print(f"  Estimated size: ~{total_keys * 2 * 250 / 1024:.0f} KB")
