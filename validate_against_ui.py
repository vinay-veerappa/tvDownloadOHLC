"""Fetch WebUI API values for 3 filters and compare with validator's local computation."""
import json
import urllib.request
from collections import defaultdict
from pathlib import Path

_DATA = Path(__file__).parent / "data"
API = "http://127.0.0.1:8000"

# Load sessions
sessions = json.load(open(_DATA / "NQ1_profiler.json"))
if isinstance(sessions, dict):
    sessions = sessions.get("sessions", [])
by_date = defaultdict(dict)
for s in sessions:
    by_date[s["date"]][s["session"]] = s

# Load columnar level touches
lt = json.load(open(_DATA / "NQ1_level_touches_columnar.json"))
date_indices = {d: i for i, d in enumerate(lt["dates"])}

FILTERS = [
    ("LF|LF", {"Asia": "Long False", "London": "Long False"}),
    ("LT|ST", {"Asia": "Long True", "London": "Short True"}),
    ("SF|ST", {"Asia": "Short False", "London": "Short True"}),
]

def api_post(path, payload):
    req = urllib.request.Request(
        f"{API}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))

def compute_local_hits(dates, target_session):
    """Compute per-outcome level hits locally from columnar data."""
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

for filter_key, filters in FILTERS:
    print(f"\n{'='*70}")
    print(f"FILTER: {filter_key} (Asia={filters['Asia']}, London={filters['London']})")
    print(f"{'='*70}")

    # 1. Call WebUI API
    api_result = api_post("/stats/filtered-stats", {
        "ticker": "NQ1",
        "target_session": "NY1",
        "filters": filters,
        "broken_filters": {},
        "intra_state": "Any",
    })

    # 2. Local computation
    matched = []
    for date in sorted(by_date.keys()):
        sm = by_date[date]
        asia = sm.get("Asia", {})
        london = sm.get("London", {})
        ny1 = sm.get("NY1", {})
        # Context filter
        if asia.get("status") != filters["Asia"] or london.get("status") != filters["London"]:
            continue
        # Target session must exist (not missing)
        if not ny1.get("status", ""):
            continue
        matched.append(date)

    # Group by outcome
    outcome_dates = defaultdict(list)
    for d in matched:
        ny1 = by_date[d].get("NY1", {})
        status = ny1.get("status", "None")
        outcome_dates[status].append(d)

    # 3. Compare counts
    api_count = api_result.get("count", 0)
    local_count = len(matched)
    count_match = "✅" if api_count == local_count else "❌"
    print(f"\n  Count: API={api_count}, Local={local_count} {count_match}")

    # 4. Compare distribution
    api_dist = api_result.get("distribution", {})
    print(f"\n  Distribution:")
    print(f"    {'Outcome':<15} {'API':>8} {'Local':>8} {'Match':>8}")
    print(f"    {'-'*45}")
    dist_ok = True
    for status in ["Long True", "Long False", "Short True", "Short False", "None"]:
        api_val = api_dist.get(status, 0)
        local_val = len(outcome_dates.get(status, []))
        match = "✅" if api_val == local_val else "❌"
        if match == "❌":
            dist_ok = False
        print(f"    {status:<15} {api_val:>8} {local_val:>8} {match:>8}")
    print(f"  Distribution: {'✅ ALL MATCH' if dist_ok else '❌ MISMATCH'}")

    # 5. Compare per-outcome level hits for Long True
    for outcome in ["Long True", "Short True"]:
        o_dates = outcome_dates.get(outcome, [])
        if not o_dates:
            continue
        local_hits = compute_local_hits(o_dates, "NY1")
        print(f"\n  Per-Outcome Level Hits: {outcome} ({len(o_dates)} days, target=NY1)")
        print(f"    {'Level':<20} {'Local (%)':>12}")
        print(f"    {'-'*35}")
        for level in ["pdh", "pdm", "pdl", "ny_p12h", "ny_p12m", "ny_p12l",
                       "daily_open", "prev_asia_mid", "prev_london_mid",
                       "prev_ny1_mid", "prev_ny2_mid"]:
            val = local_hits.get(level, 0)
            print(f"    {level:<20} {val:>12}")

    # 6. Compare lookup table
    lookup = json.load(open(_DATA / "derived" / "NQ1_profiler_lookup.json"))
    lk_entry = lookup["tables"]["NY1"].get(filter_key, {})
    lk_count = lk_entry.get("samples", 0)
    lk_match = "✅" if lk_count == local_count else "❌"
    print(f"\n  Lookup table count: {lk_count}, Local: {local_count} {lk_match}")

    # Compare lookup per-outcome level hits with local
    lk_per_outcome = lk_entry.get("per_outcome_level_hits", {})
    for outcome in ["LT", "ST"]:
        full = {"LT": "Long True", "ST": "Short True"}.get(outcome, "")
        o_dates = outcome_dates.get(full, [])
        if not o_dates or outcome not in lk_per_outcome:
            continue
        local_hits = compute_local_hits(o_dates, "NY1")
        lk_hits = lk_per_outcome.get(outcome, {})
        print(f"\n  Lookup vs Local Per-Outcome Level Hits: {full} ({len(o_dates)} days)")
        print(f"    {'Level':<20} {'Local':>8} {'Lookup':>8} {'Match':>8}")
        print(f"    {'-'*48}")
        all_match = True
        for level in ["pdh", "pdm", "pdl", "ny_p12h", "ny_p12m", "ny_p12l",
                       "daily_open", "prev_asia_mid", "prev_london_mid",
                       "prev_ny1_mid", "prev_ny2_mid"]:
            lv = local_hits.get(level, 0)
            wv = lk_hits.get(level, 0)
            match = "✅" if abs(lv - wv) < 0.1 else "❌"
            if match == "❌":
                all_match = False
            print(f"    {level:<20} {lv:>8} {wv:>8} {match:>8}")
        print(f"  {'✅ ALL MATCH' if all_match else '❌ MISMATCH'}")