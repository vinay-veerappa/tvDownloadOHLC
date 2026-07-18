"""Verify Long False per-outcome level hit rates: WebUI vs Local vs Lookup."""
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

lt = json.load(open(_DATA / "NQ1_level_touches_columnar.json"))
date_indices = {d: i for i, d in enumerate(lt["dates"])}
lookup = json.load(open(_DATA / "derived" / "NQ1_profiler_lookup.json"))

# Apply filter: Asia=LF, London=LF -> NY1 Long False
matched = []
for date in sorted(by_date.keys()):
    sm = by_date[date]
    if sm.get("Asia", {}).get("status") != "Long False":
        continue
    if sm.get("London", {}).get("status") != "Long False":
        continue
    if not sm.get("NY1", {}).get("status", ""):
        continue
    if sm["NY1"]["status"] == "Long False":
        matched.append(date)

print(f"Long False dates: {len(matched)}")

def compute_hits(dates, target_session):
    result = {}
    for level_key, level_data in lt["levels"].items():
        session_hits = level_data.get("hits", {}).get(target_session, [])
        if not session_hits:
            continue
        touched = 0
        counted = 0
        for d in dates:
            idx = date_indices.get(d)
            if idx is None or idx >= len(session_hits):
                continue
            counted += 1
            if session_hits[idx] != -1:
                touched += 1
        if counted > 0:
            result[level_key] = round(touched / counted * 100, 1)
    return result

local_hits = compute_hits(matched, "NY1")
lk_hits = lookup["tables"]["NY1"]["LF|LF"].get("per_outcome_level_hits", {}).get("LF", {})

# WebUI values (from browser)
webui = {
    "pdl": 51.1, "pdm": 68.9, "pdh": 28.9,
    "p12h": 71.1, "p12m": 88.9, "p12l": 86.7,
    "midnight_open": 82.2, "open_0730": 82.2,
    "asia_mid": 80.0, "london_mid": 93.3,
    "prev_ny1_mid": 42.2, "prev_ny2_mid": 64.4,
}

print(f"\n{'Level':<20} {'WebUI':>8} {'Local':>8} {'Lookup':>8} {'Match':>12}")
print("-" * 60)
all_match = True
for level in ["pdh", "pdm", "pdl", "p12h", "p12m", "p12l",
              "midnight_open", "open_0730",
              "asia_mid", "london_mid", "prev_ny1_mid", "prev_ny2_mid"]:
    wv = webui.get(level)
    lv = local_hits.get(level)
    lkv = lk_hits.get(level)
    if wv is not None and lv is not None and lkv is not None:
        w_ok = abs(wv - lv) < 0.1
        l_ok = abs(lv - lkv) < 0.1
        match = "ALL MATCH" if (w_ok and l_ok) else f"W:{'Y' if w_ok else 'N'} L:{'Y' if l_ok else 'N'}"
        if not (w_ok and l_ok):
            all_match = False
        print(f"{level:<20} {wv:>8.1f} {lv:>8.1f} {lkv:>8.1f} {match:>12}")
    else:
        print(f"{level:<20} {str(wv):>8} {str(lv):>8} {str(lkv):>8}")

print(f"\nAll match: {'YES' if all_match else 'NO'}")