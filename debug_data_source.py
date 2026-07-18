"""Check all data sources for 2020-04-09."""
import json
import urllib.request
from pathlib import Path

_DATA = Path(__file__).parent / "data"

# Check API
for unadj in [True, False]:
    url = f"http://127.0.0.1:8000/stats/daily-hod-lod/NQ1?unadjusted={str(unadj).lower()}"
    data = json.loads(urllib.request.urlopen(url, timeout=30).read())
    dates = data.get("dates", [])
    idx = dates.index("2020-04-09") if "2020-04-09" in dates else -1
    if idx >= 0:
        o = data["daily_open"][idx]
        h = data["daily_high"][idx]
        l = data["daily_low"][idx]
        h_pct = ((h / o - 1) * 100)
        l_pct = ((l / o - 1) * 100)
        print(f"API unadjusted={unadj}: open={o}, high={h}, low={l}, h_pct={h_pct:.4f}, l_pct={l_pct:.4f}")

# Check local JSON files
for fname in ["NQ1_daily_hod_lod_unadjusted.json", "NQ1_daily_hod_lod.json"]:
    local = json.load(open(_DATA / fname))
    rec = local.get("2020-04-09", {})
    o = rec.get("daily_open")
    h = rec.get("daily_high")
    l = rec.get("daily_low")
    h_pct = ((h / o - 1) * 100) if o and o > 0 else 0
    l_pct = ((l / o - 1) * 100) if o and o > 0 else 0
    print(f"Local {fname}: open={o}, high={h}, low={l}, h_pct={h_pct:.4f}, l_pct={l_pct:.4f}")

# The WebUI component shows open=3459.75 for this date
# Check if this matches any profiler session's open
sessions = json.load(open(_DATA / "NQ1_profiler.json"))
if isinstance(sessions, dict):
    sessions = sessions.get("sessions", [])
for s in sessions:
    if s.get("date") == "2020-04-09":
        if abs(s.get("open", 0) - 3459.75) < 1:
            print(f"\nProfiler session match: date={s['date']}, session={s['session']}, open={s.get('open')}, high_pct={s.get('high_pct')}, low_pct={s.get('low_pct')}")
            print(f"  range_high={s.get('range_high')}, range_low={s.get('range_low')}")