"""Compare the WebUI's highPcts/lowPcts arrays with our local computation."""
import json
import math
from collections import defaultdict
from pathlib import Path
import numpy as np

_DATA = Path(__file__).parent / "data"

# WebUI's actual highPcts and lowPcts arrays (extracted from browser)
webui_highPcts = [1.1827809104662412,8.119588302564939,0,4.702380952380958,2.9522828698935744,0.5486284289276888,3.9317123642007346,3.571428571428581,2.0786262991414395,2.3454157782516027,1.4184397163120588,0.8668730650154721,1.3234344738541015,0,0.7616629641383765,0.06405329233922785,0.17473789316027055,0.5722278738555353,4.1446208112874805,0.5698005698005604,0.7835051546391858,0.42028579434014723,0.4480614484272172,0.5634807417974397,1.4451911265264794,0.9778403095321853,0.23699802501646605,0.3512027035981635,0.2415608547537973,0.5977893074667229,1.112576704708368,1.1200818740050078,0.3544154255094689,0.532068915592876,0.8691156990081161]
webui_lowPcts = [-1.911704029707051,-1.2743015847083816,-6.219277623423814,-1.6071428571428625,-0.4806041881222134,-3.7406483790523692,-1.8623900672529725,-0.6036217303822977,-0.2711251694532346,-0.17057569296374808,-1.5435961618689986,-0.2476780185758476,-0.06455777921239303,-2.2397476340694,-0.17454776261504046,-2.3571611580835206,-1.085871193210186,-0.6866734486266513,-3.4391534391534417,-1.675884028825203,-0.46735395189003714,-2.9046418231063797,-0.3749085588880763,0,-1.2862201026085707,-0.22511431586352826,-1.2113232389730055,-0.25843217811940544,-1.7528646639826562,-0.7782540040604524,-0.4301198600676681,-0.24448487605185365,-0.16033078773047826,-0.926596206746777,-0.7172627701851342]

# Load sessions
sessions = json.load(open(_DATA / "NQ1_profiler.json"))
if isinstance(sessions, dict):
    sessions = sessions.get("sessions", [])
by_date = defaultdict(dict)
for s in sessions:
    by_date[s["date"]][s["session"]] = s

# Load unadjusted daily HOD/LOD
daily_hl = json.load(open(_DATA / "NQ1_daily_hod_lod_unadjusted.json"))

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
    if ny1.get("status") == "Long True":
        matched.append(date)

print(f"Long True dates: {len(matched)}")
print(f"WebUI highPcts count: {len(webui_highPcts)}")
print(f"WebUI lowPcts count: {len(webui_lowPcts)}")

# Compute local highPcts/lowPcts
local_h = []
local_l = []
for d in matched:
    day_hl = daily_hl.get(d, {})
    daily_open = day_hl.get("daily_open")
    daily_high = day_hl.get("daily_high")
    daily_low = day_hl.get("daily_low")
    if daily_open and daily_open > 0:
        h = ((daily_high / daily_open - 1) * 100) if daily_high is not None else None
        l = ((daily_low / daily_open - 1) * 100) if daily_low is not None else None
        if h is not None and l is not None:
            local_h.append(h)
            local_l.append(l)
            print(f"  {d}: open={daily_open}, high={daily_high}, low={daily_low}, h_pct={h:.4f}, l_pct={l:.4f}")

print(f"\nLocal highPcts count: {len(local_h)}")
print(f"Local lowPcts count: {len(local_l)}")

# Compare arrays
print(f"\n{'='*80}")
print("ARRAY COMPARISON")
print(f"{'='*80}")

# Sort both arrays and compare
webui_h_sorted = sorted(webui_highPcts)
local_h_sorted = sorted(local_h)
webui_l_sorted = sorted(webui_lowPcts)
local_l_sorted = sorted(local_l)

print(f"\nHigh Pcts (sorted):")
print(f"{'Idx':<5} {'WebUI':>15} {'Local':>15} {'Diff':>15} {'Match':>8}")
print(f"{'-'*60}")
all_h_match = True
for i in range(max(len(webui_h_sorted), len(local_h_sorted))):
    w = webui_h_sorted[i] if i < len(webui_h_sorted) else None
    l = local_h_sorted[i] if i < len(local_h_sorted) else None
    if w is not None and l is not None:
        diff = w - l
        match = "✅" if abs(diff) < 0.001 else "❌"
        if match == "❌":
            all_h_match = False
        print(f"{i:<5} {w:>15.6f} {l:>15.6f} {diff:>15.6f} {match:>8}")
    elif w is not None:
        print(f"{i:<5} {w:>15.6f} {'MISSING':>15} {'':>15} {'❌':>8}")
        all_h_match = False
    elif l is not None:
        print(f"{i:<5} {'MISSING':>15} {l:>15.6f} {'':>15} {'❌':>8}")
        all_h_match = False

print(f"\nAll high match: {'✅' if all_h_match else '❌'}")

print(f"\nLow Pcts (sorted):")
print(f"{'Idx':<5} {'WebUI':>15} {'Local':>15} {'Diff':>15} {'Match':>8}")
print(f"{'-'*60}")
all_l_match = True
for i in range(max(len(webui_l_sorted), len(local_l_sorted))):
    w = webui_l_sorted[i] if i < len(webui_l_sorted) else None
    l = local_l_sorted[i] if i < len(local_l_sorted) else None
    if w is not None and l is not None:
        diff = w - l
        match = "✅" if abs(diff) < 0.001 else "❌"
        if match == "❌":
            all_l_match = False
        print(f"{i:<5} {w:>15.6f} {l:>15.6f} {diff:>15.6f} {match:>8}")
    elif w is not None:
        print(f"{i:<5} {w:>15.6f} {'MISSING':>15} {'':>15} {'❌':>8}")
        all_l_match = False
    elif l is not None:
        print(f"{i:<5} {'MISSING':>15} {l:>15.6f} {'':>15} {'❌':>8}")
        all_l_match = False

print(f"\nAll low match: {'✅' if all_l_match else '❌'}")

# Compute mode/median from both arrays
def mode_bucket(values, bucket_size=0.1):
    buckets = defaultdict(int)
    for v in values:
        bin_start = math.floor(v / bucket_size) * bucket_size
        buckets[round(bin_start, 1)] += 1
    max_count = max(buckets.values())
    candidates = sorted([k for k, v in buckets.items() if v == max_count])
    return candidates[0]

def median_bin(values, bucket_size=0.1):
    sorted_vals = sorted(values)
    mid_idx = len(sorted_vals) // 2
    median_val = sorted_vals[mid_idx]
    bin_start = math.floor(median_val / bucket_size) * bucket_size
    return round(bin_start, 1)

# JS-style mode (Object.entries().sort((a,b) => b[1] - a[1]) — insertion order on ties)
def mode_bucket_js(values, bucket_size=0.1):
    """Simulate JS object key insertion order for tie-breaking."""
    buckets = {}  # dict preserves insertion order in Python 3.7+
    for v in values:
        bin_start = round(math.floor(v / bucket_size) * bucket_size, 1)
        if bin_start not in buckets:
            buckets[bin_start] = 0
        buckets[bin_start] += 1
    # Sort by count desc, insertion order on ties (stable sort)
    entries = list(buckets.items())
    entries.sort(key=lambda x: -x[1])  # Python sort is stable, so ties keep insertion order
    return entries[0][0]

print(f"\n{'='*80}")
print("MODE/MEDIAN COMPARISON")
print(f"{'='*80}")

print(f"\n{'Field':<15} {'WebUI Array':>15} {'Local Array':>15} {'Match':>8}")
print(f"{'-'*55}")
h_mode_w = mode_bucket_js(webui_highPcts)
h_mode_l = mode_bucket_js(local_h)
h_med_w = median_bin(webui_highPcts)
h_med_l = median_bin(local_h)
l_mode_w = mode_bucket_js(webui_lowPcts)
l_mode_l = mode_bucket_js(local_l)
l_med_w = median_bin(webui_lowPcts)
l_med_l = median_bin(local_l)

print(f"{'h_mode':<15} {h_mode_w:>15.1f} {h_mode_l:>15.1f} {'✅' if h_mode_w == h_mode_l else '❌':>8}")
print(f"{'h_median':<15} {h_med_w:>15.1f} {h_med_l:>15.1f} {'✅' if h_med_w == h_med_l else '❌':>8}")
print(f"{'l_mode':<15} {l_mode_w:>15.1f} {l_mode_l:>15.1f} {'✅' if l_mode_w == l_mode_l else '❌':>8}")
print(f"{'l_median':<15} {l_med_w:>15.1f} {l_med_l:>15.1f} {'✅' if l_med_w == l_med_l else '❌':>8}")

# Also compute with sorted tie-breaking (our current approach)
print(f"\n{'Field':<15} {'WebUI (sorted)':>15} {'Local (sorted)':>15} {'Match':>8}")
print(f"{'-'*55}")
h_mode_w2 = mode_bucket(webui_highPcts)
h_mode_l2 = mode_bucket(local_h)
l_mode_w2 = mode_bucket(webui_lowPcts)
l_mode_l2 = mode_bucket(local_l)
print(f"{'h_mode':<15} {h_mode_w2:>15.1f} {h_mode_l2:>15.1f} {'✅' if h_mode_w2 == h_mode_l2 else '❌':>8}")
print(f"{'l_mode':<15} {l_mode_w2:>15.1f} {l_mode_l2:>15.1f} {'✅' if l_mode_w2 == l_mode_l2 else '❌':>8}")

# Check what the WebUI actually displays (from browser):
print(f"\n{'='*80}")
print("WEBUI DISPLAYED vs COMPUTED FROM WEBUI ARRAY")
print(f"{'='*80}")
print(f"{'Field':<15} {'Displayed':>20} {'Computed from array':>25} {'Match':>8}")
print(f"{'-'*70}")
print(f"{'h_mode':<15} {'0.5 to 0.6 %':>20} {f'{h_mode_w:.1f} to {h_mode_w+0.1:.1f} %':>25} {'✅' if h_mode_w == 0.5 else '❌':>8}")
print(f"{'h_median':<15} {'0.7 to 0.8 %':>20} {f'{h_med_w:.1f} to {h_med_w+0.1:.1f} %':>25} {'✅' if h_med_w == 0.7 else '❌':>8}")
print(f"{'l_mode':<15} {'-0.3 to -0.2 %':>20} {f'{l_mode_w:.1f} to {l_mode_w+0.1:.1f} %':>25} {'✅' if l_mode_w == -0.3 else '❌':>8}")
print(f"{'l_median':<15} {'-0.8 to -0.7 %':>20} {f'{l_med_w:.1f} to {l_med_w+0.1:.1f} %':>25} {'✅' if l_med_w == -0.8 else '❌':>8}")