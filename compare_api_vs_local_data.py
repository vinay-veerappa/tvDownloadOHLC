"""Compare API daily-hod-lod values with local JSON for Long True dates."""
import json
import urllib.request
from pathlib import Path

_DATA = Path(__file__).parent / "data"

# Get API daily-hod-lod for NQ1 (unadjusted)
url = "http://127.0.0.1:8000/stats/daily-hod-lod/NQ1?unadjusted=true"
data = json.loads(urllib.request.urlopen(url, timeout=30).read())
api_dates = data.get("dates", [])
api_open = data.get("daily_open", [])
api_high = data.get("daily_high", [])
api_low = data.get("daily_low", [])

# Local file
local = json.load(open(_DATA / "NQ1_daily_hod_lod_unadjusted.json"))

# Long True dates for LF|LF
lt_dates = [
    "2006-07-04", "2007-04-17", "2007-08-15", "2007-09-12", "2008-09-03",
    "2008-12-12", "2008-12-23", "2009-02-02", "2009-10-09", "2009-11-10",
    "2009-11-12", "2011-06-06", "2011-06-28", "2012-04-03", "2013-02-01",
    "2014-02-04", "2014-02-20", "2015-01-19", "2015-05-07", "2015-10-29",
    "2016-07-08", "2019-03-11", "2019-05-30", "2020-03-31", "2020-04-09",
    "2020-08-06", "2020-09-25", "2020-09-30", "2021-01-14", "2021-07-29",
    "2022-06-15", "2022-09-28", "2023-10-10", "2025-02-05", "2025-07-03",
]

print(f"{'Date':<12} {'API Open':>12} {'API High':>12} {'API Low':>12} {'Loc Open':>12} {'Loc High':>12} {'Loc Low':>12} {'Match':>8}")
print("-" * 95)

all_match = True
for d in lt_dates[:15]:
    idx = api_dates.index(d) if d in api_dates else -1
    api_o = api_open[idx] if idx >= 0 else None
    api_h = api_high[idx] if idx >= 0 else None
    api_l = api_low[idx] if idx >= 0 else None
    loc = local.get(d, {})
    loc_o = loc.get("daily_open")
    loc_h = loc.get("daily_high")
    loc_l = loc.get("daily_low")

    match = "✅" if (api_o == loc_o and api_h == loc_h and api_l == loc_l) else "❌"
    if match == "❌":
        all_match = False

    print(f"{d:<12} {str(api_o):>12} {str(api_h):>12} {str(api_l):>12} {str(loc_o):>12} {str(loc_h):>12} {str(loc_l):>12} {match:>8}")

# Also check a few that have big discrepancies
print("\n--- Big discrepancy dates ---")
for d in ["2008-12-12", "2022-06-15", "2008-09-03"]:
    idx = api_dates.index(d) if d in api_dates else -1
    api_o = api_open[idx] if idx >= 0 else None
    api_h = api_high[idx] if idx >= 0 else None
    api_l = api_low[idx] if idx >= 0 else None
    loc = local.get(d, {})
    loc_o = loc.get("daily_open")
    loc_h = loc.get("daily_high")
    loc_l = loc.get("daily_low")
    print(f"\n  {d}:")
    print(f"    API:  open={api_o}, high={api_h}, low={api_l}")
    print(f"    Local: open={loc_o}, high={loc_h}, low={loc_l}")
    if api_o and loc_o and api_o > 0 and loc_o > 0:
        api_h_pct = ((api_h / api_o - 1) * 100) if api_h else None
        api_l_pct = ((api_l / api_o - 1) * 100) if api_l else None
        loc_h_pct = ((loc_h / loc_o - 1) * 100) if loc_h else None
        loc_l_pct = ((loc_l / loc_o - 1) * 100) if loc_l else None
        print(f"    API h_pct={api_h_pct:.4f}, l_pct={api_l_pct:.4f}")
        print(f"    Local h_pct={loc_h_pct:.4f}, l_pct={loc_l_pct:.4f}")

# Also compare the adjusted data
print("\n--- Checking adjusted data ---")
url2 = "http://127.0.0.1:8000/stats/daily-hod-lod/NQ1?unadjusted=false"
data2 = json.loads(urllib.request.urlopen(url2, timeout=30).read())
api_dates2 = data2.get("dates", [])
api_open2 = data2.get("daily_open", [])
api_high2 = data2.get("daily_high", [])
api_low2 = data2.get("daily_low", [])

local_adj = json.load(open(_DATA / "NQ1_daily_hod_lod.json"))

for d in ["2008-12-12", "2022-06-15"]:
    idx = api_dates2.index(d) if d in api_dates2 else -1
    api_o = api_open2[idx] if idx >= 0 else None
    api_h = api_high2[idx] if idx >= 0 else None
    api_l = api_low2[idx] if idx >= 0 else None
    loc = local_adj.get(d, {})
    loc_o = loc.get("daily_open")
    loc_h = loc.get("daily_high")
    loc_l = loc.get("daily_low")
    print(f"\n  {d} (adjusted):")
    print(f"    API:  open={api_o}, high={api_h}, low={api_l}")
    print(f"    Local: open={loc_o}, high={loc_h}, low={loc_l}")