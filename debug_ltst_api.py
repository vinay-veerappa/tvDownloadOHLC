"""Debug the LT|ST count discrepancy: API=508, Local=507."""
import json
import urllib.request
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

# API call for LT|ST
req = urllib.request.Request(
    "http://127.0.0.1:8000/stats/filtered-stats",
    data=json.dumps({
        "ticker": "NQ1",
        "target_session": "NY1",
        "filters": {"Asia": "Long True", "London": "Short True"},
        "broken_filters": {},
        "intra_state": "Any",
    }).encode("utf-8"),
    headers={"Content-Type": "application/json"},
)
api_result = json.loads(urllib.request.urlopen(req, timeout=30).read())
api_count = api_result.get("count", 0)
api_dates = set(api_result.get("filtered_dates", []))
print(f"API count: {api_count}")
print(f"API filtered_dates count: {len(api_dates)}")

# Local
matched = []
for date in dates:
    sm = by_date[date]
    asia = sm.get("Asia", {})
    london = sm.get("London", {})
    ny1 = sm.get("NY1", {})
    if asia.get("status") != "Long True" or london.get("status") != "Short True":
        continue
    if not ny1.get("status", ""):
        continue
    matched.append(date)
print(f"Local count: {len(matched)}")

# Find the extra date in API
local_set = set(matched)
api_extra = api_dates - local_set
local_extra = local_set - api_dates
print(f"API extra dates (in API not local): {sorted(api_extra)}")
print(f"Local extra dates (in local not API): {sorted(local_extra)}")

for d in sorted(api_extra):
    sm = by_date[d]
    asia_s = sm.get("Asia", {}).get("status", "MISSING")
    london_s = sm.get("London", {}).get("status", "MISSING")
    ny1_s = sm.get("NY1", {}).get("status", "MISSING")
    print(f"  {d}: Asia={asia_s!r}, London={london_s!r}, NY1={ny1_s!r}")

# Also check: does the API include the date in the distribution?
api_dist = api_result.get("distribution", {})
print(f"\nAPI distribution: {api_dist}")
print(f"API distribution total: {sum(api_dist.values())}")