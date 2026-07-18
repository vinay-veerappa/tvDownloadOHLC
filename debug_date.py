"""Debug the specific date 2018-12-05 that's in local but not generator."""
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

# Check 2018-12-05
d = "2018-12-05"
sess_map = by_date.get(d, {})
print(f"Date: {d}")
print(f"Sessions present: {sorted(sess_map.keys())}")
for sn in ["Asia", "London", "NY1", "NY2"]:
    s = sess_map.get(sn, {})
    print(f"  {sn}: status={s.get('status', 'MISSING')!r} broken={s.get('broken', 'MISSING')!r}")

# Check the previous date too
dates = sorted(by_date.keys())
idx = dates.index(d) if d in dates else -1
print(f"\nIndex in sorted dates: {idx}")
if idx > 0:
    prev_d = dates[idx - 1]
    print(f"Previous date: {prev_d}")
    prev_map = by_date.get(prev_d, {})
    for sn in ["Asia", "London", "NY1", "NY2"]:
        s = prev_map.get(sn, {})
        print(f"  {sn}: status={s.get('status', 'MISSING')!r} broken={s.get('broken', 'MISSING')!r}")

# Check: does this date have Asia=Long True and London=Long True?
asia = sess_map.get("Asia", {})
london = sess_map.get("London", {})
print(f"\nAsia status: {asia.get('status')!r}")
print(f"London status: {london.get('status')!r}")
print(f"Matches LT|LT: {asia.get('status') == 'Long True' and london.get('status') == 'Long True'}")

# Check: does the generator skip this date?
# The generator checks: if status not in ALL_STATUSES: valid = False
ALL_STATUSES = ["Long True", "Long False", "Short True", "Short False"]
ny1 = sess_map.get("NY1", {})
print(f"NY1 status: {ny1.get('status')!r}")
print(f"NY1 status in ALL_STATUSES: {ny1.get('status', '') in ALL_STATUSES}")

# Check the filter engine approach - it uses pandas pivot
# The pivot includes ALL dates that have ANY session data
# Let's check if this date appears in the pivot
print(f"\nDate in by_date: {d in by_date}")
print(f"Has Asia: {'Asia' in sess_map}")
print(f"Has London: {'London' in sess_map}")
print(f"Has NY1: {'NY1' in sess_map}")