"""Check low pcts for LF|LF → NY1 Long True."""
import json, sys, math
sys.path.insert(0, r'C:\Users\vinay\tvDownloadOHLC')

from scripts.testing.features.profiler.data import load_profiler, load_hod_lod_unadjusted
from scripts.testing.core.filter_engine import FilterEngine

sessions = load_profiler('NQ1')
hod_lod = load_hod_lod_unadjusted('NQ1')

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

l_pcts = []
for d in lt_dates:
    if d in hod_lod:
        e = hod_lod[d]
        opn = e.get("daily_open", 0)
        lp = e.get("lod_price", 0)
        if opn and lp:
            l_pct = round((lp / opn - 1) * 100, 2)
            l_pcts.append(l_pct)

print(f"Low pcts: {sorted(l_pcts)}")
print(f"Sorted: {sorted(l_pcts)}")
print(f"Median value: {sorted(l_pcts)[len(l_pcts)//2]}")
print(f"Median bin (floor to 0.1): {round(math.floor(sorted(l_pcts)[len(l_pcts)//2] / 0.1) * 0.1, 1)}")

# WebUI uses unadjusted prices from the API, let me check those
import urllib.request
with urllib.request.urlopen('http://127.0.0.1:8000/stats/daily-hod-lod/NQ1?unadjusted=true', timeout=30) as resp:
    unadj = json.loads(resp.read().decode())

l_pcts_webui = []
for d in lt_dates:
    if d in unadj["dates"]:
        idx = unadj["dates"].index(d)
        if idx < len(unadj["lod_price"]) and idx < len(unadj["daily_open"]) and unadj["daily_open"][idx] > 0:
            l_pcts_webui.append(round((unadj["lod_price"][idx] - unadj["daily_open"][idx]) / unadj["daily_open"][idx] * 100, 2))

print(f"\nWebUI unadjusted low pcts: {sorted(l_pcts_webui)}")
print(f"WebUI median value: {sorted(l_pcts_webui)[len(l_pcts_webui)//2]}")
print(f"WebUI median bin: {round(math.floor(sorted(l_pcts_webui)[len(l_pcts_webui)//2] / 0.1) * 0.1, 1)}")