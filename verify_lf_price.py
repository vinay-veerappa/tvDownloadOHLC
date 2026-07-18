"""Verify Long False price distribution: WebUI vs Local vs Lookup."""
import json
import math
from collections import defaultdict
from pathlib import Path

_DATA = Path(__file__).parent / "data"

# WebUI values (from browser)
webui = {
    "count": 45,
    "h_mode": "0.1 to 0.2 %",
    "h_median": "0.4 to 0.5 %",
    "l_mode": "-1.0 to -0.9 %",
    "l_median": "-0.8 to -0.7 %",
}
webui_h = [0.07585335018962525,0.07616146230007281,0.11457782478405676,0.12496528742016455,0.14826443397872868,0.14992503748125774,0.15808888108204133,0.17479461632581295,0.1754143008816822,0.17624954274881866,0.1844670652232372,0.1995848634839481,0.21689206430210994,0.23563073297989678,0.2391470422161035,0.2520655370396252,0.3283622930633445,0.33162496231533556,0.3456593166581312,0.40128410914928025,0.41294947212591193,0.4184684056353749,0.42446941323346365,0.48450135984583476,0.4918566775244271,0.4938740621141635,0.5248792777661215,0.5558899550331065,0.560157320779453,0.5757124441496453,0.5822341302555545,0.5909666525960366,0.5986530306809623,0.7296197558580131,0.773857411025558,0.8656873032528933,0.92592592592593,1.0993225105458304,1.103036594861151,1.236690610830915,1.2436860647735415,1.291729575574574,1.5801354401805856,2.0148546144121315]
webui_l = [-2.6435974003161777,-2.5916561314791364,-2.3297491039426577,-2.3084332547248176,-2.222751921816335,-1.7006802721088454,-1.6722018295169838,-1.5246236284766512,-1.4787572309696184,-1.4718133851707838,-1.414367735611255,-1.338265694701335,-1.3043844147100914,-1.0740689077974652,-0.9975781340099132,-0.9936766034327027,-0.9841302555647191,-0.9353953604390175,-0.9270965023177369,-0.8337606594116198,-0.8200032315398342,-0.7798850885250674,-0.7669691934040657,-0.7548801170563002,-0.7096281648540037,-0.6866416978776546,-0.6838256244657615,-0.6430428239157182,-0.5830618892508133,-0.5752771151957381,-0.528554689490035,-0.47445384697093473,-0.43284365162644667,-0.41776131616348966,-0.40228393459641465,-0.3386004514672636,-0.32102728731941976,-0.28343480999369897,-0.2516356316054402,-0.2395018361807444,-0.2298492344851799,-0.17079813506901687,-0.08442380751372269,-0.05518061038244371]

# Load local data
sessions = json.load(open(_DATA / "NQ1_profiler.json"))
if isinstance(sessions, dict):
    sessions = sessions.get("sessions", [])
by_date = defaultdict(dict)
for s in sessions:
    by_date[s["date"]][s["session"]] = s

daily_hl = json.load(open(_DATA / "NQ1_daily_hod_lod_unadjusted.json"))
lookup = json.load(open(_DATA / "derived" / "NQ1_profiler_lookup.json"))

# Apply filter: Asia=Long False, London=Long False -> NY1 Long False
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
    if ny1.get("status") == "Long False":
        matched.append(date)

print(f"Long False dates: {len(matched)}")

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

print(f"Local highPcts: {len(local_h)}, WebUI highPcts: {len(webui_h)}")
print(f"Local lowPcts: {len(local_l)}, WebUI lowPcts: {len(webui_l)}")

# Compare arrays
print(f"\n{'='*70}")
print("ARRAY COMPARISON")
print(f"{'='*70}")

all_h_match = True
for i in range(max(len(webui_h), len(local_h_sorted))):
    w = webui_h[i] if i < len(webui_h) else None
    l = local_h_sorted[i] if i < len(local_h_sorted) else None
    if w is not None and l is not None:
        if abs(w - l) >= 0.001:
            all_h_match = False
            print(f"  HIGH MISMATCH [{i}]: webui={w:.6f}, local={l:.6f}, diff={w-l:.6f}")
    elif w is not None:
        all_h_match = False
        print(f"  HIGH [{i}]: webui={w:.6f}, local=MISSING")
    elif l is not None:
        all_h_match = False
        print(f"  HIGH [{i}]: webui=MISSING, local={l:.6f}")
print(f"High arrays match: {'YES' if all_h_match else 'NO'}")

all_l_match = True
for i in range(max(len(webui_l), len(local_l_sorted))):
    w = webui_l[i] if i < len(webui_l) else None
    l = local_l_sorted[i] if i < len(local_l_sorted) else None
    if w is not None and l is not None:
        if abs(w - l) >= 0.001:
            all_l_match = False
            print(f"  LOW MISMATCH [{i}]: webui={w:.6f}, local={l:.6f}, diff={w-l:.6f}")
    elif w is not None:
        all_l_match = False
        print(f"  LOW [{i}]: webui={w:.6f}, local=MISSING")
    elif l is not None:
        all_l_match = False
        print(f"  LOW [{i}]: webui=MISSING, local={l:.6f}")
print(f"Low arrays match: {'YES' if all_l_match else 'NO'}")

# Compute mode/median
def mode_bucket(values, bucket_size=0.1):
    buckets = defaultdict(int)
    for v in values:
        buckets[round(math.floor(v / bucket_size) * bucket_size, 1)] += 1
    max_count = max(buckets.values())
    candidates = sorted([k for k, v in buckets.items() if v == max_count])
    return candidates[0]

def median_bin(values, bucket_size=0.1):
    sorted_vals = sorted(values)
    mid_idx = len(sorted_vals) // 2
    bin_start = math.floor(sorted_vals[mid_idx] / bucket_size) * bucket_size
    return round(bin_start, 1)

def fmt(v):
    return f"{v:.1f} to {v+0.1:.1f} %"

# Lookup table values
lk_ps = lookup["tables"]["NY1"]["LF|LF"]["price_stats"]["LF"]

h_mode_l = mode_bucket(local_h)
h_med_l = median_bin(local_h)
l_mode_l = mode_bucket(local_l)
l_med_l = median_bin(local_l)

print(f"\n{'='*70}")
print("MODE/MEDIAN: WebUI vs Local vs Lookup")
print(f"{'='*70}")
print(f"{'Field':<12} {'WebUI':<20} {'Local':<20} {'Lookup':<20} {'Match':<10}")
print(f"{'-'*82}")

for name, wv, lv, lkv in [
    ("h_mode", webui["h_mode"], fmt(h_mode_l), fmt(lk_ps["h_mode"])),
    ("h_median", webui["h_median"], fmt(h_med_l), fmt(lk_ps["h_med"])),
    ("l_mode", webui["l_mode"], fmt(l_mode_l), fmt(lk_ps["l_mode"])),
    ("l_median", webui["l_median"], fmt(l_med_l), fmt(lk_ps["l_med"])),
]:
    match = "ALL MATCH" if (wv == lv == lkv) else f"W:{'Y' if wv==lv else 'N'} L:{'Y' if lv==lkv else 'N'}"
    print(f"{name:<12} {wv:<20} {lv:<20} {lkv:<20} {match:<10}")