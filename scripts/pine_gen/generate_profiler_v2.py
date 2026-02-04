import json
import requests
import os
from pathlib import Path
import time

# --- Configuration ---
OUT_DIR = Path("scripts/profiler_v2")
API_BASE_URL = "http://localhost:8000"
TICKERS = ["NQ1", "ES1"]
V1_INDICATOR_PATH = Path("scripts/profiler/ProfilerIndicator.pine")
MODELS_PER_LIB = 35 # Further reduced to stay under 100k token limit in libraries

def ensure_dir(d):
    if not d.exists(): d.mkdir(parents=True, exist_ok=True)

def fetch_deep_model(ticker, filters, broken_filters):
    url = f"{API_BASE_URL}/stats/filtered-price-model"
    payload = {
        "ticker": ticker,
        "target_session": "Daily",
        "filters": filters,
        "broken_filters": broken_filters,
        "bucket_minutes": 5
    }
    try:
        res = requests.post(url, json=payload, timeout=60)
        res.raise_for_status()
        res_j = res.json()
        median = res_j.get('median', [])
        count = res_j.get('count', 0)
        if count < 5: return None
        return [round(i["high"], 4) for i in median], [round(i["low"], 4) for i in median]
    except: return None

def pack_to_csv(data):
    return ",".join([str(int(round(v * 10000.0))) for v in data])

def pack_bits(data, bits):
    packed = []
    current, count = 0, 0
    for val in data:
        current = (current * (2**bits)) + (int(val) & ((1 << bits) - 1))
        count += 1
        if count == 15:
            packed.append(current)
            current, count = 0, 0
    if count > 0: packed.append(current)
    return packed

def gen_lib_file(lib_name, models_batch):
    lines = [f'//@version=6', f'library("{lib_name}", overlay=true)', '']
    
    model_items = list(models_batch.items())
    chunk_size = 15 # Models per internal function
    
    fill_fns = []
    for i in range(0, len(model_items), chunk_size):
        idx = (i // chunk_size) + 1
        fn_name = f"f_fill_bag_{idx}"
        fill_fns.append(fn_name)
        lines.append(f"{fn_name}(string[] res) =>")
        chunk = model_items[i : i + chunk_size]
        for seq, dat in chunk:
            h_str = "_".join(map(str, seq))
            lines.append(f'    array.push(res, "{h_str}h:{dat["high"]}")')
            lines.append(f'    array.push(res, "{h_str}l:{dat["low"]}")')
        lines.append("")

    lines.append("export get_models_bag() =>")
    lines.append("    res = array.new_string(0)")
    for fn in fill_fns:
        lines.append(f"    {fn}(res)")
    lines.append("    res")
    return "\n".join(lines)

def get_state(item):
    return (item['status_code'] * 2) + (1 if item['broken'] else 0)

def process_ticker(ticker):
    print(f"Deep Processing {ticker} (Token Optimization Mode)...")
    d_dir = Path("data")
    prof_p = d_dir / f"{ticker}_profiler.json"
    with open(prof_p, 'r') as f: prof_raw = json.load(f)
    days = {}
    for entry in prof_raw:
        d = entry['date']
        if d not in days: days[d] = {}
        s, stat = entry['session'], entry['status'].lower()
        code = 1 if "long" in stat and "true" in stat else 2 if "long" in stat else 3 if "short" in stat and "true" in stat else 4 if "short" in stat else 0
        days[d][s] = {'status_code': code, 'broken': entry.get('broken', False)}
    valid_seqs = {}
    for d, sessions in days.items():
        if 'Asia' in sessions:
            a_s = get_state(sessions['Asia'])
            valid_seqs[(a_s,)] = valid_seqs.get((a_s,), 0) + 1
            if 'London' in sessions:
                l_s = get_state(sessions['London'])
                valid_seqs[(a_s, l_s)] = valid_seqs.get((a_s, l_s), 0) + 1
                if 'NY1' in sessions:
                    n_s = get_state(sessions['NY1'])
                    valid_seqs[(a_s, l_s, n_s)] = valid_seqs.get((a_s, l_s, n_s), 0) + 1
    models = {}
    sorted_seqs = sorted(valid_seqs.keys(), key=lambda x: (len(x), x))
    for seq in sorted_seqs:
        if valid_seqs[seq] < 5: continue
        f_map, b_map = {}, {}
        for i, s_val in enumerate(seq):
            sess_name = 'Asia' if i==0 else 'London' if i==1 else 'NY1'
            f_code = s_val // 2
            b_val = (s_val % 2) == 1
            f_name = 'Long True' if f_code==1 else 'Long False' if f_code==2 else 'Short True' if f_code==3 else 'Short False' if f_code==4 else 'Neutral'
            if f_code > 0: f_map[sess_name] = f_name
            if b_val: b_map[sess_name] = 'Broken'
        res = fetch_deep_model(ticker, f_map, b_map)
        if res: models[seq] = {'high': pack_to_csv(res[0]), 'low': pack_to_csv(res[1])}
    parts = []
    current_models = list(models.items())
    for i in range(0, len(current_models), MODELS_PER_LIB):
        batch = dict(current_models[i : i + MODELS_PER_LIB])
        lib_idx = (i // MODELS_PER_LIB) + 1
        lib_name = f"ProfilerDeepModels_{ticker}_P{lib_idx}"
        with open(OUT_DIR / f"{lib_name}.pine", 'w', encoding='utf-8') as f: f.write(gen_lib_file(lib_name, batch))
        parts.append({'name': lib_name, 'count': len(batch)})
    print(f"  Packed {len(models)} models into {len(parts)} bags for {ticker}")
    return parts

def generate_ticker_indicators(tickers, ticker_part_maps):
    t_map = {"NQ1": "NQ", "ES1": "ES"}
    
    for current_ticker in tickers:
        lines = [f'//@version=6', f'indicator("VxV Profiler V2 ({current_ticker})", overlay=true, max_boxes_count=500, max_lines_count=500, max_labels_count=500)', 'max_bars_back(time, 2000)', '']
        
        t_root = t_map[current_ticker]
        
        # Imports for THIS ticker only
        lines.append(f"import vveerappa/ProfilerDataV2_{current_ticker}_Asia/1 as Lib_{t_root}_Asia")
        lines.append(f"import vveerappa/ProfilerDataV2_{current_ticker}_London/1 as Lib_{t_root}_London")
        lines.append(f"import vveerappa/ProfilerDataV2_{current_ticker}_NY1/1 as Lib_{t_root}_NY1")
        lines.append(f"import vveerappa/ProfilerDataV2_{current_ticker}_NY2/1 as Lib_{t_root}_NY2")
        for i in range(1, len(ticker_part_maps[current_ticker]) + 1):
            lines.append(f"import vveerappa/ProfilerDeepModels_{current_ticker}_P{i}/1 as Lib_{t_root}_P{i}")
        lines.append("")

        lines += ["f_get_root() =>", f'    "{t_root}"', ""]
        
        def gen_fn(fn_name, target_lib_suffix, call, ret_type="int[]"):
            lines.append(f"{fn_name}() =>")
            lines.append(f"    Lib_{t_root}_{target_lib_suffix}.{call}")
            lines.append("")

        gen_fn('f_get_dates', 'Asia', 'get_dates()')
        gen_fn('f_get_hod_time', 'Asia', 'get_hod_t()')
        gen_fn('f_get_lod_time', 'Asia', 'get_lod_t()')
        for sn in ['Asia', 'London', 'NY1', 'NY2']:
            for f in ['status', 'broken']: gen_fn(f'f_get_{f}_{sn.lower()}', sn, f'get_{f}()')
            for f in ['hp', 'lp']: gen_fn(f'f_get_{f}_{sn.lower()}', sn, f'get_{f}()', "float[]")
        
        lvls = ["pdh","pdl","pdm","p12h","p12m","p12l","asia_mid","london_mid","ny1_mid","midnight_open","open_0730"]
        for sn in ['Asia', 'London', 'NY1', 'NY2']:
            for lvl in lvls: gen_fn(f'f_get_tch_{sn.lower()}_{lvl}', sn, f'get_tch_{lvl}()')

        lines += ["f_unpack_csv(csv) =>", "    res = array.new_float(0)", "    parts = str.split(csv, ',')", "    for p in parts", "        array.push(res, str.tonumber(p) / 10000.0)", "    res", ""]
        
        # Deep Model Fetcher for THIS ticker
        lines += ["f_get_deep_model(root, a_s, l_s, n_s, is_high) =>", "    float[] res = array.new_float(0)"]
        for level in [3, 2, 1]:
            lines += [f'    if array.size(res) == 0']
            h_str = 'str.tostring(a_s) + "_" + str.tostring(l_s) + "_" + str.tostring(n_s)' if level==3 else 'str.tostring(a_s) + "_" + str.tostring(l_s)' if level==2 else 'str.tostring(a_s)'
            lines += [f'        target_key = ({h_str}) + (is_high ? "h:" : "l:")', f'        full_bags = array.new_string(0)']
            for i in range(1, len(ticker_part_maps[current_ticker]) + 1): 
                lines += [f'        array.concat(full_bags, Lib_{t_root}_P{i}.get_models_bag())']
            lines += [f'        for item in full_bags', f'            if str.startswith(item, target_key)', f'                res := f_unpack_csv(str.replace(item, target_key, ""))', '                break']
        lines += ["    res", ""]

        with open(V1_INDICATOR_PATH, 'r') as f: v1_lines = f.readlines()
        sl = 0
        for i, l in enumerate(v1_lines):
            if "type ModeRange" in l: sl = i; break
        v1_content = "".join(v1_lines[sl:])
        
        root_header = "root = f_get_root()\nvar int[] dates = f_get_dates()\n"
        root_header += "var int[] asia_stats = f_get_status_asia(), var int[] lon_stats = f_get_status_london(), var int[] ny1_stats = f_get_status_ny1(), var int[] ny2_stats = f_get_status_ny2()\n"
        root_header += "var int[] asia_bk = f_get_broken_asia(), var int[] lon_bk = f_get_broken_london(), var int[] ny1_bk = f_get_broken_ny1(), var int[] ny2_bk = f_get_broken_ny2()\n"
        root_header += "var float[] asia_hp = f_get_hp_asia(), var float[] asia_lp = f_get_lp_asia(), var float[] lon_hp = f_get_hp_london(), var float[] lon_lp = f_get_lp_london()\n"
        root_header += "var float[] n1_hp = f_get_hp_ny1(), var float[] n1_lp = f_get_lp_ny1(), var float[] n2_hp = f_get_hp_ny2(), var float[] n2_lp = f_get_lp_ny2()\n"
        
        for s in ['asia', 'london', 'ny1', 'ny2']:
            for lvl in lvls: v1_content = v1_content.replace(f"LibTouches.get_{lvl}_{s}()", f"f_get_tch_{s}_{lvl}()")
        v1_content = v1_content.replace("LibTimes.get_hod_time()", "f_get_hod_time()").replace("LibTimes.get_lod_time()", "f_get_lod_time()")
        v1_content = v1_content.replace("LibLevels.get_hod_pct()", "f_get_hp_asia()").replace("LibLevels.get_lod_pct()", "f_get_lp_asia()")

        lines.append(root_header + v1_content)
        
        mod_inject = """
// ---------------- FUNCTIONS ----------------
f_sync_deep_models(root, st_asia, bk_asia, st_lon, bk_lon, st_ny1, bk_ny1) =>
    a_s = (st_asia * 2) + (bk_asia ? 1 : 0)
    l_s = (st_lon * 2) + (bk_lon ? 1 : 0)
    n_s = (st_ny1 * 2) + (bk_ny1 ? 1 : 0)
    [f_get_deep_model(root, a_s, l_s, n_s, true), f_get_deep_model(root, a_s, l_s, n_s, false)]

// ---------------- MAIN EXECUTION ----------------
if barstate.islast
    [m_curr_h, m_curr_l] = f_sync_deep_models(root, st_asia, bk_asia, st_lon, bk_lon, st_ny1, bk_ny1)
    if array.size(m_curr_h) > 0
        array.copy(m_lt_h, m_curr_h)
        array.copy(m_lt_l, m_curr_l)
"""
        lines.append(mod_inject) # Append the mod_inject content to lines
        
        combined = "\n".join(lines)
        combined = combined.replace("var float[] m_lt_h = LibModelLT.get_high()", "var float[] m_lt_h = array.new_float(0)")
        combined = combined.replace("var float[] m_lt_l = LibModelLT.get_low()", "var float[] m_lt_l = array.new_float(0)")
        combined = combined.replace("var int[] m_lt_t = LibModelLT.get_times()", "var int[] m_lt_t = f_get_hod_time()")
        
        out_fn = f"VxV_Profiler_V2_{current_ticker}.pine"
        with open(OUT_DIR / out_fn, 'w', encoding='utf-8') as f: f.write(combined)
        print(f"Generated Ticker Indicator: {out_fn}")

if __name__ == "__main__":
    ensure_dir(OUT_DIR)
    maps = {}
    for t in TICKERS: maps[t] = process_ticker(t)
    generate_ticker_indicators(TICKERS, maps)
