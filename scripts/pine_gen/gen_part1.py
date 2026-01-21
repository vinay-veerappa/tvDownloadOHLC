
import json
import requests
from pathlib import Path

# --- Configuration ---
DATA_DIR = Path("data")
OUT_DIR = Path("scripts/profiler") # MOVED TO SCRIPTS/PROFILER
IMPORT_BASE = "vveerappa" 
API_BASE_URL = "http://localhost:8000"

def load_json(name):
    path = DATA_DIR / name
    if not path.exists(): return {}
    with open(path, 'r') as f: return json.load(f)

def load_data(ticker="NQ1"):
    profiler = load_json(f"{ticker}_profiler.json")
    hod_lod = load_json(f"{ticker}_daily_hod_lod.json")
    touches = load_json(f"{ticker}_level_touches.json")
    return profiler, hod_lod, touches

def encode_status(status_str):
    if status_str == "Long True": return 1
    if status_str == "Long False": return 2
    if status_str == "Short True": return 3
    if status_str == "Short False": return 4
    return 0

def time_to_min(t_str):
    try:
        h, m = map(int, t_str.split(':'))
        return h * 60 + m
    except:
        return 0

def chunk_list(lst, size=500):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]

def generate_library_code(var_name, data_list, type_str="int"):
    chunks = list(chunk_list(data_list))
    functions = []
    merges = []
    for i, chunk in enumerate(chunks):
        func_name = f"_get_{var_name}_{i}" 
        chunk_str = ", ".join(map(str, chunk))
        # Ensure we don't have trailing commas or empty arrays that Pine doesn't like
        if not chunk_str: continue 
        func_def = f"{func_name}() =>\n    array.from({chunk_str})"
        functions.append(func_def)
        merges.append(f"        array.concat(arr, {func_name}())")
    
    merge_logic = "\n".join(merges)
    export_func = f"""
export get_{var_name}() =>
    var {type_str}[] arr = array.new_{type_str}(0)
    if barstate.isfirst
{merge_logic}
    arr
"""
    return "\n".join(functions) + "\n" + export_func

def fetch_price_model(ticker, outcome):
    """
    Fetch price model data from the backend API.
    Uses the filtered-price-model endpoint for consistency with web app.
    """
    payload = {
        "ticker": ticker,
        "target_session": "Daily",
        "filters": {
            "NY2": outcome
        },
        "broken_filters": {},
        "intra_state": "Any",
        "bucket_minutes": 5
    }
    
    try:
        print(f"  Fetching {outcome} model via API (5m buckets)...")
        response = requests.post(f"{API_BASE_URL}/stats/filtered-price-model", json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        # API returns median: list of {time_idx, high, low}
        median_path = data.get("median", [])
        if not median_path:
            # Fallback to NY1 if NY2 has no data
            payload["filters"] = {"NY1": outcome}
            response = requests.post(f"{API_BASE_URL}/stats/filtered-price-model", json=payload, timeout=30)
            data = response.json()
            median_path = data.get("median", [])
            
        if not median_path:
            return [], [], []
            
        times = [int(item["time_idx"]) for item in median_path]
        highs = [float(item["high"]) for item in median_path]
        lows = [float(item["low"]) for item in median_path]
        
        return times, highs, lows
    except Exception as e:
        print(f"  Error fetching {outcome} model: {e}")
        return [], [], []

def generate_price_model_libraries(ticker, data_map):
    print(f"Generating Price Model data for {ticker} (using API)...")
    
    models = {}
    outcomes = {
        'LT': 'Long True',
        'LF': 'Long False',
        'ST': 'Short True',
        'SF': 'Short False'
    }
    
    for key, status in outcomes.items():
        models[key] = fetch_price_model(ticker, status)
        
    return models

def generate_scripts(profiler, hod_lod, touches):
    if not OUT_DIR.exists():
        OUT_DIR.mkdir(parents=True, exist_ok=True)

    # --- Prepare Data ---
    data_map = {}
    for s in profiler:
        date = s.get('date')
        if not date: continue
        d_int = int(date.replace('-', ''))
        if d_int not in data_map:
            data_map[d_int] = {
                'date': d_int, 'Asia': 0, 'London': 0, 'NY1': 0, 'NY2': 0,
                'bk_Asia': 0, 'bk_London': 0, 'bk_NY1': 0, 'bk_NY2': 0,
                'hod_t': 0, 'lod_t': 0, 'hod_p': 0.0, 'lod_p': 0.0,
                't_p12h': 0, 't_p12m': 0, 't_p12l': 0, 't_asia_mid': 0, 't_lon_mid': 0
            }
        sess_name = s.get('session')
        code = encode_status(s.get('status'))
        broken = 1 if s.get('broken', False) else 0
        if sess_name in data_map[d_int]:
            data_map[d_int][sess_name] = code
            data_map[d_int][f"bk_{sess_name}"] = broken
            
    for date_str, stats in hod_lod.items():
        d_int = int(date_str.replace('-', ''))
        if d_int in data_map:
            data_map[d_int]['hod_t'] = time_to_min(stats.get('hod_time', '00:00'))
            data_map[d_int]['lod_t'] = time_to_min(stats.get('lod_time', '00:00'))
            d_open = stats.get('daily_open')
            d_high = stats.get('hod_price')
            d_low = stats.get('lod_price')
            if d_open and d_open > 0:
                data_map[d_int]['hod_p'] = round((d_high - d_open) / d_open * 100, 2)
                data_map[d_int]['lod_p'] = round((d_low - d_open) / d_open * 100, 2)

    for date_str, t_data in touches.items():
        d_int = int(date_str.replace('-', ''))
        if d_int in data_map:
            def chk(k): return 1 if t_data.get(k, {}).get('touched', False) else 0
            data_map[d_int]['t_p12h'] = chk('p12h')
            data_map[d_int]['t_p12m'] = chk('p12m')
            data_map[d_int]['t_p12l'] = chk('p12l')
            data_map[d_int]['t_asia_mid'] = chk('asia_mid')
            data_map[d_int]['t_lon_mid'] = chk('london_mid')

    dates = []
    asia, london, ny1, ny2 = [], [], [], []
    bk_asia, bk_london, bk_ny1, bk_ny2 = [], [], [], []
    hod_t, lod_t, hod_p, lod_p = [], [], [], []
    t_p12h, t_p12m, t_p12l, t_asia_mid, t_lon_mid = [], [], [], [], []
    
    for d in sorted(data_map.keys()):
        row = data_map[d]
        dates.append(row['date'])
        asia.append(row['Asia'])
        london.append(row['London'])
        ny1.append(row['NY1'])
        ny2.append(row['NY2'])
        bk_asia.append(row['bk_Asia'])
        bk_london.append(row['bk_London'])
        bk_ny1.append(row['bk_NY1'])
        bk_ny2.append(row['bk_NY2'])
        hod_t.append(row['hod_t'])
        lod_t.append(row['lod_t'])
        hod_p.append(row['hod_p'])
        lod_p.append(row['lod_p'])
        t_p12h.append(row['t_p12h'])
        t_p12m.append(row['t_p12m'])
        t_p12l.append(row['t_p12l'])
        t_asia_mid.append(row['t_asia_mid'])
        t_lon_mid.append(row['t_lon_mid'])
        
    print(f"Total History Depth: {len(dates)} days")
    
    pm_ticker = "NQ1"
    price_models = generate_price_model_libraries(pm_ticker, data_map)

    libs_def = {
        "ProfilerData_Asia":   [("dates", dates, "int"), ("asia", asia, "int")],
        "ProfilerData_London": [("london", london, "int")], 
        "ProfilerData_NY":     [("ny1", ny1, "int"), ("ny2", ny2, "int")],
        "ProfilerData_Broken": [("asia", bk_asia, "int"), ("london", bk_london, "int"), ("ny1", bk_ny1, "int"), ("ny2", bk_ny2, "int")],
        "ProfilerData_Times":  [("hod_time", hod_t, "int"), ("lod_time", lod_t, "int")],
        "ProfilerData_Levels": [("hod_pct", hod_p, "float"), ("lod_pct", lod_p, "float")],
        "ProfilerData_Touches":[
            ("p12h", t_p12h, "int"), ("p12m", t_p12m, "int"), ("p12l", t_p12l, "int"),
            ("asia_mid", t_asia_mid, "int"), ("lon_mid", t_lon_mid, "int")
        ],
        "ProfilerData_Model_LT": [("times", price_models.get('LT', ([],[],[]))[0], "int"), ("high", price_models.get('LT', ([],[],[]))[1], "float"), ("low", price_models.get('LT', ([],[],[]))[2], "float")],
        "ProfilerData_Model_LF": [("times", price_models.get('LF', ([],[],[]))[0], "int"), ("high", price_models.get('LF', ([],[],[]))[1], "float"), ("low", price_models.get('LF', ([],[],[]))[2], "float")],
        "ProfilerData_Model_ST": [("times", price_models.get('ST', ([],[],[]))[0], "int"), ("high", price_models.get('ST', ([],[],[]))[1], "float"), ("low", price_models.get('ST', ([],[],[]))[2], "float")],
        "ProfilerData_Model_SF": [("times", price_models.get('SF', ([],[],[]))[0], "int"), ("high", price_models.get('SF', ([],[],[]))[1], "float"), ("low", price_models.get('SF', ([],[],[]))[2], "float")]
    }
    
    for lib_name, fields in libs_def.items():
        fname = OUT_DIR / f"{lib_name}.pine"
        lib_header = f'// © vveerappa\n//@version=6\nlibrary("{lib_name}", overlay=true)\n'
        lib_body = []
        for (vname, vdata, vtype) in fields:
            lib_body.append(generate_library_code(vname, vdata, vtype))
        full_lib = lib_header + "\n\n".join(lib_body)
        with open(fname, "w", encoding='utf-8') as f:
            f.write(full_lib)
        print(f"Generated {fname}")

    # --- Generate Indicator ---
    imports = []
    imports.append(f"import {IMPORT_BASE}/ProfilerData_Asia/1 as LibAsia")
    imports.append(f"import {IMPORT_BASE}/ProfilerData_London/1 as LibLon")
    imports.append(f"import {IMPORT_BASE}/ProfilerData_NY/2 as LibNY")
    imports.append(f"import {IMPORT_BASE}/ProfilerData_Broken/1 as LibBroken")
    imports.append(f"import {IMPORT_BASE}/ProfilerData_Times/1 as LibTimes")
    imports.append(f"import {IMPORT_BASE}/ProfilerData_Levels/1 as LibLevels")
    imports.append(f"import {IMPORT_BASE}/ProfilerData_Touches/1 as LibTouches")
    imports.append(f"import {IMPORT_BASE}/ProfilerData_Model_LT/1 as LibModelLT")
    imports.append(f"import {IMPORT_BASE}/ProfilerData_Model_LF/1 as LibModelLF")
    imports.append(f"import {IMPORT_BASE}/ProfilerData_Model_ST/1 as LibModelST")
    imports.append(f"import {IMPORT_BASE}/ProfilerData_Model_SF/1 as LibModelSF")
