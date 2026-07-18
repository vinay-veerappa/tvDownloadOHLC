"""Debug the count off-by-1 issue for LT|LT filter."""
import json
from collections import defaultdict
from pathlib import Path

_DATA = Path(__file__).parent / "data"

# Load sessions
sessions = json.load(open(_DATA / "NQ1_profiler.json"))
if isinstance(sessions, dict):
    sessions = sessions.get("sessions", [])

# Build pivot
by_date = defaultdict(dict)
for s in sessions:
    by_date[s["date"]][s["session"]] = s
dates = sorted(by_date.keys())

# Load lookup table
lookup = json.load(open(_DATA / "derived" / "NQ1_profiler_lookup.json"))
lk_count = lookup["tables"]["NY1"]["LT|LT"]["samples"]
print(f"Lookup table LT|LT count: {lk_count}")

# Apply filter: Asia=Long True, London=Long True -> NY1 target
matched = []
for date in dates:
    sess_map = by_date[date]
    asia = sess_map.get("Asia", {})
    london = sess_map.get("London", {})
    ny1 = sess_map.get("NY1", {})
    if asia.get("status") == "Long True" and london.get("status") == "Long True":
        matched.append(date)

print(f"Local filter LT|LT count: {len(matched)}")
print(f"Diff: {len(matched) - lk_count}")

# Now simulate what the generator does: skip first date if needs_prev
# For NY1, needs_prev = False, so first date is NOT skipped
# But let's check: does the generator skip dates where context is invalid?
# The generator checks: if status not in ALL_STATUSES: valid = False
# Let's check each matched date for valid context
ALL_STATUSES = ["Long True", "Long False", "Short True", "Short False"]

generator_matched = []
for i, curr_date in enumerate(dates):
    curr = by_date.get(curr_date, {})
    # NY1 context: Asia (curr), London (curr)
    asia = curr.get("Asia", {})
    london = curr.get("London", {})
    asia_status = asia.get("status", "")
    london_status = london.get("status", "")
    if asia_status not in ALL_STATUSES or london_status not in ALL_STATUSES:
        continue
    # Target: NY1
    ny1 = curr.get("NY1", {})
    ny1_status = ny1.get("status", "")
    if ny1_status not in ALL_STATUSES:
        continue
    # Check if this matches LT|LT
    if asia_status == "Long True" and london_status == "Long True":
        generator_matched.append(curr_date)

print(f"Generator simulation LT|LT count: {len(generator_matched)}")
print(f"Diff from lookup: {len(generator_matched) - lk_count}")

# Find dates in local but not in generator
local_set = set(matched)
gen_set = set(generator_matched)
only_local = local_set - gen_set
only_gen = gen_set - local_set
print(f"\nDates only in local: {sorted(only_local)[:10]}")
print(f"Dates only in generator: {sorted(only_gen)[:10]}")

# Check what the lookup table generator ACTUALLY does
# It uses _build_key which includes broken status
# LT|LT is a status-only key, which is aggregated from full keys
# The full key would be LT|F|LT|F, LT|F|LT|T, LT|T|LT|F, LT|T|LT|T
# Let's check if the status-only aggregation loses dates
print("\n--- Checking full keys for LT|LT ---")
for bk_asia in ["F", "T"]:
    for bk_lon in ["F", "T"]:
        full_key = f"LT|{bk_asia}|LT|{bk_lon}"
        entry = lookup["tables"]["NY1"].get(full_key, {})
        full_count = entry.get("samples", 0)
        # Count locally
        local_full = []
        for date in dates:
            sess_map = by_date[date]
            asia = sess_map.get("Asia", {})
            london = sess_map.get("London", {})
            if (asia.get("status") == "Long True" and
                london.get("status") == "Long True" and
                bool(asia.get("broken", False)) == (bk_asia == "T") and
                bool(london.get("broken", False)) == (bk_lon == "T")):
                local_full.append(date)
        diff = len(local_full) - full_count if full_count else len(local_full)
        print(f"  {full_key}: lookup={full_count}, local={len(local_full)}, diff={diff}")