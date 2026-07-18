"""Verify level hit timing: lookup table vs WebUI for Long False."""
import json
from pathlib import Path

d = json.load(open(Path(__file__).parent / "data" / "derived" / "NQ1_profiler_lookup.json"))
t = d["tables"]["NY1"]["LF|LF"]
olh = t.get("per_outcome_level_hits", {})
lf = olh.get("LF", {})

webui = {
    "pdl": {"hit_rate": 51.1, "mode_time": "08:00", "median_time": "10:00"},
    "pdm": {"hit_rate": 68.9, "mode_time": "09:30", "median_time": "10:00"},
    "pdh": {"hit_rate": 28.9, "mode_time": "09:30", "median_time": "09:30"},
    "p12h": {"hit_rate": 71.1, "mode_time": "09:30", "median_time": "09:30"},
    "p12m": {"hit_rate": 88.9, "mode_time": "08:00", "median_time": "08:30"},
    "p12l": {"hit_rate": 86.7, "mode_time": "08:00", "median_time": "09:30"},
    "midnight_open": {"hit_rate": 82.2, "mode_time": "08:00", "median_time": "08:45"},
    "open_0730": {"hit_rate": 82.2, "mode_time": "08:00", "median_time": "08:45"},
    "asia_mid": {"hit_rate": 80.0, "mode_time": "08:00", "median_time": "09:00"},
    "london_mid": {"hit_rate": 93.3, "mode_time": "08:15", "median_time": "08:45"},
    "prev_ny1_mid": {"hit_rate": 42.2, "mode_time": "09:30", "median_time": "10:00"},
    "prev_ny2_mid": {"hit_rate": 64.4, "mode_time": "08:00", "median_time": "09:30"},
}

print(f"{'Level':<20} {'Field':<12} {'Lookup':>10} {'WebUI':>10} {'Match':>8}")
print("-" * 62)
all_match = True
for level, wv in webui.items():
    lv = lf.get(level, {})
    for field in ["hit_rate", "mode_time", "median_time"]:
        l_val = lv.get(field)
        w_val = wv.get(field)
        match = "YES" if str(l_val) == str(w_val) else "NO"
        if match == "NO":
            all_match = False
        print(f"{level:<20} {field:<12} {str(l_val):>10} {str(w_val):>10} {match:>8}")
print(f"\nAll match: {'YES' if all_match else 'NO'}")