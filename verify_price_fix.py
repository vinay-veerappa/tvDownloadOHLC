"""Compare WebUI highPcts/lowPcts (after fix) with local computation."""
import json
import math
from collections import defaultdict
from pathlib import Path
import numpy as np

_DATA = Path(__file__).parent / "data"

# WebUI arrays (extracted from browser after useDailyHodLod fix)
webui_h = [0.0936914428482094,0.12863804470171214,0.4059539918809252,0.41038880967978475,0.41852301876603715,0.46974000436967867,0.496277915632759,0.5221462009362687,0.5325112107623209,0.5945639864099572,0.6045445069835287,0.6156792994937765,0.6623400457131501,0.6847319347319303,0.7831179181537751,0.8027091433588263,0.8635479812421298,0.8819087888855437,0.9957842709696241,1.0806047676467756,1.1271613044429918,1.1342846688620511,1.2305465074194721,1.5329926682959405,1.598486928403653,1.6022174148188295,1.6061099567585835,1.759633436217256,1.7781541066892448,1.8107940994611882,2.2001495247249814,2.222515623624677,2.3089080788876837,2.510018983336848,3.779229635495729]
webui_l = [-4.323982282218941,-2.328535139712107,-2.167950894606241,-1.9320482351905643,-1.9178653324994799,-1.6200891049007682,-1.390524071658128,-1.3603038600830342,-1.1409047924102356,-0.9208145314611671,-0.8921422852567806,-0.8688340807174844,-0.7537688442211032,-0.7282956340796121,-0.7188160676532718,-0.6133475558853574,-0.5536130536130557,-0.5322077445402806,-0.5041411595246625,-0.4640662235043225,-0.46095299351449626,-0.44465727185661885,-0.3999111308598091,-0.3963759909399789,-0.38534342888048023,-0.3524511374559447,-0.26955691581962427,-0.2571041948579156,-0.23259194650385728,-0.21861336664584785,-0.16286644951140072,-0.09147457006951631,-0.08662808829135171,-0.07879185817465384,-0.05499461052816956]

# Load local data
sessions = json.load(open(_DATA / "NQ1_profiler.json"))
if isinstance(sessions, dict):
    sessions = sessions.get("sessions", [])
by_date = defaultdict(dict)
for s in sessions:
    by_date[s["date"]][s["session"]] = s

daily_hl = json.load(open(_DATA / "NQ1_daily_hod_lod_unadjusted.json"))
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
    if ny1.get("status") == "Long True":
        matched.append(date)

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

local_h_sorted = sorted(local_h)
local_l_sorted = sorted(local_l)

print(f"WebUI highPcts count: {len(webui_h)}")
print(f"Local highPcts count: {len(local_h)}")
print(f"WebUI lowPcts count: {len(webui_l)}")
print(f"Local lowPcts count: {len(local_l)}")

# Compare arrays
print(f"\n{'='*80}")
print("ARRAY COMPARISON (sorted)")
print(f"{'='*80}")

print(f"\nHigh Pcts:")
print(f"{'Idx':<5} {'WebUI':>15} {'Local':>15} {'Diff':>15} {'Match':>8}")
print(f"{'-'*60}")
all_h_match = True
for i in range(max(len(webui_h), len(local_h_sorted))):
    w = webui_h[i] if i < len(webui_h) else None
    l = local_h_sorted[i] if i < len(local_h_sorted) else None
    if w is not None and l is not None:
        diff = w - l
        match = "YES" if abs(diff) < 0.001 else "NO"
        if match == "NO":
            all_h_match = False
            print(f"{i:<5} {w:>15.6f} {l:>15.6f} {diff:>15.6f} {match:>8}")
    elif w is not None:
        print(f"{i:<5} {w:>15.6f} {'MISSING':>15} {'':>15} {'NO':>8}")
        all_h_match = False
    elif l is not None:
        print(f"{i:<5} {'MISSING':>15} {l:>15.6f} {'':>15} {'NO':>8}")
        all_h_match = False

if all_h_match:
    print("  All 35 values match!")
print(f"\nAll high match: {'YES' if all_h_match else 'NO'}")

print(f"\nLow Pcts:")
print(f"{'Idx':<5} {'WebUI':>15} {'Local':>15} {'Diff':>15} {'Match':>8}")
print(f"{'-'*60}")
all_l_match = True
for i in range(max(len(webui_l), len(local_l_sorted))):
    w = webui_l[i] if i < len(webui_l) else None
    l = local_l_sorted[i] if i < len(local_l_sorted) else None
    if w is not None and l is not None:
        diff = w - l
        match = "YES" if abs(diff) < 0.001 else "NO"
        if match == "NO":
            all_l_match = False
            print(f"{i:<5} {w:>15.6f} {l:>15.6f} {diff:>15.6f} {match:>8}")
    elif w is not None:
        print(f"{i:<5} {w:>15.6f} {'MISSING':>15} {'':>15} {'NO':>8}")
        all_l_match = False
    elif l is not None:
        print(f"{i:<5} {'MISSING':>15} {l:>15.6f} {'':>15} {'NO':>8}")
        all_l_match = False

if all_l_match:
    print("  All 35 values match!")
print(f"\nAll low match: {'YES' if all_l_match else 'NO'}")

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

# JS-style mode (insertion order on ties)
def mode_bucket_js(values, bucket_size=0.1):
    buckets = {}
    for v in values:
        bin_start = round(math.floor(v / bucket_size) * bucket_size, 1)
        if bin_start not in buckets:
            buckets[bin_start] = 0
        buckets[bin_start] += 1
    entries = list(buckets.items())
    entries.sort(key=lambda x: -x[1])
    return entries[0][0]

print(f"\n{'='*80}")
print("MODE/MEDIAN COMPARISON")
print(f"{'='*80}")
print(f"\n{'Field':<15} {'WebUI':>15} {'Local':>15} {'Lookup':>15} {'Match':>10}")
print(f"{'-'*70}")

lk_ps = lookup["tables"]["NY1"]["LF|LF"]["price_stats"]["LT"]

h_mode_w = mode_bucket_js(webui_h)
h_mode_l = mode_bucket_js(local_h)
h_med_w = median_bin(webui_h)
h_med_l = median_bin(local_h)
l_mode_w = mode_bucket_js(webui_l)
l_mode_l = mode_bucket_js(local_l)
l_med_w = median_bin(webui_l)
l_med_l = median_bin(local_l)

def fmt(v):
    return f"{v:.1f} to {v+0.1:.1f} %"

def check(w, l, lk):
    all_match = (w == l) and (l == lk)
    return "ALL MATCH" if all_match else f"W:{'Y' if w==l else 'N'} L:{'Y' if l==lk else 'N'}"

print(f"{'h_mode':<15} {fmt(h_mode_w):>15} {fmt(h_mode_l):>15} {fmt(lk_ps['h_mode']):>15} {check(h_mode_w, h_mode_l, lk_ps['h_mode']):>10}")
print(f"{'h_median':<15} {fmt(h_med_w):>15} {fmt(h_med_l):>15} {fmt(lk_ps['h_med']):>15} {check(h_med_w, h_med_l, lk_ps['h_med']):>10}")
print(f"{'l_mode':<15} {fmt(l_mode_w):>15} {fmt(l_mode_l):>15} {fmt(lk_ps['l_mode']):>15} {check(l_mode_w, l_mode_l, lk_ps['l_mode']):>10}")
print(f"{'l_median':<15} {fmt(l_med_w):>15} {fmt(l_med_l):>15} {fmt(lk_ps['l_med']):>15} {check(l_med_w, l_med_l, lk_ps['l_med']):>10}")

# Also show the old WebUI values (before fix) for comparison
print(f"\n{'='*80}")
print("BEFORE FIX vs AFTER FIX")
print(f"{'='*80}")
print(f"{'Field':<15} {'Before (broken)':>20} {'After (fixed)':>20} {'Local/Lookup':>20}")
print(f"{'-'*75}")
print(f"{'h_mode':<15} {'0.5 to 0.6 %':>20} {fmt(h_mode_w):>20} {fmt(h_mode_l):>20}")
print(f"{'h_median':<15} {'0.7 to 0.8 %':>20} {fmt(h_med_w):>20} {fmt(h_med_l):>20}")
print(f"{'l_mode':<15} {'-0.3 to -0.2 %':>20} {fmt(l_mode_w):>20} {fmt(l_mode_l):>20}")
print(f"{'l_median':<15} {'-0.8 to -0.7 %':>20} {fmt(l_med_w):>20} {fmt(l_med_l):>20}")