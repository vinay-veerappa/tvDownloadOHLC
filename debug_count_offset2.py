"""Debug the remaining count off-by-1 for LF|LT filter."""
import json
from collections import defaultdict
from pathlib import Path

_DATA = Path(__file__).parent / "data"

sessions = json.load(open(_DATA / "NQ1_profiler.json"))
if isinstance(sessions, dict):
    sessions = sessions.get("sessions", [])

by_date = defaultdict(dict)
for s in sessions:
    by_date[s["date"]][s["session"]] = s
dates = sorted(by_date.keys())

lookup = json.load(open(_DATA / "derived" / "NQ1_profiler_lookup.json"))
lk_count = lookup["tables"]["NY1"]["LF|LT"]["samples"]
print(f"Lookup LF|LT count: {lk_count}")

# Local filter: Asia=Long False, London=Long True
matched_local = []
for date in dates:
    sm = by_date[date]
    asia = sm.get("Asia", {})
    london = sm.get("London", {})
    if asia.get("status") == "Long False" and london.get("status") == "Long True":
        matched_local.append(date)

print(f"Local LF|LT count: {len(matched_local)}")

# Generator simulation: context must be valid (not None), target can be None
ALL_STATUSES = ["Long True", "Long False", "Short True", "Short False"]
matched_gen = []
for date in dates:
    sm = by_date[date]
    asia = sm.get("Asia", {})
    london = sm.get("London", {})
    asia_status = asia.get("status", "")
    london_status = london.get("status", "")
    # Context must be valid
    if asia_status not in ALL_STATUSES or london_status not in ALL_STATUSES:
        continue
    # Target NY1 can be any status (including None)
    ny1 = sm.get("NY1", {})
    if not ny1.get("status", ""):
        continue
    if asia_status == "Long False" and london_status == "Long True":
        matched_gen.append(date)

print(f"Generator LF|LT count: {len(matched_gen)}")

# Find the extra date(s)
local_set = set(matched_local)
gen_set = set(matched_gen)
only_local = local_set - gen_set
print(f"\nDates only in local: {sorted(only_local)}")

for d in sorted(only_local):
    sm = by_date[d]
    print(f"\n  Date: {d}")
    for sn in ["Asia", "London", "NY1", "NY2"]:
        s = sm.get(sn, {})
        print(f"    {sn}: status={s.get('status', 'MISSING')!r} broken={s.get('broken', 'MISSING')!r}")