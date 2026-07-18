"""Compare price distribution (mode/median) between WebUI and local computation
for LF|LF -> Long True outcome (35 days)."""
import json
import math
from collections import defaultdict
from pathlib import Path

_DATA = Path(__file__).parent / "data"

# Load sessions
sessions = json.load(open(_DATA / "NQ1_profiler.json"))
if isinstance(sessions, dict):
    sessions = sessions.get("sessions", [])
by_date = defaultdict(dict)
for s in sessions:
    by_date[s["date"]][s["session"]] = s

# Load unadjusted daily HOD/LOD (matches WebUI frontend)
daily_hl = json.load(open(_DATA / "NQ1_daily_hod_lod_unadjusted.json"))

# Load lookup table
lookup = json.load(open(_DATA / "derived" / "NQ1_profiler_lookup.json"))

# Apply filter: Asia=Long False, London=Long False -> NY1 Long True
matched = []
for date in sorted(by_date.keys()):
    sm = by_date[date]
    asia = sm.get("Asia", {})
    london = sm.get("London", {})
    ny1 = sm.get("NY1", {})
    if asia.get("status") != "Long False" or london.get("status") != "Long False":
        continue
    if not ny1.get("status", ""):
        continue
    matched.append(date)

# Group by outcome
outcome_dates = defaultdict(list)
for d in matched:
    ny1 = by_date[d].get("NY1", {})
    outcome_dates[ny1.get("status", "None")].append(d)

print(f"Total matched: {len(matched)}")
for outcome, dates in sorted(outcome_dates.items()):
    print(f"  {outcome}: {len(dates)} days")

# WebUI values for Long True (from browser extraction)
webui_lt = {
    "high_mode": "0.5 to 0.6 %",
    "high_median": "0.7 to 0.8 %",
    "low_mode": "-0.3 to -0.2 %",
    "low_median": "-0.8 to -0.7 %",
}

def mode_bucket(values, bucket_size=0.1):
    """Mode bin: floor to bin start, tie-break first alphabetically."""
    if not values:
        return None
    buckets = defaultdict(int)
    for v in values:
        bin_start = math.floor(v / bucket_size) * bucket_size
        buckets[round(bin_start, 1)] += 1
    if not buckets:
        return None
    max_count = max(buckets.values())
    candidates = sorted([k for k, v in buckets.items() if v == max_count])
    return candidates[0]

def median_bin(values, bucket_size=0.1):
    """Median bin: sorted[len//2], floor to bin start."""
    if not values:
        return None
    sorted_vals = sorted(values)
    mid_idx = len(sorted_vals) // 2
    median_val = sorted_vals[mid_idx]
    bin_start = math.floor(median_val / bucket_size) * bucket_size
    return round(bin_start, 1)

def span_str(bin_val):
    """Convert bin to span string like '0.5 to 0.6 %'."""
    return f"{bin_val:.1f} to {bin_val + 0.1:.1f} %"

# Compute for ALL outcomes
print("\n" + "=" * 80)
print("PRICE DISTRIBUTION COMPARISON: WebUI vs Local vs Lookup Table")
print("=" * 80)

for outcome in ["Long True", "Long False", "Short True", "Short False"]:
    dates = outcome_dates.get(outcome, [])
    if not dates:
        continue

    # Compute high_pct and low_pct using unadjusted daily data (matches WebUI)
    h_pcts = []
    l_pcts = []
    for d in dates:
        day_hl = daily_hl.get(d, {})
        daily_open = day_hl.get("daily_open")
        daily_high = day_hl.get("daily_high")
        daily_low = day_hl.get("daily_low")
        if daily_open and daily_open > 0:
            h_pct = ((daily_high / daily_open - 1) * 100) if daily_high is not None else None
            l_pct = ((daily_low / daily_open - 1) * 100) if daily_low is not None else None
            if h_pct is not None and l_pct is not None:
                h_pcts.append(h_pct)
                l_pcts.append(l_pct)

    h_mode = mode_bucket(h_pcts)
    h_med = median_bin(h_pcts)
    l_mode = mode_bucket(l_pcts)
    l_med = median_bin(l_pcts)

    # Lookup table values
    short = {"Long True": "LT", "Long False": "LF", "Short True": "ST", "Short False": "SF"}[outcome]
    lk_ps = lookup["tables"]["NY1"]["LF|LF"].get("price_stats", {}).get(short, {})

    print(f"\n--- {outcome} ({len(dates)} days, {len(h_pcts)} with price data) ---")
    print(f"{'Field':<15} {'WebUI':<20} {'Local':<20} {'Lookup':<20} {'Match':<10}")
    print(f"{'-'*85}")

    fields = [
        ("h_mode", webui_lt if outcome == "Long True" else None, h_mode, lk_ps.get("h_mode"), span_str),
        ("h_median", webui_lt if outcome == "Long True" else None, h_med, lk_ps.get("h_med"), span_str),
        ("l_mode", webui_lt if outcome == "Long True" else None, l_mode, lk_ps.get("l_mode"), span_str),
        ("l_median", webui_lt if outcome == "Long True" else None, l_med, lk_ps.get("l_med"), span_str),
    ]

    for field_name, webui_val, local_val, lookup_val, fmt in fields:
        webui_str = webui_val.get({
            "h_mode": "high_mode",
            "h_median": "high_median",
            "l_mode": "low_mode",
            "l_median": "low_median",
        }[field_name], "N/A") if webui_val else "N/A"
        local_str = fmt(local_val) if local_val is not None else "None"
        lookup_str = fmt(lookup_val) if lookup_val is not None else "None"

        # Check matches
        local_lookup_match = "✅" if local_str == lookup_str else "❌"
        if webui_str != "N/A":
            webui_local_match = "✅" if webui_str == local_str else "❌"
            match = f"W:{webui_local_match} L:{local_lookup_match}"
        else:
            match = f"L:{local_lookup_match}"

        print(f"{field_name:<15} {webui_str:<20} {local_str:<20} {lookup_str:<20} {match:<10}")

    # Also show raw values for debugging
    if h_pcts:
        import numpy as np
        print(f"\n  Raw stats: h_mean={np.mean(h_pcts):.3f}, h_median_raw={np.median(h_pcts):.3f}, "
              f"l_mean={np.mean(l_pcts):.3f}, l_median_raw={np.median(l_pcts):.3f}")
        print(f"  Histograms:")
        h_buckets = defaultdict(int)
        for v in h_pcts:
            h_buckets[round(math.floor(v / 0.1) * 0.1, 1)] += 1
        l_buckets = defaultdict(int)
        for v in l_pcts:
            l_buckets[round(math.floor(v / 0.1) * 0.1, 1)] += 1
        print(f"    High buckets: {dict(sorted(h_buckets.items()))}")
        print(f"    Low buckets: {dict(sorted(l_buckets.items()))}")