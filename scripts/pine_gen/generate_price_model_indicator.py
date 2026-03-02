"""
Generate Standalone Price Model Indicator for TradingView.

Architecture: Strategy S3 (Direction-Only Context + Full Outcome)
- Context filters use Long/Short/Neutral to keep sample sizes high
- Outcome curves preserve full LT/LF/ST/SF granularity
- Hierarchical fallback: Level 1 (full context) -> Level 2 (single pred) -> Level 3 (baseline)
- String-packed map for TradingView memory efficiency

Output Files:
  - scripts/profiler/PriceModelData.pine     (library with packed model strings)
  - scripts/profiler/PriceModelIndicator.pine (standalone indicator)
"""

import json
import os
import sys
import requests
import itertools
from collections import defaultdict
from pathlib import Path

API_BASE_URL = "http://localhost:8000"
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "profiler"

TICKER = "NQ1"
BUCKET = 5
MIN_SAMPLE = 30

DIRECTIONS = ['L', 'S', 'N']
OUTCOMES = ['Long True', 'Long False', 'Short True', 'Short False']
OUTCOME_SHORT = {'Long True': 'LT', 'Long False': 'LF', 'Short True': 'ST', 'Short False': 'SF'}

# Context dependency chains
CONTEXT_DEPS = {
    'Asia':   [('prev_ny1', DIRECTIONS), ('prev_ny2', DIRECTIONS)],
    'London': [('asia',     DIRECTIONS), ('prev_ny2', DIRECTIONS)],
    'NY1':    [('asia',     DIRECTIONS), ('london',   DIRECTIONS)],
    'NY2':    [('asia',     DIRECTIONS), ('london',   DIRECTIONS), ('ny1', DIRECTIONS)],
}


def dir_only(status):
    """Map full status to direction: L, S, or N."""
    if isinstance(status, str):
        if status.startswith('Long'):
            return 'L'
        elif status.startswith('Short'):
            return 'S'
    return 'N'


def load_context_table():
    """Build cross-day context table from profiler JSON."""
    data_file = DATA_DIR / f"{TICKER}_profiler.json"
    with open(data_file, 'r') as f:
        sessions = json.load(f)

    days = defaultdict(dict)
    for s in sessions:
        if 'date' in s and 'session' in s and 'status' in s:
            days[s['date']][s['session']] = s.get('status', 'None')

    sorted_dates = sorted(days.keys())
    ctx = {}

    for i in range(1, len(sorted_dates)):
        prev_date = sorted_dates[i - 1]
        curr_date = sorted_dates[i]
        prev = days[prev_date]
        curr = days[curr_date]

        ctx[curr_date] = {
            'prev_ny1':     prev.get('NY1', 'None'),
            'prev_ny1_dir': dir_only(prev.get('NY1', 'None')),
            'prev_ny2':     prev.get('NY2', 'None'),
            'prev_ny2_dir': dir_only(prev.get('NY2', 'None')),
            'asia':         curr.get('Asia', 'None'),
            'asia_dir':     dir_only(curr.get('Asia', 'None')),
            'london':       curr.get('London', 'None'),
            'london_dir':   dir_only(curr.get('London', 'None')),
            'ny1':          curr.get('NY1', 'None'),
            'ny1_dir':      dir_only(curr.get('NY1', 'None')),
            'ny2':          curr.get('NY2', 'None'),
            'ny2_dir':      dir_only(curr.get('NY2', 'None')),
        }

    print(f"Built context table for {len(ctx)} trading days.")
    return ctx


def fetch_model_by_dates(target_session, dates):
    """Call the custom-price-model endpoint with explicit dates."""
    url = f"{API_BASE_URL}/stats/custom-price-model"
    payload = {
        "ticker": TICKER,
        "target_session": target_session,
        "dates": dates,
        "bucket_minutes": BUCKET,
    }
    try:
        resp = requests.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"  API error: {e}")
        return {"median": [], "extreme": [], "count": 0}


def fetch_model_filtered(target_session, filters):
    """Call the filtered-price-model endpoint with same-day filters."""
    url = f"{API_BASE_URL}/stats/filtered-price-model"
    payload = {
        "ticker": TICKER,
        "target_session": target_session,
        "filters": filters,
        "broken_filters": {},
        "intra_state": "Any",
        "bucket_minutes": BUCKET,
    }
    try:
        resp = requests.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"  API error: {e}")
        return {"median": [], "extreme": [], "count": 0}


def pack_model(model_data):
    """Pack median path into a compact string: 'h1:l1,h2:l2,...'"""
    median = model_data.get("median", [])
    if not median:
        return None
    parts = []
    for pt in median:
        h = round(pt.get("high", 0.0), 3)
        l = round(pt.get("low", 0.0), 3)
        parts.append(f"{h}:{l}")
    return ",".join(parts)


def generate_all_models(ctx_table):
    """Generate all contextual price models."""
    models = {}  # key -> (packed_string, count)
    stats = {"total_calls": 0, "valid": 0, "skipped_low_n": 0, "skipped_empty": 0}

    # ---- Level 1: Full directional context ----
    for target_session, deps in CONTEXT_DEPS.items():
        print(f"\n=== {target_session} Level 1 Models ===")
        dep_names = [d[0] for d in deps]
        dep_values = [d[1] for d in deps]
        combos = list(itertools.product(*dep_values))

        for combo in combos:
            ctx_dict = dict(zip(dep_names, combo))

            for outcome in OUTCOMES:
                stats["total_calls"] += 1
                key = f"{target_session}_{'_'.join(combo)}_{OUTCOME_SHORT[outcome]}"

                # Find matching dates from context table
                if target_session in ['Asia', 'London']:
                    # Cross-day filtering: compute dates locally
                    matching_dates = []
                    for date, c in ctx_table.items():
                        match = True
                        for dep_name, dep_val in ctx_dict.items():
                            if dep_val == 'N':
                                if c.get(f'{dep_name}_dir') != 'N':
                                    match = False
                                    break
                            else:
                                if c.get(f'{dep_name}_dir') != dep_val:
                                    match = False
                                    break
                        # Also check outcome
                        sess_key = target_session.lower()
                        if sess_key == 'asia':
                            if c.get('asia') != outcome:
                                match = False
                        elif sess_key == 'london':
                            if c.get('london') != outcome:
                                match = False
                        if match:
                            matching_dates.append(date)

                    if len(matching_dates) < MIN_SAMPLE:
                        stats["skipped_low_n"] += 1
                        continue

                    result = fetch_model_by_dates(target_session, matching_dates)

                else:
                    # Same-day filtering: use filtered API
                    filters = {}
                    dep_to_session = {'asia': 'Asia', 'london': 'London', 'ny1': 'NY1'}
                    for dep_name, dep_val in ctx_dict.items():
                        if dep_val == 'N':
                            continue
                        sess_name = dep_to_session.get(dep_name)
                        if sess_name:
                            filters[sess_name] = 'Long' if dep_val == 'L' else 'Short'
                    filters[target_session] = outcome
                    result = fetch_model_filtered(target_session, filters)

                count = result.get("count", 0)
                if count < MIN_SAMPLE:
                    stats["skipped_low_n"] += 1
                    continue

                packed = pack_model(result)
                if not packed:
                    stats["skipped_empty"] += 1
                    continue

                models[key] = (packed, count)
                stats["valid"] += 1
                print(f"  {key}: N={count} ✓")

    # ---- Level 2: Single predecessor fallback ----
    print(f"\n=== Level 2 Fallback Models (Single Predecessor) ===")
    # Asia -> prev_ny2, London -> asia, NY1 -> london, NY2 -> ny1
    fallback_deps = {
        'Asia':   'prev_ny2',
        'London': 'asia',
        'NY1':    'london',
        'NY2':    'ny1',
    }
    for target_session, dep_name in fallback_deps.items():
        for dep_val in DIRECTIONS:
            for outcome in OUTCOMES:
                stats["total_calls"] += 1
                key = f"{target_session}_F_{dep_val}_{OUTCOME_SHORT[outcome]}"

                if target_session in ['Asia', 'London']:
                    matching_dates = []
                    for date, c in ctx_table.items():
                        if dep_val != 'N' and c.get(f'{dep_name}_dir') != dep_val:
                            continue
                        if dep_val == 'N' and c.get(f'{dep_name}_dir') != 'N':
                            continue
                        sess_key = target_session.lower()
                        if c.get(sess_key) != outcome:
                            continue
                        matching_dates.append(date)

                    if len(matching_dates) < MIN_SAMPLE:
                        stats["skipped_low_n"] += 1
                        continue
                    result = fetch_model_by_dates(target_session, matching_dates)
                else:
                    dep_to_sess = {'asia': 'Asia', 'london': 'London', 'ny1': 'NY1'}
                    filters = {}
                    if dep_val != 'N':
                        sess_name = dep_to_sess.get(dep_name)
                        if sess_name:
                            filters[sess_name] = 'Long' if dep_val == 'L' else 'Short'
                    filters[target_session] = outcome
                    result = fetch_model_filtered(target_session, filters)

                count = result.get("count", 0)
                if count < MIN_SAMPLE:
                    stats["skipped_low_n"] += 1
                    continue

                packed = pack_model(result)
                if not packed:
                    stats["skipped_empty"] += 1
                    continue

                models[key] = (packed, count)
                stats["valid"] += 1
                print(f"  {key}: N={count} ✓")

    # ---- Level 3: Baseline (unfiltered) ----
    print(f"\n=== Level 3 Baseline Models (Unfiltered) ===")
    for target_session in ['Asia', 'London', 'NY1', 'NY2']:
        for outcome in OUTCOMES:
            stats["total_calls"] += 1
            key = f"{target_session}_B_{OUTCOME_SHORT[outcome]}"
            filters = {target_session: outcome}
            result = fetch_model_filtered(target_session, filters)

            count = result.get("count", 0)
            packed = pack_model(result)
            if not packed:
                stats["skipped_empty"] += 1
                continue

            models[key] = (packed, count)
            stats["valid"] += 1
            print(f"  {key}: N={count} ✓")

    print(f"\n=== Generation Summary ===")
    print(f"  Total API calls: {stats['total_calls']}")
    print(f"  Valid models: {stats['valid']}")
    print(f"  Skipped (N<{MIN_SAMPLE}): {stats['skipped_low_n']}")
    print(f"  Skipped (empty): {stats['skipped_empty']}")

    return models


def write_library(models):
    """Write the PriceModelData.pine library."""
    # Check if we need to split into multiple libraries
    # Pine Script string literals max 4096 chars; most models ~1500 chars — safe
    total_chars = sum(len(v[0]) for v in models.values())
    print(f"\nTotal packed data: {total_chars:,} characters across {len(models)} models")

    lines = []
    lines.append("// Auto-generated by generate_price_model_indicator.py")
    lines.append("// DO NOT EDIT MANUALLY")
    lines.append("//@version=6")
    lines.append(f'library("PriceModelData", overlay=true)')
    lines.append("")
    lines.append("// Returns map of all contextual price models")
    lines.append("// Key format: SESSION_CTX1_CTX2_OUTCOME (L1), SESSION_F_CTX_OUTCOME (L2), SESSION_B_OUTCOME (L3)")
    lines.append("// Value format: 'high:low,high:low,...' (5-min buckets, % from session open)")
    lines.append("export f_get_models() =>")
    lines.append("    m = map.new<string, string>()")

    for key, (packed, count) in sorted(models.items()):
        # Pine Script string literal — escape any quotes (shouldn't be any)
        lines.append(f'    m.put("{key}", "{packed}")')

    lines.append("    m")
    lines.append("")

    out_path = OUTPUT_DIR / "PriceModelData.pine"
    with open(out_path, 'w', newline='\n') as f:
        f.write('\n'.join(lines))
    print(f"Generated {out_path} ({len(models)} models)")


def write_indicator():
    """Write the PriceModelIndicator.pine standalone indicator."""
    code = r"""// Auto-generated by generate_price_model_indicator.py
// DO NOT EDIT MANUALLY
//@version=6
indicator("NQ Price Model", overlay=true, max_polypoints=10000)

import vinay_veerappa/PriceModelData/1 as PMD

// ===== INPUTS =====
grp = "Price Model"
i_mode     = input.string("Auto", "Session", options=["Auto", "Asia", "London", "NY1", "NY2"], group=grp)
i_outcome  = input.string("Auto", "Outcome", options=["Auto", "Long True", "Long False", "Short True", "Short False"], group=grp)
i_scale    = input.float(1.0, "Scale", step=0.1, minval=0.1, maxval=5.0, group=grp)
c_hi       = input.color(#4CAF5080, "High Color", inline="c1", group=grp)
c_lo       = input.color(#F4433680, "Low Color", inline="c1", group=grp)
w_line     = input.int(2, "Line Width", minval=1, maxval=5, group=grp)

grp_dbg = "Debug"
i_show_key = input.bool(false, "Show Model Key", group=grp_dbg)

// ===== SESSION WINDOWS (EST) =====
var string TZ = "America/New_York"

in_asia_class()  => not na(time(timeframe.period, "1800-1929", TZ))
in_lon_class()   => not na(time(timeframe.period, "0230-0329", TZ))
in_ny1_class()   => not na(time(timeframe.period, "0730-0829", TZ))
in_ny2_class()   => not na(time(timeframe.period, "1130-1229", TZ))

in_asia()   => not na(time(timeframe.period, "1800-0229", TZ))
in_london() => not na(time(timeframe.period, "0230-0729", TZ))
in_ny1()    => not na(time(timeframe.period, "0730-1129", TZ))
in_ny2()    => not na(time(timeframe.period, "1130-1559", TZ))

// ===== SESSION STATE TRACKING =====
var float v_asia_h = na, var float v_asia_l = na, var float v_asia_open = na
var float v_lon_h  = na, var float v_lon_l  = na, var float v_lon_open = na
var float v_ny1_h  = na, var float v_ny1_l  = na, var float v_ny1_open = na
var float v_ny2_open = na
var int   v_day_bi = 0

// Directions: L=Long, S=Short, N=Neutral
var string v_prev_ny1_dir = "N"
var string v_prev_ny2_dir = "N"
var string v_asia_dir = "N"
var string v_lon_dir  = "N"
var string v_ny1_dir  = "N"

// ===== DAY BOUNDARY =====
bool _new_day = in_asia_class() and not in_asia_class()[1]

if _new_day
    // Save prev day context
    v_prev_ny1_dir := v_ny1_dir
    v_prev_ny2_dir := v_lon_dir  // NY2 dir not tracked separately, use last known
    // Reset
    v_asia_h := high
    v_asia_l := low
    v_asia_open := open
    v_lon_h := na
    v_lon_l := na
    v_lon_open := na
    v_ny1_h := na
    v_ny1_l := na
    v_ny1_open := na
    v_ny2_open := na
    v_asia_dir := "N"
    v_lon_dir  := "N"
    v_ny1_dir  := "N"
    v_day_bi := bar_index

// ===== CLASSIFICATION TRACKING =====
// Asia
if in_asia_class()
    v_asia_h := math.max(nz(v_asia_h, high), high)
    v_asia_l := math.min(nz(v_asia_l, low), low)

// London
if in_lon_class() and not in_lon_class()[1]
    v_lon_open := open
    v_lon_h := high
    v_lon_l := low
if in_lon_class()
    v_lon_h := math.max(nz(v_lon_h, high), high)
    v_lon_l := math.min(nz(v_lon_l, low), low)

// NY1
if in_ny1_class() and not in_ny1_class()[1]
    v_ny1_open := open
    v_ny1_h := high
    v_ny1_l := low
if in_ny1_class()
    v_ny1_h := math.max(nz(v_ny1_h, high), high)
    v_ny1_l := math.min(nz(v_ny1_l, low), low)

// NY2
if in_ny2_class() and not in_ny2_class()[1]
    v_ny2_open := open

// ===== DIRECTION CLASSIFICATION =====
float _asia_mid = na(v_asia_h) or na(v_asia_l) ? na : (v_asia_h + v_asia_l) / 2.0
float _lon_mid  = na(v_lon_h)  or na(v_lon_l)  ? na : (v_lon_h  + v_lon_l)  / 2.0
float _ny1_mid  = na(v_ny1_h)  or na(v_ny1_l)  ? na : (v_ny1_h  + v_ny1_l)  / 2.0

if not na(_asia_mid)
    v_asia_dir := close > _asia_mid ? "L" : "S"
if not na(_lon_mid)
    v_lon_dir := close > _lon_mid ? "L" : "S"
if not na(_ny1_mid)
    v_ny1_dir := close > _ny1_mid ? "L" : "S"

// ===== PRICE MODEL RENDERING =====
var polyline pm_h = na
var polyline pm_l = na
var label lbl_key = na

if barstate.islast and v_day_bi > 0
    // Load model map
    var map<string, string> models = PMD.f_get_models()

    // Determine active session
    string active = in_ny2() ? "NY2" : in_ny1() ? "NY1" : in_london() ? "London" : "Asia"
    string target = i_mode == "Auto" ? active : i_mode

    // Build context key
    string ctx = ""
    if target == "Asia"
        ctx := v_prev_ny1_dir + "_" + v_prev_ny2_dir
    else if target == "London"
        ctx := v_asia_dir + "_" + v_prev_ny2_dir
    else if target == "NY1"
        ctx := v_asia_dir + "_" + v_lon_dir
    else // NY2
        ctx := v_asia_dir + "_" + v_lon_dir + "_" + v_ny1_dir

    // Determine outcome
    string out = i_outcome
    if out == "Auto"
        string dev_dir = target == "Asia" ? v_asia_dir : target == "London" ? v_lon_dir : target == "NY1" ? v_ny1_dir : "N"
        out := dev_dir == "L" ? "Long True" : dev_dir == "S" ? "Short True" : "Long True"

    string out_s = out == "Long True" ? "LT" : out == "Long False" ? "LF" : out == "Short True" ? "ST" : "SF"

    // Hierarchical Lookup
    string key_l1 = target + "_" + ctx + "_" + out_s
    string packed = models.get(key_l1)

    // Level 2 fallback: single predecessor
    string used_key = key_l1
    if na(packed)
        // Use last element of context as single predecessor
        string last_dir = target == "Asia" ? v_prev_ny2_dir : target == "London" ? v_asia_dir : target == "NY1" ? v_lon_dir : v_ny1_dir
        string key_l2 = target + "_F_" + last_dir + "_" + out_s
        packed := models.get(key_l2)
        used_key := key_l2

    // Level 3 fallback: baseline
    if na(packed)
        string key_l3 = target + "_B_" + out_s
        packed := models.get(key_l3)
        used_key := key_l3

    // Draw
    if not na(packed)
        string[] points = str.split(packed, ",")
        pts_h = array.new<chart.point>()
        pts_l = array.new<chart.point>()

        // Base price = session open
        float base = target == "NY1" ? v_ny1_open : target == "NY2" ? v_ny2_open : target == "London" ? v_lon_open : v_asia_open
        if na(base)
            base := v_asia_open

        // Time base = day start (18:00)
        int ts_start = na(time[bar_index - v_day_bi]) ? time : time[bar_index - v_day_bi]

        // Session time offsets from 18:00 (in minutes)
        int sess_offset = target == "London" ? 510 : target == "NY1" ? 810 : target == "NY2" ? 930 : 0

        if not na(base) and not na(ts_start)
            for i = 0 to array.size(points) - 1
                string pt_str = array.get(points, i)
                string[] hl = str.split(pt_str, ":")
                if array.size(hl) >= 2
                    float h_pct = str.tonumber(array.get(hl, 0))
                    float l_pct = str.tonumber(array.get(hl, 1))

                    if not na(h_pct) and not na(l_pct)
                        int t_min = sess_offset + i * 5  // BUCKET = 5 min
                        int t_pt = ts_start + t_min * 60000

                        float p_h = base * (1.0 + h_pct * i_scale / 100.0)
                        float p_l = base * (1.0 + l_pct * i_scale / 100.0)

                        array.push(pts_h, chart.point.from_time(t_pt, p_h))
                        array.push(pts_l, chart.point.from_time(t_pt, p_l))

            polyline.delete(pm_h)
            polyline.delete(pm_l)
            if array.size(pts_h) > 1
                pm_h := polyline.new(pts_h, curved=true, line_color=c_hi, xloc=xloc.bar_time, line_width=w_line)
                pm_l := polyline.new(pts_l, curved=true, line_color=c_lo, xloc=xloc.bar_time, line_width=w_line)

    // Debug label
    if i_show_key
        label.delete(lbl_key)
        lbl_key := label.new(bar_index, high, "PM: " + used_key + "\nCtx: " + ctx, style=label.style_label_down, color=#333333CC, textcolor=color.white, size=size.small)
"""

    out_path = OUTPUT_DIR / "PriceModelIndicator.pine"
    with open(out_path, 'w', newline='\n') as f:
        f.write(code.strip())
    print(f"Generated {out_path}")


def main():
    print("=" * 60)
    print("Price Model Indicator Generator")
    print("=" * 60)

    # 1. Build cross-day context table
    ctx_table = load_context_table()

    # 2. Generate all models
    models = generate_all_models(ctx_table)

    # 3. Write Pine Script library
    write_library(models)

    # 4. Write Pine Script indicator
    write_indicator()

    print("\n✓ Generation complete!")
    print(f"  Library: {OUTPUT_DIR / 'PriceModelData.pine'}")
    print(f"  Indicator: {OUTPUT_DIR / 'PriceModelIndicator.pine'}")


if __name__ == "__main__":
    main()
