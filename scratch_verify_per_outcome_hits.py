"""Quick verification: compute per-outcome level hits for LF|LF -> NY1
and compare against WebUI values extracted from the browser."""
import json
from pathlib import Path

_DATA = Path(__file__).parent / "data"

# Load profiler sessions
with open(_DATA / "NQ1_profiler.json") as f:
    sessions = json.load(f)
if isinstance(sessions, dict):
    sessions = sessions.get("sessions", [])

# Load columnar level touches
with open(_DATA / "NQ1_level_touches_columnar.json") as f:
    lt = json.load(f)

# Build date -> index map
date_indices = {d: i for i, d in enumerate(lt["dates"])}

# Filter: Asia=Long False, London=Long False -> NY1 target
# Context chain for NY1: Asia (curr), London (curr)
# Build date -> session status map
from collections import defaultdict

sessions_by_date = defaultdict(dict)
for s in sessions:
    sessions_by_date[s["date"]][s["session"]] = s

# Apply filter: Asia=LF, London=LF
matched_dates = []
for date, sess_map in sessions_by_date.items():
    asia = sess_map.get("Asia")
    london = sess_map.get("London")
    ny1 = sess_map.get("NY1")
    if not asia or not london or not ny1:
        continue
    if asia.get("status") == "Long False" and london.get("status") == "Long False":
        matched_dates.append(date)

print(f"Total matched dates (LF|LF): {len(matched_dates)}")

# Group by NY1 outcome
outcome_dates = defaultdict(list)
for d in matched_dates:
    ny1 = sessions_by_date[d].get("NY1", {})
    status = ny1.get("status", "None")
    outcome_dates[status].append(d)

# WebUI values for Long True (35 days), target session = NY1
webui_lt_ny1 = {
    "pdl": 28.6,
    "pdm": 48.6,
    "pdh": 60.0,
    "ny_p12h": 62.9,
    "ny_p12m": 57.1,
    "ny_p12l": 31.4,
    "daily_open": 82.9,
    "prev_asia_mid": 31.4,
    "prev_london_mid": 31.4,
    "prev_ny1_mid": 28.6,
    "prev_ny2_mid": 54.3,
}

# WebUI values for Long True (35 days), target session = Daily
webui_lt_daily = {
    "pdl": 34.3,
    "pdm": 57.1,
    "pdh": 62.9,
    "ny_p12h": 65.7,
    "ny_p12m": 62.9,
    "ny_p12l": 34.3,
    "daily_open": 100.0,
    "prev_asia_mid": 34.3,
    "prev_london_mid": 37.1,
    "prev_ny1_mid": 31.4,
    "prev_ny2_mid": 62.9,
}


def compute_hit_rate(level_key, dates, target_session):
    """Compute hit rate for a level on a set of dates for a target session."""
    level_data = lt["levels"].get(level_key)
    if not level_data:
        return 0.0
    session_hits = level_data.get("hits", {}).get(target_session, [])
    if not session_hits:
        return 0.0
    touched = 0
    counted = 0
    for d in dates:
        idx = date_indices.get(d)
        if idx is None:
            continue
        counted += 1
        if idx < len(session_hits) and session_hits[idx] != -1:
            touched += 1
    return round(touched / counted * 100, 1) if counted else 0.0


# Compare for Long True outcome
lt_dates = outcome_dates.get("Long True", [])
print(f"\nLong True dates: {len(lt_dates)}")

print("\n=== Per-Outcome Level Hits: Long True (target=NY1) ===")
print(f"{'Level':<20} {'Local (%)':<12} {'WebUI (%)':<12} {'Match':<8}")
print("-" * 52)
all_match = True
for level, webui_val in webui_lt_ny1.items():
    local_val = compute_hit_rate(level, lt_dates, "NY1")
    match = "✅" if abs(local_val - webui_val) < 0.1 else "❌"
    if match == "❌":
        all_match = False
    print(f"{level:<20} {local_val:<12} {webui_val:<12} {match}")

print(f"\nAll match (NY1): {'✅' if all_match else '❌'}")

print("\n=== Per-Outcome Level Hits: Long True (target=Daily) ===")
print(f"{'Level':<20} {'Local (%)':<12} {'WebUI (%)':<12} {'Match':<8}")
print("-" * 52)
all_match_daily = True
for level, webui_val in webui_lt_daily.items():
    local_val = compute_hit_rate(level, lt_dates, "Daily")
    match = "✅" if abs(local_val - webui_val) < 0.1 else "❌"
    if match == "❌":
        all_match_daily = False
    print(f"{level:<20} {local_val:<12} {webui_val:<12} {match}")

print(f"\nAll match (Daily): {'✅' if all_match_daily else '❌'}")

# Also show all outcomes for reference
print("\n=== All Outcomes Level Hits (target=NY1) ===")
for outcome in ["Long True", "Long False", "Short True", "Short False"]:
    dates = outcome_dates.get(outcome, [])
    if not dates:
        continue
    print(f"\n{outcome} ({len(dates)} days):")
    for level in ["pdh", "pdm", "pdl", "ny_p12h", "ny_p12m", "ny_p12l",
                   "daily_open", "prev_asia_mid", "prev_london_mid",
                   "prev_ny1_mid", "prev_ny2_mid"]:
        val = compute_hit_rate(level, dates, "NY1")
        print(f"  {level:<20} {val}%")