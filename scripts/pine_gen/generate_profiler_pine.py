import json
import requests
from pathlib import Path
from datetime import datetime

# --- Configuration ---
OUT_DIR = Path("scripts/profiler")
IMPORT_BASE = "vveerappa/ProfilerData"
API_BASE_URL = "http://localhost:8000" # Update if different

def time_to_min(t_str):
    if not t_str or ":" not in t_str: return 0
    h, m = map(int, t_str.split(':'))
    return h * 60 + m

# Session Time Ranges (ET) - Start (inclusive), End (exclusive)
SESSION_RANGES = {
    'Asia': ('18:00', '02:00'),
    'London': ('02:00', '07:00'),
    'NY1': ('08:00', '12:00'),
    'NY2': ('12:00', '16:00'),
}

def time_in_session(t_str, session):
    """Check if time HH:MM falls within session range (handles midnight crossing)."""
    if not t_str or session not in SESSION_RANGES:
        return False
    
    start_str, end_str = SESSION_RANGES[session]
    
    h, m = map(int, t_str.split(':'))
    t = h * 60 + m
    
    sh, sm = map(int, start_str.split(':'))
    s = sh * 60 + sm
    
    eh, em = map(int, end_str.split(':'))
    e_raw = eh * 60 + em
    
    # Handle midnight crossing (e.g. 18:00 -> 02:00)
    if e_raw < s:
        e = e_raw + 24 * 60
        if t < s:
            t += 24 * 60
    else:
        e = e_raw
    
    return s <= t < e

def touched_in_session(touch_times, session):
    """Check if any touch time falls within the session."""
    if not touch_times:
        return 0
    for ts in touch_times:
        if time_in_session(ts, session):
            return 1
    return 0

def encode_status(status):
    if not status: return 0
    s = status.lower()
    if "long" in s: return 1 if "true" in s else 2
    if "short" in s: return 3 if "true" in s else 4
    return 0

def load_data(ticker):
    fname_prof = Path(f"data/{ticker}_profiler.json")
    fname_hl = Path(f"data/{ticker}_daily_hod_lod.json")
    fname_touch = Path(f"data/{ticker}_level_touches.json")
    
    prof, hl, touch = [], {}, {}
    if fname_prof.exists():
        with open(fname_prof, "r") as f: prof = json.load(f)
    if fname_hl.exists():
        with open(fname_hl, "r") as f: hl = json.load(f)
    if fname_touch.exists():
        with open(fname_touch, "r") as f: touch = json.load(f)
    return prof, hl, touch

def fetch_price_model(ticker, outcome, bucket_minutes=5):
    """Fetch price model data from the backend API."""
    url = f"{API_BASE_URL}/stats/filtered-price-model"
    # Map outcomes to API filters
    # Outcomes: Long True, Long False, Short True, Short False
    # API outcomes: 1, 2, 3, 4
    outcome_map = {
        "Long True": 1,
        "Long False": 2,
        "Short True": 3,
        "Short False": 4
    }
    
    payload = {
        "ticker": ticker,
        "session": "NY2", # Use NY2 as it has the full context
        "outcome": outcome_map.get(outcome, 1),
        "bucket_minutes": bucket_minutes
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Extract median path
        median_list = data.get("median", [])
        times, highs, lows = [], [], []
        
        for item in median_list:
            t_str = item.get("time", "00:00")
            h_val = item.get("high", 0.0)
            l_val = item.get("low", 0.0)
            
            h, m = map(int, t_str.split(':'))
            total_m = h * 60 + m
            
            # Adjust for 18:00 start (Globex)
            if total_m >= 1080:
                rel_m = total_m - 1080
            else:
                rel_m = total_m + (1440 - 1080)
            
            times.append(rel_m)
            highs.append(round(h_val, 3))
            lows.append(round(l_val, 3))
            
        return times, highs, lows
    except Exception as e:
        print(f"Error fetching price model for {outcome}: {e}")
        return [], [], []

def generate_price_model_libraries(ticker, data_map):
    outcomes = ["Long True", "Long False", "Short True", "Short False"]
    models = {}
    for out in outcomes:
        print(f"  Fetching {out} model...")
        short_key = "".join([w[0] for w in out.split()]).upper() # LT, LF, ST, SF
        models[short_key] = fetch_price_model(ticker, out)
    return models

def pack_bits(data, bits):
    """Packs multiple values into 50-bit integers (safe for Pine Script float math)."""
    vals_per_int = 15
    packed = []
    current = 0
    count = 0
    for val in data:
        current = (current * (2**bits)) + (int(val) & ((1 << bits) - 1))
        count += 1
        if count == vals_per_int:
            packed.append(current)
            current = 0
            count = 0
    if count > 0:
        packed.append(current)
    return packed

def generate_library_code(vname, vdata, vtype, bits=0):
    if bits > 0:
        vdata = pack_bits(vdata, bits)
        
    chunk_size = 2000
    chunks = [vdata[i:i + chunk_size] for i in range(0, len(vdata), chunk_size)]
    code = []
    
    # Helper functions for each chunk
    for i, chunk in enumerate(chunks):
        vals = ",".join(map(str, chunk))
        code.append(f"_get_{vname}_{i}() =>\n    array.from({vals})")
        
    # Main export function
    code.append(f"export get_{vname}() =>")
    init_type = "array.new_int(0)" if vtype == "int" else "array.new_float(0)"
    arr_type = "int[]" if vtype == "int" else "float[]"
    
    code.append(f"    var {arr_type} arr = {init_type}")
    code.append(f"    if barstate.isfirst")
    for i in range(len(chunks)):
        code.append(f"        array.concat(arr, _get_{vname}_{i}())")
    code.append(f"    arr")
    
    return "\n".join(code)

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
        if not date_str[0].isdigit(): continue # Skip "daily" etc
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
            # Store absolute high/low for PDH/PDL calc
            data_map[d_int]['high_abs'] = d_high
            data_map[d_int]['low_abs'] = d_low

    # Levels to process for session-specific touches
    TOUCH_LEVELS = ['p12h', 'p12m', 'p12l', 'pdh', 'pdm', 'pdl', 
                    'asia_mid', 'london_mid', 'ny1_mid', 'midnight_open', 'open_0730']
    SESSIONS = ['Asia', 'London', 'NY1', 'NY2']
    
    for date_str, t_data in touches.items():
        if not date_str[0].isdigit(): continue
        d_int = int(date_str.replace('-', ''))
        if d_int in data_map:
            # Store touch_times for session-specific calculation
            for lvl in TOUCH_LEVELS:
                lvl_data = t_data.get(lvl, {})
                touch_times = lvl_data.get('touch_times', [])
                
                # Calculate session-specific touches
                for sess in SESSIONS:
                    key = f't_{lvl}_{sess.lower()}'
                    data_map[d_int][key] = touched_in_session(touch_times, sess)
                
                # Also store daily touch for backward compatibility
                data_map[d_int][f't_{lvl}'] = 1 if lvl_data.get('touched', False) else 0



    dates = []
    asia, london, ny1, ny2 = [], [], [], []
    bk_asia, bk_london, bk_ny1, bk_ny2 = [], [], [], []
    hod_t, lod_t, hod_p, lod_p = [], [], [], []
    
    # Session-specific touch arrays: level_session
    touch_arrays = {}
    for lvl in TOUCH_LEVELS:
        for sess in ['asia', 'london', 'ny1', 'ny2']:
            touch_arrays[f'{lvl}_{sess}'] = []
    
    # Sort dates and build arrays
    sorted_days = sorted(data_map.keys())
    
    for d in sorted_days:
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
        
        # Append session-specific touches
        for lvl in TOUCH_LEVELS:
            for sess in ['asia', 'london', 'ny1', 'ny2']:
                key = f't_{lvl}_{sess}'
                touch_arrays[f'{lvl}_{sess}'].append(row.get(key, 0))
        
    pm_ticker = "NQ1"
    price_models = generate_price_model_libraries(pm_ticker, data_map)

    # Build Touches library definition with session-indexed arrays
    touches_fields = []
    for lvl in TOUCH_LEVELS:
        for sess in ['asia', 'london', 'ny1', 'ny2']:
            arr_name = f'{lvl}_{sess}'
            touches_fields.append((arr_name, touch_arrays[arr_name], "int"))

    libs_def = {
        "ProfilerData_Asia":   [("dates", dates, "int", 0), ("asia", asia, "int", 3)],
        "ProfilerData_London": [("london", london, "int", 3)], 
        "ProfilerData_NY":     [("ny1", ny1, "int", 3), ("ny2", ny2, "int", 3)],
        "ProfilerData_Broken": [("asia", bk_asia, "int", 1), ("london", bk_london, "int", 1), ("ny1", bk_ny1, "int", 1), ("ny2", bk_ny2, "int", 1)],
        "ProfilerData_Times":  [("hod_time", hod_t, "int", 0), ("lod_time", lod_t, "int", 0)],
        "ProfilerData_Levels": [("hod_pct", hod_p, "float", 0), ("lod_pct", lod_p, "float", 0)],
        "ProfilerData_Touches": touches_fields,
        "ProfilerData_Model_LT": [("times", price_models.get('LT', ([],[],[]))[0], "int", 0), ("high", price_models.get('LT', ([],[],[]))[1], "float", 0), ("low", price_models.get('LT', ([],[],[]))[2], "float", 0)],
        "ProfilerData_Model_LF": [("times", price_models.get('LF', ([],[],[]))[0], "int", 0), ("high", price_models.get('LF', ([],[],[]))[1], "float", 0), ("low", price_models.get('LF', ([],[],[]))[2], "float", 0)],
        "ProfilerData_Model_ST": [("times", price_models.get('ST', ([],[],[]))[0], "int", 0), ("high", price_models.get('ST', ([],[],[]))[1], "float", 0), ("low", price_models.get('ST', ([],[],[]))[2], "float", 0)],
        "ProfilerData_Model_SF": [("times", price_models.get('SF', ([],[],[]))[0], "int", 0), ("high", price_models.get('SF', ([],[],[]))[1], "float", 0), ("low", price_models.get('SF', ([],[],[]))[2], "float", 0)]
    }

    # Update touches_fields to include bit-packing flag (1 bit)
    for i in range(len(touches_fields)):
        touches_fields[i] = list(touches_fields[i]) + [1]

    
    for lib_name, fields in libs_def.items():
        fname = OUT_DIR / f"{lib_name}.pine"
        lib_header = f'// © vveerappa\n//@version=6\nlibrary("{lib_name}", overlay=true)\n'
        lib_body = []
        for (vname, vdata, vtype, vbits) in fields:
            lib_body.append(generate_library_code(vname, vdata, vtype, vbits))
        full_lib = lib_header + "\n\n".join(lib_body)
        with open(fname, "w", encoding='utf-8') as f:
            f.write(full_lib)
        print(f"Generated {fname}")

    # --- Generate Indicator ---
    imports = []
    imports.append(f"import {IMPORT_BASE}_Asia/3 as LibAsia")
    imports.append(f"import {IMPORT_BASE}_London/3 as LibLon")
    imports.append(f"import {IMPORT_BASE}_NY/4 as LibNY")
    imports.append(f"import {IMPORT_BASE}_Broken/3 as LibBroken")
    imports.append(f"import {IMPORT_BASE}_Times/1 as LibTimes")
    imports.append(f"import {IMPORT_BASE}_Levels/1 as LibLevels")
    imports.append(f"import {IMPORT_BASE}_Touches/4 as LibTouches")
    imports.append(f"import {IMPORT_BASE}_Model_LT/3 as LibModelLT")
    imports.append(f"import {IMPORT_BASE}_Model_LF/3 as LibModelLF")
    imports.append(f"import {IMPORT_BASE}_Model_ST/3 as LibModelST")
    imports.append(f"import {IMPORT_BASE}_Model_SF/3 as LibModelSF")

    ind_header = f"""// © vveerappa
//@version=6
// 
// Daily Profiler [Semantic]
// 
// Based on the statistical analysis framework developed by:
//   • Pack Trade Group
//   • The Daily Profiler (https://thedailyprofiler.com/)
// 
// This indicator tracks session outcomes and calculates conditional
// probabilities based on historical data matching current market trajectory.
// 
// Credits:
//   Original Concepts: Pack Trade Group & The Daily Profiler
//   Pine Script Implementation: vveerappa
// 
indicator("Daily Profiler [VxV]", overlay=true, max_boxes_count=500, max_lines_count=500, max_labels_count=500)
max_bars_back(time, 2000)

{chr(10).join(imports)}

f_get_bit(arr, i) =>
    val = array.get(arr, math.floor(i / 15))
    pos = 14 - (i % 15)
    math.floor(val / math.pow(2, pos)) % 2

f_get_code(arr, i) =>
    val = array.get(arr, math.floor(i / 15))
    pos = 14 - (i % 15)
    math.floor(val / math.pow(8, pos)) % 8

// ————— LOAD DATA —————
var int[] dates = LibAsia.get_dates()
var int[] asia_stats = LibAsia.get_asia()
var int[] london_stats = LibLon.get_london()
var int[] ny1_stats = LibNY.get_ny1()
var int[] ny2_stats = LibNY.get_ny2()
var int[] asia_bk = LibBroken.get_asia()
var int[] london_bk = LibBroken.get_london()
var int[] ny1_bk = LibBroken.get_ny1()
var int[] ny2_bk = LibBroken.get_ny2()
// Load Data Arrays

var int[] m_lt_t = LibModelLT.get_times()
var float[] m_lt_h = LibModelLT.get_high()
var float[] m_lt_l = LibModelLT.get_low()
var int[] m_lf_t = LibModelLF.get_times()
var float[] m_lf_h = LibModelLF.get_high()
var float[] m_lf_l = LibModelLF.get_low()
var int[] m_st_t = LibModelST.get_times()
var float[] m_st_h = LibModelST.get_high()
var float[] m_st_l = LibModelST.get_low()
var int[] m_sf_t = LibModelSF.get_times()
var float[] m_sf_h = LibModelSF.get_high()
var float[] m_sf_l = LibModelSF.get_low()

type ModeRange
    string disp
    float min_val
    float max_val
    bool valid
"""

    ind_body = """
// ————— INPUTS —————
grp_theme = "🎨 Theme"
theme_sel = input.string("Dark Pro", "Color Theme", options=["Default", "Dark Pro", "Light Pro", "Neon"], group=grp_theme)

f_theme_asia_box() => theme_sel == "Dark Pro" ? color.new(#1E88E5, 85) : theme_sel == "Light Pro" ? color.new(#90CAF9, 85) : theme_sel == "Neon" ? color.new(#00BCD4, 85) : color.new(color.blue, 90)
f_theme_asia_bor() => theme_sel == "Dark Pro" ? color.new(#42A5F5, 40) : theme_sel == "Light Pro" ? color.new(#1976D2, 40) : theme_sel == "Neon" ? color.new(#00E5FF, 20) : color.new(color.blue, 50)
f_theme_lon_box() => theme_sel == "Dark Pro" ? color.new(#E53935, 85) : theme_sel == "Light Pro" ? color.new(#EF9A9A, 85) : theme_sel == "Neon" ? color.new(#FF1744, 85) : color.new(color.red, 90)
f_theme_lon_bor() => theme_sel == "Dark Pro" ? color.new(#EF5350, 40) : theme_sel == "Light Pro" ? color.new(#C62828, 40) : theme_sel == "Neon" ? color.new(#FF5252, 20) : color.new(color.red, 50)
f_theme_ny1_box() => theme_sel == "Dark Pro" ? color.new(#FB8C00, 85) : theme_sel == "Light Pro" ? color.new(#FFCC80, 85) : theme_sel == "Neon" ? color.new(#FF9100, 85) : color.new(color.orange, 90)
f_theme_ny1_bor() => theme_sel == "Dark Pro" ? color.new(#FFA726, 40) : theme_sel == "Light Pro" ? color.new(#E65100, 40) : theme_sel == "Neon" ? color.new(#FFAB40, 20) : color.new(color.orange, 50)
f_theme_ny2_box() => theme_sel == "Dark Pro" ? color.new(#8E24AA, 85) : theme_sel == "Light Pro" ? color.new(#CE93D8, 85) : theme_sel == "Neon" ? color.new(#EA80FC, 85) : color.new(color.purple, 90)
f_theme_ny2_bor() => theme_sel == "Dark Pro" ? color.new(#AB47BC, 40) : theme_sel == "Light Pro" ? color.new(#6A1B9A, 40) : theme_sel == "Neon" ? color.new(#E040FB, 20) : color.new(color.purple, 50)
f_theme_p12() => theme_sel == "Dark Pro" ? #FFD54F : theme_sel == "Light Pro" ? #F9A825 : theme_sel == "Neon" ? #FFEA00 : color.rgb(255, 235, 59)
f_theme_pd() => theme_sel == "Dark Pro" ? #9E9E9E : theme_sel == "Light Pro" ? #616161 : theme_sel == "Neon" ? #B0BEC5 : color.gray
f_theme_open() => theme_sel == "Dark Pro" ? #E0E0E0 : theme_sel == "Light Pro" ? #424242 : theme_sel == "Neon" ? #FFFFFF : color.white
f_theme_weekly() => theme_sel == "Dark Pro" ? #66BB6A : theme_sel == "Light Pro" ? #2E7D32 : theme_sel == "Neon" ? #00E676 : color.rgb(76, 175, 80)
f_theme_settle() => theme_sel == "Dark Pro" ? #FFA726 : theme_sel == "Light Pro" ? #E65100 : theme_sel == "Neon" ? #FF6D00 : color.rgb(255, 152, 0)

grp_tbl = "Table Settings"
p_res = input.string("Bottom Right", "Result Table Position", options=["Top Right", "Top Left", "Bottom Right", "Bottom Left", "Middle Right"], group=grp_tbl)
s_res = input.string("Tiny", "Result Table Size", options=["Tiny", "Small", "Normal", "Large"], group=grp_tbl)
p_stat = input.string("Middle Right", "Status Table Position", options=["Top Right", "Top Left", "Bottom Right", "Bottom Left", "Middle Right"], group=grp_tbl)

grp_box = "Prediction Visuals"
show_boxes = input.bool(true, "Show Prediction Boxes", group=grp_box)
c_box_long  = input.color(color.new(color.green, 60), "Long Box Color", group=grp_box)
c_box_short = input.color(color.new(color.red, 60), "Short Box Color", group=grp_box)
c_box_false = input.color(color.new(color.gray, 60), "False/Neutral Box Color", group=grp_box)
t_box_fill  = input.int(60, "Box Fill Transparency (0-100)", minval=0, maxval=100, group=grp_box)
show_labels = input.bool(true, "Show Labels", group=grp_box)
c_lbl_text  = input.color(color.white, "Label Text Color", group=grp_box)
s_lbl       = input.string("Tiny", "Label Size", options=["Tiny", "Small", "Normal", "Large"], group=grp_box)

grp_ref = "Reference Levels"
show_p12     = input.bool(true, "Show P12 (High/Mid/Low)", group=grp_ref)
show_pd      = input.bool(true, "Show PDH/PDL/PDM", group=grp_ref)
show_open    = input.bool(true, "Show Opens (Globex, Mid, 7:30)", group=grp_ref)
show_weekly  = input.bool(true, "Show Weekly Close", group=grp_ref)
show_settle  = input.bool(true, "Show Prior Settlement", group=grp_ref)
show_ref_lbl = input.bool(true, "Show Labels", group=grp_ref)
line_ext_bars = input.int(20, "Line Extension (bars)", minval=1, maxval=100, group=grp_ref)

grp_pm = "Price Models"
show_pm     = input.bool(true, "Show Price Models", group=grp_pm)
pm_outcome  = input.string("Auto", "Outcome Model", options=["Auto", "Long True", "Long False", "Short True", "Short False"], group=grp_pm)
pm_anchor   = input.string("Prev Mid", "Anchor To", options=["Session Open", "Prev Mid"], group=grp_pm)
pm_opacity  = input.int(50, "Opacity (0-100)", minval=0, maxval=100, group=grp_pm)
c_pm_high   = input.color(color.green, "Model High Color", group=grp_pm)
c_pm_low    = input.color(color.red, "Model Low Color", group=grp_pm)

grp_hist = "Time Histograms"
hist_outcome = input.string("None", "Show Histogram For", options=["None", "Long True", "Long False", "Short True", "Short False"], group=grp_hist)
hist_scale   = input.float(0.5, "Histogram Height Scale", step=0.1, group=grp_hist)
hist_disp    = input.float(0.5, "Histogram Y Displacement (%)", step=0.1, group=grp_hist)

get_pos(str) => str == "Top Right" ? position.top_right : str == "Top Left" ? position.top_left : str == "Bottom Right" ? position.bottom_right : str == "Bottom Left" ? position.bottom_left : position.middle_right
get_size(str) => str == "Tiny" ? size.tiny : str == "Small" ? size.small : str == "Large" ? size.large : size.normal

f_draw_lev_bar(price, start_bi, col, style, txt, visible) =>
    if visible and not na(price) and start_bi > 0 and (bar_index - start_bi) < 500
        end_bi = bar_index + line_ext_bars
        line.new(start_bi, price, end_bi, price, xloc=xloc.bar_index, color=col, style=style)
        if show_ref_lbl
            label.new(end_bi, price, txt, xloc=xloc.bar_index, yloc=yloc.price, style=label.style_none, textcolor=col, size=size.small, textalign=text.align_left)

// ————— LIVE SESSION LOGIC —————
t_asia = "1800-1929", t_lon = "0230-0329", t_ny1 = "0730-0829", t_ny2 = "1130-1229"
s_asia = "1930-0229", s_lon = "0330-0729", s_ny1 = "0830-1129", s_ny2 = "1230-1659"
bw_asia = "0230-1700:1234567", bw_lon  = "0730-1700:1234567", bw_ny1  = "1130-1700:1234567", bw_ny2  = "1600-1700:1234567"

var float asia_h = na, var float asia_l = na, var float lon_h = na, var float lon_l = na, var float ny1_h = na, var float ny1_l = na, var float ny2_h = na, var float ny2_l = na
var int st_asia = 0, var int st_lon = 0, var int st_ny1 = 0, var int st_ny2 = 0
var bool bk_asia = false, var bool bk_lon = false, var bool bk_ny1 = false, var bool bk_ny2 = false
var float open_asia = na, var float open_lon = na, var float open_ny = na

f_update_sess(_sess) =>
    in_s = not na(time(timeframe.period, _sess + ":1234567", "America/New_York"))
    [in_s, in_s and not in_s[1]]

f_get_1600_et(start_time) =>
    y = year(start_time, "America/New_York"), m = month(start_time, "America/New_York"), d = dayofmonth(start_time, "America/New_York"), h = hour(start_time, "America/New_York")
    day_shift = (h >= 17) ? 1 : 0
    timestamp("America/New_York", y, m, d + day_shift, 16, 0, 0)

[in_asia, start_asia] = f_update_sess(t_asia)
[in_lon, start_lon]   = f_update_sess(t_lon)
[in_ny1, start_ny1]   = f_update_sess(t_ny1)
[in_ny2, start_ny2]   = f_update_sess(t_ny2)

var box b_asia = na, var line l_asia_mid = na, var label lb_asia_mid = na, var int asia_start_bi = 0
if start_asia
    box.delete(b_asia)
    line.delete(l_asia_mid)
    label.delete(lb_asia_mid)
    asia_h := high
    asia_l := low
    st_asia := 0
    bk_asia := false
    st_lon := 0
    bk_lon := false
    st_ny1 := 0
    bk_ny1 := false
    st_ny2 := 0
    bk_ny2 := false
    asia_start_bi := bar_index
    open_asia := open
    b_asia := box.new(time, high, time, low, xloc=xloc.bar_time, border_color=f_theme_asia_bor(), bgcolor=f_theme_asia_box())
    t_close = f_get_1600_et(time)
    l_asia_mid := line.new(time, high, t_close, high, xloc=xloc.bar_time, color=f_theme_asia_bor(), style=line.style_dotted)
    if show_ref_lbl
        lb_asia_mid := label.new(t_close, high, "Asia Mid", xloc=xloc.bar_time, style=label.style_none, textcolor=f_theme_asia_bor(), size=size.small, textalign=text.align_left)
if in_asia
    asia_h := math.max(nz(asia_h, high), high)
    asia_l := math.min(nz(asia_l, low), low)
    box.set_top(b_asia, asia_h)
    box.set_bottom(b_asia, asia_l)
    box.set_right(b_asia, time)
    mid = (asia_h + asia_l) / 2
    line.set_y1(l_asia_mid, mid)
    line.set_y2(l_asia_mid, mid)
    if not na(lb_asia_mid)
        label.set_y(lb_asia_mid, mid)

var box b_lon = na, var line l_lon_mid = na, var label lb_lon_mid = na
if start_lon
    box.delete(b_lon)
    line.delete(l_lon_mid)
    label.delete(lb_lon_mid)
    lon_h := high
    lon_l := low
    st_lon := 0
    bk_lon := false
    open_lon := open
    b_lon := box.new(time, high, time, low, xloc=xloc.bar_time, border_color=f_theme_lon_bor(), bgcolor=f_theme_lon_box())
    t_close = f_get_1600_et(time)
    l_lon_mid := line.new(time, high, t_close, high, xloc=xloc.bar_time, color=f_theme_lon_bor(), style=line.style_dotted)
    if show_ref_lbl
        lb_lon_mid := label.new(t_close, high, "Lon Mid", xloc=xloc.bar_time, style=label.style_none, textcolor=f_theme_lon_bor(), size=size.small, textalign=text.align_left)
if in_lon
    lon_h := math.max(nz(lon_h, high), high)
    lon_l := math.min(nz(lon_l, low), low)
    box.set_top(b_lon, lon_h)
    box.set_bottom(b_lon, lon_l)
    box.set_right(b_lon, time)
    mid = (lon_h + lon_l) / 2
    line.set_y1(l_lon_mid, mid)
    line.set_y2(l_lon_mid, mid)
    if not na(lb_lon_mid)
        label.set_y(lb_lon_mid, mid)

var box b_ny1 = na, var line l_ny1_mid = na, var label lb_ny1_mid = na
if start_ny1
    box.delete(b_ny1)
    line.delete(l_ny1_mid)
    label.delete(lb_ny1_mid)
    ny1_h := high
    ny1_l := low
    st_ny1 := 0
    bk_ny1 := false
    open_ny := open
    b_ny1 := box.new(time, high, time, low, xloc=xloc.bar_time, border_color=f_theme_ny1_bor(), bgcolor=f_theme_ny1_box())
    t_close = f_get_1600_et(time)
    l_ny1_mid := line.new(time, high, t_close, high, xloc=xloc.bar_time, color=f_theme_ny1_bor(), style=line.style_dotted)
    if show_ref_lbl
        lb_ny1_mid := label.new(t_close, high, "NY1 Mid", xloc=xloc.bar_time, style=label.style_none, textcolor=f_theme_ny1_bor(), size=size.small, textalign=text.align_left)
if in_ny1
    ny1_h := math.max(nz(ny1_h, high), high)
    ny1_l := math.min(nz(ny1_l, low), low)
    box.set_top(b_ny1, ny1_h)
    box.set_bottom(b_ny1, ny1_l)
    box.set_right(b_ny1, time)
    mid = (ny1_h + ny1_l) / 2
    line.set_y1(l_ny1_mid, mid)
    line.set_y2(l_ny1_mid, mid)
    if not na(lb_ny1_mid)
        label.set_y(lb_ny1_mid, mid)

var box b_ny2 = na, var line l_ny2_mid = na, var label lb_ny2_mid = na
if start_ny2
    box.delete(b_ny2)
    line.delete(l_ny2_mid)
    label.delete(lb_ny2_mid)
    ny2_h := high
    ny2_l := low
    st_ny2 := 0
    bk_ny2 := false
    b_ny2 := box.new(time, high, time, low, xloc=xloc.bar_time, border_color=f_theme_ny2_bor(), bgcolor=f_theme_ny2_box())
    t_close = f_get_1600_et(time)
    l_ny2_mid := line.new(time, high, t_close, high, xloc=xloc.bar_time, color=f_theme_ny2_bor(), style=line.style_dotted)
    if show_ref_lbl
        lb_ny2_mid := label.new(t_close, high, "NY2 Mid", xloc=xloc.bar_time, style=label.style_none, textcolor=f_theme_ny2_bor(), size=size.small, textalign=text.align_left)
if in_ny2
    ny2_h := math.max(nz(ny2_h, high), high)
    ny2_l := math.min(nz(ny2_l, low), low)
    box.set_top(b_ny2, ny2_h)
    box.set_bottom(b_ny2, ny2_l)
    box.set_right(b_ny2, time)
    mid = (ny2_h + ny2_l) / 2
    line.set_y1(l_ny2_mid, mid)
    line.set_y2(l_ny2_mid, mid)
    if not na(lb_ny2_mid)
        label.set_y(lb_ny2_mid, mid)

// ————— REFERENCE LEVELS —————
[pd_h, pd_l, pd_c] = request.security(syminfo.tickerid, "D", [high[1], low[1], close[1]], lookahead=barmerge.lookahead_on)
pd_m = (pd_h + pd_l) / 2
pw_c = request.security(syminfo.tickerid, "W", close[1], lookahead=barmerge.lookahead_on)

// 3. Intraday Levels (P12, Midnight Open, Globex Open)
var float p12_h = na, var float p12_l = na, var float open_mid = na, var float open_glob = na, var float open_0730 = na
var int bi_day_start = 0
var line[] a_lines = array.new_line()
var label[] a_labels = array.new_label()

bool is_1800 = (hour(time, "America/New_York") == 18) and (minute(time, "America/New_York") == 0)
bool start_p12 = is_1800 or (hour(time, "America/New_York") == 18 and not (hour(time[1], "America/New_York") == 18))
if start_p12
    p12_h := high
    p12_l := low
    open_glob := open
    open_mid := na
    open_0730 := na
    bi_day_start := bar_index

bool in_p12 = not na(time(timeframe.period, "1800-0559:1234567", "America/New_York"))
if in_p12
    p12_h := math.max(nz(p12_h, high), high)
    p12_l := math.min(nz(p12_l, low), low)

bool is_0000 = (hour(time, "America/New_York") == 0) and (minute(time, "America/New_York") == 0)
if is_0000 or (hour(time, "America/New_York") == 0 and hour(time[1], "America/New_York") != 0)
    open_mid := open

bool is_0730 = (hour(time, "America/New_York") == 7) and (minute(time, "America/New_York") == 30)
if is_0730 or (hour(time, "America/New_York") == 7 and minute(time, "America/New_York") >= 30 and minute(time[1], "America/New_York") < 30)
    open_0730 := open

f_draw_lev(price, t_start, t_end, col, style, txt, visible) =>
    if visible and not na(price)
        l = line.new(int(t_start), price, int(t_end), price, xloc=xloc.bar_time, color=col, style=style)
        array.push(a_lines, l)
        if show_ref_lbl
            lb = label.new(int(t_end), price, txt, xloc=xloc.bar_time, yloc=yloc.price, style=label.style_none, textcolor=col, size=size.small, textalign=text.align_left)
            array.push(a_labels, lb)

if barstate.islast
    while array.size(a_lines) > 0
        line.delete(array.pop(a_lines))
    while array.size(a_labels) > 0
        label.delete(array.pop(a_labels))
        
    t_start_d = time[bar_index - bi_day_start]
    // 20 bars projection
    t_proj = time + 20 * timeframe.in_seconds(timeframe.period) * 1000
    
    // Legacy full-day end for reference (optional, if we wanted to clamp)
    // t_end_d = t_start_d + 86400000 
    
    if show_pd
        f_draw_lev(pd_h, t_start_d, t_proj, f_theme_pd(), line.style_dashed, "PDH", true)
        f_draw_lev(pd_l, t_start_d, t_proj, f_theme_pd(), line.style_dashed, "PDL", true)
        f_draw_lev(pd_m, t_start_d, t_proj, f_theme_pd(), line.style_dotted, "PDM", true)
    if show_settle
        f_draw_lev(pd_c, t_start_d, t_proj, f_theme_settle(), line.style_solid, "Settle", true)
    if show_weekly
        f_draw_lev(pw_c, time("W"), t_proj, f_theme_weekly(), line.style_solid, "Weekly", true)
    if show_open 
        f_draw_lev(open_glob, t_start_d, t_proj, f_theme_open(), line.style_dashed, "Globex", true)
        if not na(open_mid)
            f_draw_lev(open_mid, t_start_d + 6*3600000, t_proj, f_theme_open(), line.style_dashed, "Midnight", true)
        if not na(open_0730)
            f_draw_lev(open_0730, t_start_d + 13.5*3600000, t_proj, f_theme_open(), line.style_dashed, "07:30", true)
    if show_p12
        p12_m = (p12_h + p12_l) / 2
        t_0600 = t_start_d + 12*3600000
        // Only show P12 after it is finalized (06:00 ET)
        if time >= t_0600
            f_draw_lev(p12_h, t_0600, t_proj, f_theme_p12(), line.style_solid, "P12H", true)
            f_draw_lev(p12_l, t_0600, t_proj, f_theme_p12(), line.style_solid, "P12L", true)
            f_draw_lev(p12_m, t_0600, t_proj, f_theme_p12(), line.style_dotted, "P12M", true)

// ————— CORE LOGIC —————
f_calc_status(s_sess, h, l, c_st) =>
    mode = c_st
    if not na(time(timeframe.period, s_sess + ":1234567", "America/New_York")) and not na(h) and not na(l)
        b_h = high > h
        b_l = low < l
        if mode == 0
            if b_h and not b_l
                mode := 1
            else if b_l and not b_h
                mode := 3
            else if b_h and b_l
                mode := 2
        else if mode == 1 and b_l
            mode := 2
        else if mode == 3 and b_h
            mode := 4
    mode
st_asia := f_calc_status(s_asia, asia_h, asia_l, st_asia)
st_lon := f_calc_status(s_lon, lon_h, lon_l, st_lon)
st_ny1 := f_calc_status(s_ny1, ny1_h, ny1_l, st_ny1)
st_ny2 := f_calc_status(s_ny2, ny2_h, ny2_l, st_ny2)

f_check_broken(s_win, h, l, c_bk) =>
    bk = c_bk
    if not bk and not na(time(timeframe.period, s_win, "America/New_York")) and not na(h) and not na(l)
        mid = (h + l) / 2
        if low <= mid and high >= mid
            bk := true
    bk
bk_asia := f_check_broken(bw_asia, asia_h, asia_l, bk_asia)
bk_lon  := f_check_broken(bw_lon, lon_h, lon_l, bk_lon)
bk_ny1  := f_check_broken(bw_ny1, ny1_h, ny1_l, bk_ny1)
bk_ny2  := f_check_broken(bw_ny2, ny2_h, ny2_l, bk_ny2)

// ————— HELPERS —————
f_fmt_time(m) =>
    h = math.floor(m / 60)
    mm = m % 60
    str.format("{0,number,00}:{1,number,00}", h, mm)

f_calc_mode_time(arr_vals) =>
    ModeRange r = ModeRange.new("N/A", 0.0, 0.0, false)
    if array.size(arr_vals) > 0
        int b_size = 15
        var int[] buckets = array.new_int(96, 0)
        array.fill(buckets, 0)
        int max_c = 0
        int max_b = 0
        for i = 0 to array.size(arr_vals) - 1
            v = array.get(arr_vals, i)
            b_idx = math.min(math.floor(v / b_size), 95)
            c = array.get(buckets, b_idx) + 1
            array.set(buckets, b_idx, c)
            if c > max_c
                max_c := c
                max_b := b_idx
        start_t = max_b * b_size
        end_t = start_t + b_size
        r.disp := f_fmt_time(start_t) + "-" + f_fmt_time(end_t)
        r.min_val := start_t
        r.max_val := end_t
        r.valid := true
    r

f_calc_mode_pct(arr_vals) =>
    ModeRange r = ModeRange.new("N/A", 0.0, 0.0, false)
    if array.size(arr_vals) > 0
        float step = 0.1
        int n_b = 120
        var int[] buckets = array.new_int(120, 0)
        array.fill(buckets, 0)
        int max_c = 0
        int max_b = 0
        for i = 0 to array.size(arr_vals) - 1
            v = array.get(arr_vals, i)
            // Offset by 6.0 to cover -6% to +6% range
            b_idx = math.min(math.max(math.floor((v + 6.0) / step), 0), n_b - 1)
            c = array.get(buckets, b_idx) + 1
            array.set(buckets, b_idx, c)
            if c > max_c
                max_c := c
                max_b := b_idx
        
        // Mode Range
        float mode_s = (max_b * step) - 6.0
        float mode_e = mode_s + step
        
        // Median Range
        array.sort(arr_vals)
        int mid_idx = array.size(arr_vals) / 2
        float med_val = array.get(arr_vals, mid_idx)
        float med_s = math.floor(med_val / step) * step
        float med_e = med_s + step
        
        // Union Range
        float u_min = math.min(mode_s, med_s)
        float u_max = math.max(mode_e, med_e)
        
        // Display "Highest to Lowest" (User preference)
        r.disp := str.format("{0,number,#.#} to {1,number,#.#}%", u_max, u_min)
        r.min_val := u_min
        r.max_val := u_max
        r.valid := true
    r

f_draw_box(m_time, m_price, d_open, b_col, row_name, is_high) =>
    if show_boxes and not na(d_open) and m_time.valid and m_price.valid
        y = year(time("D"))
        m = month(time("D"))
        d = dayofmonth(time("D"))
        t_base = timestamp("America/New_York", y, m, d, 0, 0)
        t_start = t_base + int(m_time.min_val * 60000)
        t_end   = t_base + int(m_time.max_val * 60000)
        if m_time.min_val < 1080
            t_start := t_start + 86400000
        if m_time.max_val < 1080
            t_end := t_end + 86400000
        p_start = d_open * (1 + m_price.min_val / 100.0)
        p_end   = d_open * (1 + m_price.max_val / 100.0)
        fill_c = color.new(b_col, t_box_fill)
        bx = box.new(t_start, p_end, t_end, p_start, xloc=xloc.bar_time, bgcolor=fill_c, border_color=b_col, border_style=line.style_solid)
        if show_labels
            txt = row_name + (is_high ? " HOD" : " LOD") + "\\n" + m_price.disp + "\\n" + m_time.disp
            label.new(int((t_start + t_end)/2), p_end, txt, xloc=xloc.bar_time, yloc=yloc.price, color=color.new(c_lbl_text, 100), style=label.style_label_down, textcolor=c_lbl_text, size=get_size(s_lbl))

f_render_row_adv(tbl, r, label, cnt, tot, bg_col, sz, arr_hod_t, arr_lod_t, arr_hod_p, arr_lod_p, cp12h, cp12m, cp12l, casia, clon, cmid, c0730, cpdh, cpdl, cpdm, d_open, is_long, is_fls, v_p12, v_asia, v_lon, v_mid, v_0730, v_pd) =>
    b_col = is_fls ? c_box_false : (is_long ? c_box_long : c_box_short)
    if cnt > 0
        pct = 100.0 * cnt / tot
        pp12h = 100.0 * cp12h / cnt
        pp12m = 100.0 * cp12m / cnt
        pp12l = 100.0 * cp12l / cnt
        pasia = 100.0 * casia / cnt
        plon = 100.0 * clon / cnt
        pmid = 100.0 * cmid / cnt
        p0730 = 100.0 * c0730 / cnt
        ppdh = 100.0 * cpdh / cnt
        ppdl = 100.0 * cpdl / cnt
        ppdm = 100.0 * cpdm / cnt
        
        m_hod_t = f_calc_mode_time(arr_hod_t)
        m_lod_t = f_calc_mode_time(arr_lod_t)
        m_hod_p = f_calc_mode_pct(arr_hod_p)
        m_lod_p = f_calc_mode_pct(arr_lod_p)
        f_draw_box(m_hod_t, m_hod_p, d_open, b_col, label, true)
        f_draw_box(m_lod_t, m_lod_p, d_open, b_col, label, false)
        
        table.cell(tbl, 0, r, label, bgcolor=bg_col, text_color=color.black, text_size=sz)
        table.cell(tbl, 1, r, str.format("{0,number,#.#}%", pct) + " (" + str.tostring(cnt) + ")", bgcolor=color.black, text_color=color.white, text_size=sz)
        table.cell(tbl, 2, r, m_lod_t.disp, bgcolor=color.black, text_color=color.white, text_size=sz)
        table.cell(tbl, 3, r, m_hod_t.disp, bgcolor=color.black, text_color=color.white, text_size=sz)
        table.cell(tbl, 4, r, m_lod_p.disp, bgcolor=color.black, text_color=color.white, text_size=sz)
        table.cell(tbl, 5, r, m_hod_p.disp, bgcolor=color.black, text_color=color.white, text_size=sz)
        table.cell(tbl, 6, r, v_p12 ? str.format("{0,number,#.#}%", pp12h) : "...", bgcolor=color.black, text_color=color.white, text_size=sz)
        table.cell(tbl, 7, r, v_p12 ? str.format("{0,number,#.#}%", pp12m) : "...", bgcolor=color.black, text_color=color.white, text_size=sz)
        table.cell(tbl, 8, r, v_p12 ? str.format("{0,number,#.#}%", pp12l) : "...", bgcolor=color.black, text_color=color.white, text_size=sz)
        table.cell(tbl, 9, r, v_asia ? str.format("{0,number,#.#}%", pasia) : "...", bgcolor=color.black, text_color=color.white, text_size=sz)
        table.cell(tbl, 10, r, v_lon ? str.format("{0,number,#.#}%", plon) : "...", bgcolor=color.black, text_color=color.white, text_size=sz)
        table.cell(tbl, 11, r, v_mid ? str.format("{0,number,#.#}%", pmid) : "...", bgcolor=color.black, text_color=color.white, text_size=sz)
        table.cell(tbl, 12, r, v_0730 ? str.format("{0,number,#.#}%", p0730) : "...", bgcolor=color.black, text_color=color.white, text_size=sz)
        table.cell(tbl, 13, r, v_pd ? str.format("{0,number,#.#}%", ppdh) : "...", bgcolor=color.black, text_color=color.white, text_size=sz)
        table.cell(tbl, 14, r, v_pd ? str.format("{0,number,#.#}%", ppdm) : "...", bgcolor=color.black, text_color=color.white, text_size=sz)
        table.cell(tbl, 15, r, v_pd ? str.format("{0,number,#.#}%", ppdl) : "...", bgcolor=color.black, text_color=color.white, text_size=sz)

// ————— HISTOGRAMS —————
f_draw_time_hist(arr_times, anchor_p, col, is_up, t_ref) =>
    if array.size(arr_times) > 0 and not na(anchor_p) and not na(t_ref)
        // Bucketize into 15-minute intervals (0-95) based on RELATIVE time from 18:00
        var int[] buckets = array.new_int(96, 0)
        array.fill(buckets, 0)
        int max_cnt = 0
        for i = 0 to array.size(arr_times) - 1
            t_raw = array.get(arr_times, i)
            // Convert raw time (0-1439) to relatives minutes from 18:00 (offset 1080)
            // 18:00 (1080) -> 0. 00:00 (0) -> 360. 17:59 (1079) -> 1439.
            t_rel = (t_raw - 1080 + 1440) % 1440
            
            b = math.min(math.floor(t_rel / 15), 95)
            c = array.get(buckets, b) + 1
            array.set(buckets, b, c)
            if c > max_cnt
                max_cnt := c
        
        // Draw
        if max_cnt > 0
            float scale_fac = hist_scale * (is_up ? 1 : -1) * 0.0005 // 0.05% price per count base
            float y_disp = (is_up ? 1 : -1) * hist_disp / 100.0
            
            // Draw buckets relative to t_ref (Session Start)
            for b = 0 to 95
                cnt = array.get(buckets, b)
                if cnt > 0
                    // t_ref is 18:00 of prev day (Session Start)
                    // b=0 is 18:00-18:15. b=24 is 00:00-00:15.
                    t_s = t_ref + b * 15 * 60000
                    t_e = t_s + 15 * 60000
                    
                    p_base = anchor_p * (1.0 + y_disp)
                    p_curr = p_base * (1.0 + cnt * scale_fac)
                    
                    box.new(t_s, p_curr, t_e, p_base, xloc=xloc.bar_time, bgcolor=col, border_width=0)

// ————— PRICE MODEL —————
f_draw_price_model(st_asia, st_lon, st_ny1, st_ny2, pd_m, d_open, bi_day_start, open_asia, open_lon, open_ny, lt_t, lt_h, lt_l, lf_t, lf_h, lf_l, st_t, st_h, st_l, sf_t, sf_h, sf_l) =>
    var polyline pm_h = na, var polyline pm_l = na, var label lbl_pm = na, var label lbl_debug = na
    if show_pm
        string sel = pm_outcome
        if sel == "Auto"
            int code = st_ny2 != 0 ? st_ny2 : st_ny1 != 0 ? st_ny1 : st_lon != 0 ? st_lon : st_asia
            if code == 1 or code == 2
                sel := "Long " + (code == 1 ? "True" : "False")
            else if code == 3 or code == 4
                sel := "Short " + (code == 3 ? "True" : "False")
        int[] t_arr = sel=="Long True"?lt_t: sel=="Long False"?lf_t: sel=="Short True"?st_t: sel=="Short False"?sf_t : array.new_int(0)
        float[] h_arr = sel=="Long True"?lt_h: sel=="Long False"?lf_h: sel=="Short True"?st_h: sel=="Short False"?sf_h : array.new_float(0)
        float[] l_arr = sel=="Long True"?lt_l: sel=="Long False"?lf_l: sel=="Short True"?st_l: sel=="Short False"?sf_l : array.new_float(0)
        if array.size(t_arr) > 0
            pts_h = array.new<chart.point>(), pts_l = array.new<chart.point>()
            
            // Determine active anchor
            float base_p = d_open
            int t_offset = 0
            float anchor_val = 0.0 // Value of model at anchor time (pct)
            
            // Priority: NY (08:00=480+360=840m) > Lon (02:00=480m) > Asia (18:00=0m)
            // Note: t_arr is Minutes from 18:00.
            // Asia Open @ 18:00 (0 min)
            // Lon Open @ 02:00 (8*60 = 480 min)
            // NY Open @ 08:00 (14*60 = 840 min)
            
            bool is_ny = not na(open_ny) and bar_index > bi_day_start + 10 // approximate check
            bool is_lon = not na(open_lon) and not is_ny
            
            // Find model indices for re-anchoring
            int idx_lon = -1, int idx_ny = -1
            // Optimization: Assuming sorted time array, can binary search or loop. Loop is fine for <100 pts.
            // Usually 02:00 is around 480. 08:00 is around 840.
            
            for i=0 to array.size(t_arr)-1
                t_val = array.get(t_arr, i)
                if t_val >= 480 and idx_lon == -1
                    idx_lon := i
                if t_val >= 840 and idx_ny == -1
                    idx_ny := i
            
            // Apply Re-anchoring logic
            // If NY active: Anchor to open_ny at t=840 (approx)
            // If Lon active: Anchor to open_lon at t=480 (approx)
            // Else: Anchor to open_asia (d_open) at t=0
            
            // Currently using simple time checks. Better to use session flags passed in?
            // open_ny valid means we passed 08:00.
            
            float scale_h_base = 0.0
            float scale_l_base = 0.0
            
            if not na(open_ny) and idx_ny != -1
                base_p := open_ny
                scale_h_base := array.get(h_arr, idx_ny) / 100.0
                scale_l_base := array.get(l_arr, idx_ny) / 100.0
            else if not na(open_lon) and idx_lon != -1
                base_p := open_lon
                scale_h_base := array.get(h_arr, idx_lon) / 100.0
                scale_l_base := array.get(l_arr, idx_lon) / 100.0
            else
                base_p := d_open // Default 18:00
                scale_h_base := 0.0
                scale_l_base := 0.0

            if not na(base_p) and bi_day_start > 0
                _ts_start = time[bar_index - bi_day_start]
                if not na(_ts_start)
                    for i = 0 to array.size(t_arr) - 1
                        t_min = array.get(t_arr, i)
                        t_pt = _ts_start + t_min*60000
                        
                        // Re-anchor Formula:
                        // P_new = Base * (1 + (Model_t - Model_Anchor)) ?
                        // Or Proportional? P_new = Base * (1+Model_t) / (1+Model_Anchor)
                        // Using Proportional to preserve percentage scaling.
                        
                        float val_h = array.get(h_arr, i) / 100.0
                        float val_l = array.get(l_arr, i) / 100.0
                        
                        // Avoid division by zero if model_anchor is -100% (unlikely)
                        float p_h = base_p * (1.0 + val_h) / (1.0 + scale_h_base)
                        float p_l = base_p * (1.0 + val_l) / (1.0 + scale_l_base)
                        
                        array.push(pts_h, chart.point.from_time(t_pt, p_h))
                        array.push(pts_l, chart.point.from_time(t_pt, p_l))
                        
                    polyline.delete(pm_h)
                    polyline.delete(pm_l)
                    label.delete(lbl_pm)
                    label.delete(lbl_debug)
                    pm_h := polyline.new(pts_h, line_color=color.new(c_pm_high, pm_opacity), xloc=xloc.bar_time, line_width=2)
                    pm_l := polyline.new(pts_l, line_color=color.new(c_pm_low, pm_opacity), xloc=xloc.bar_time, line_width=2)

// ————— TABLES —————
f_status_str(c, act, bk) =>
    s = c==1?(act?"Long (Pend)":"Long True"): c==2?"Long False": c==3?(act?"Short (Pend)":"Short True"): c==4?"Short False":"Neutral"
    bk ? s + " (BK)" : s

var table tbl_res = table.new(get_pos(p_res), 16, 5, border_width = 1) 
var table tbl_stat = table.new(get_pos(p_stat), 2, 5, border_width = 1)

f_match(hc, hb, lc, lb, loose, ignore_bk) =>
    // Status Match
    s_ok = lc==0 ? true : loose ? (lc==1 ? (hc==1 or hc==2) : lc==3 ? (hc==3 or hc==4) : hc==lc) : (hc==lc)
    // Broken Match (Old Logic: lb restricts to hb=1. lb=0 allows all)
    b_ok = ignore_bk ? true : (lb ? (hb == 1) : true)
    s_ok and b_ok

// Caching Variables
var int last_tgt_idx = -1
var int last_st_asia = -1, var int last_st_lon = -1, var int last_st_ny1 = -1, var int last_st_ny2 = -1
var bool last_bk_asia = false, var bool last_bk_lon = false, var bool last_bk_ny1 = false, var bool last_bk_ny2 = false

// Aggregators
var int c_lt = 0, var int c_lf = 0, var int c_st = 0, var int c_sf = 0
var int total_cnt = 0
var string cached_title = "Loading..."

var int[] lt_ht = array.new_int(0), var int[] lt_lt = array.new_int(0), var float[] lt_hp = array.new_float(0), var float[] lt_lp = array.new_float(0)
var int[] lf_ht = array.new_int(0), var int[] lf_lt = array.new_int(0), var float[] lf_hp = array.new_float(0), var float[] lf_lp = array.new_float(0)
var int[] st_ht = array.new_int(0), var int[] st_lt = array.new_int(0), var float[] st_hp = array.new_float(0), var float[] st_lp = array.new_float(0)
var int[] sf_ht = array.new_int(0), var int[] sf_lt = array.new_int(0), var float[] sf_hp = array.new_float(0), var float[] sf_lp = array.new_float(0)

var int lt_t_p12h = 0, var int lt_t_p12m = 0, var int lt_t_p12l = 0, var int lt_t_asia = 0, var int lt_t_lon = 0, var int lt_t_ny1m = 0, var int lt_t_midnight = 0, var int lt_t_0730 = 0
var int lt_t_pdh = 0, var int lt_t_pdl = 0, var int lt_t_pdm = 0
var int lf_t_p12h = 0, var int lf_t_p12m = 0, var int lf_t_p12l = 0, var int lf_t_asia = 0, var int lf_t_lon = 0, var int lf_t_ny1m = 0, var int lf_t_midnight = 0, var int lf_t_0730 = 0
var int lf_t_pdh = 0, var int lf_t_pdl = 0, var int lf_t_pdm = 0
var int st_t_p12h = 0, var int st_t_p12m = 0, var int st_t_p12l = 0, var int st_t_asia = 0, var int st_t_lon = 0, var int st_t_ny1m = 0, var int st_t_midnight = 0, var int st_t_0730 = 0
var int st_t_pdh = 0, var int st_t_pdl = 0, var int st_t_pdm = 0
var int sf_t_p12h = 0, var int sf_t_p12m = 0, var int sf_t_p12l = 0, var int sf_t_asia = 0, var int sf_t_lon = 0, var int sf_t_ny1m = 0, var int sf_t_midnight = 0, var int sf_t_0730 = 0
var int sf_t_pdh = 0, var int sf_t_pdl = 0, var int sf_t_pdm = 0

// Load Arrays
var int[] hod_times = LibTimes.get_hod_time(), var int[] lod_times = LibTimes.get_lod_time()
var float[] hod_pcts = LibLevels.get_hod_pct(), var float[] lod_pcts = LibLevels.get_lod_pct()
// Load Touches
var int[] t_p12h = LibTouches.get_p12h_asia() // These are just dummies to establish names, will be selected dynamically
// Session-indexed touch arrays
var int[] t_p12h_a = LibTouches.get_p12h_asia(), var int[] t_p12h_l = LibTouches.get_p12h_london(), var int[] t_p12h_n1 = LibTouches.get_p12h_ny1(), var int[] t_p12h_n2 = LibTouches.get_p12h_ny2()
var int[] t_p12m_a = LibTouches.get_p12m_asia(), var int[] t_p12m_l = LibTouches.get_p12m_london(), var int[] t_p12m_n1 = LibTouches.get_p12m_ny1(), var int[] t_p12m_n2 = LibTouches.get_p12m_ny2()
var int[] t_p12l_a = LibTouches.get_p12l_asia(), var int[] t_p12l_l = LibTouches.get_p12l_london(), var int[] t_p12l_n1 = LibTouches.get_p12l_ny1(), var int[] t_p12l_n2 = LibTouches.get_p12l_ny2()
var int[] t_asia_a = LibTouches.get_asia_mid_asia(), var int[] t_asia_l = LibTouches.get_asia_mid_london(), var int[] t_asia_n1 = LibTouches.get_asia_mid_ny1(), var int[] t_asia_n2 = LibTouches.get_asia_mid_ny2()
var int[] t_lon_a = LibTouches.get_london_mid_asia(), var int[] t_lon_l = LibTouches.get_london_mid_london(), var int[] t_lon_n1 = LibTouches.get_london_mid_ny1(), var int[] t_lon_n2 = LibTouches.get_london_mid_ny2()
var int[] t_ny1m_a = LibTouches.get_ny1_mid_asia(), var int[] t_ny1m_l = LibTouches.get_ny1_mid_london(), var int[] t_ny1m_n1 = LibTouches.get_ny1_mid_ny1(), var int[] t_ny1m_n2 = LibTouches.get_ny1_mid_ny2()
var int[] t_midnight_a = LibTouches.get_midnight_open_asia(), var int[] t_midnight_l = LibTouches.get_midnight_open_london(), var int[] t_midnight_n1 = LibTouches.get_midnight_open_ny1(), var int[] t_midnight_n2 = LibTouches.get_midnight_open_ny2()
var int[] t_0730_a = LibTouches.get_open_0730_asia(), var int[] t_0730_l = LibTouches.get_open_0730_london(), var int[] t_0730_n1 = LibTouches.get_open_0730_ny1(), var int[] t_0730_n2 = LibTouches.get_open_0730_ny2()
var int[] t_pdh_a = LibTouches.get_pdh_asia(), var int[] t_pdh_l = LibTouches.get_pdh_london(), var int[] t_pdh_n1 = LibTouches.get_pdh_ny1(), var int[] t_pdh_n2 = LibTouches.get_pdh_ny2()
var int[] t_pdl_a = LibTouches.get_pdl_asia(), var int[] t_pdl_l = LibTouches.get_pdl_london(), var int[] t_pdl_n1 = LibTouches.get_pdl_ny1(), var int[] t_pdl_n2 = LibTouches.get_pdl_ny2()
var int[] t_pdm_a = LibTouches.get_pdm_asia(), var int[] t_pdm_l = LibTouches.get_pdm_london(), var int[] t_pdm_n1 = LibTouches.get_pdm_ny1(), var int[] t_pdm_n2 = LibTouches.get_pdm_ny2()

d_open = request.security(syminfo.tickerid, "D", open, lookahead=barmerge.lookahead_on)
if barstate.islast
    sz = get_size(s_res)
    bool fin_asia = not na(time(timeframe.period, "0230-1700:1234567", "America/New_York"))
    bool fin_lon  = not na(time(timeframe.period, "0730-1700:1234567", "America/New_York"))
    bool fin_ny1  = not na(time(timeframe.period, "1130-1700:1234567", "America/New_York"))
    bool fin_ny2  = not na(time(timeframe.period, "1615-1700:1234567", "America/New_York"))

    table.clear(tbl_stat, 0, 0, 1, 4)
    table.cell(tbl_stat, 0, 0, "Current Status", bgcolor=color.black, text_color=color.white, text_size=sz)
    table.cell(tbl_stat, 0, 1, "Asia: " + f_status_str(st_asia, not fin_asia, bk_asia), bgcolor=color.black, text_color=color.white, text_size=sz)
    table.cell(tbl_stat, 0, 2, "Lon: " + f_status_str(st_lon, not fin_lon, bk_lon), bgcolor=color.black, text_color=color.white, text_size=sz)
    table.cell(tbl_stat, 0, 3, "NY1: " + f_status_str(st_ny1, not fin_ny1, bk_ny1), bgcolor=color.black, text_color=color.white, text_size=sz)
    table.cell(tbl_stat, 0, 4, "NY2: " + f_status_str(st_ny2, not fin_ny2, bk_ny2), bgcolor=color.black, text_color=color.white, text_size=sz)

    int tgt_idx = 0, string title = "Asia Outcomes"
    if fin_asia
        tgt_idx := 1
        title := "London Outcomes"
    if fin_lon
        tgt_idx := 2
        title := "NY1 Outcomes"
    if fin_ny1
        tgt_idx := 3
        title := "NY2 Outcomes"

    state_changed = (tgt_idx != last_tgt_idx) or (st_asia != last_st_asia) or (st_lon != last_st_lon) or (st_ny1 != last_st_ny1) or (st_ny2 != last_st_ny2) or (bk_asia != last_bk_asia) or (bk_lon != last_bk_lon) or (bk_ny1 != last_bk_ny1) or (bk_ny2 != last_bk_ny2)
    if state_changed
        c_lt := 0, c_lf := 0, c_st := 0, c_sf := 0, total_cnt := 0
        lt_t_p12h := 0, lt_t_p12m := 0, lt_t_p12l := 0, lt_t_asia := 0, lt_t_lon := 0, lt_t_pdh := 0, lt_t_pdl := 0, lt_t_pdm := 0
        lf_t_p12h := 0, lf_t_p12m := 0, lf_t_p12l := 0, lf_t_asia := 0, lf_t_lon := 0, lf_t_pdh := 0, lf_t_pdl := 0, lf_t_pdm := 0
        st_t_p12h := 0, st_t_p12m := 0, st_t_p12l := 0, st_t_asia := 0, st_t_lon := 0, st_t_pdh := 0, st_t_pdl := 0, st_t_pdm := 0
        sf_t_p12h := 0, sf_t_p12m := 0, sf_t_p12l := 0, sf_t_asia := 0, sf_t_lon := 0, sf_t_pdh := 0, sf_t_pdl := 0, sf_t_pdm := 0
        array.clear(lt_ht), array.clear(lt_lt), array.clear(lt_hp), array.clear(lt_lp)
        array.clear(lf_ht), array.clear(lf_lt), array.clear(lf_hp), array.clear(lf_lp)
        array.clear(st_ht), array.clear(st_lt), array.clear(st_hp), array.clear(st_lp)
        array.clear(sf_ht), array.clear(sf_lt), array.clear(sf_hp), array.clear(sf_lp)
        cached_title := title
        for i = 0 to array.size(dates) - 1
            bool ok = true
            // Match History with bits
            if tgt_idx > 0 and not f_match(f_get_code(asia_stats, i), f_get_bit(asia_bk, i), st_asia, bk_asia, false, false)
                ok := false
            if tgt_idx > 1 and not f_match(f_get_code(london_stats, i), f_get_bit(london_bk, i), st_lon, bk_lon, false, false)
                ok := false
            if tgt_idx > 2 and not f_match(f_get_code(ny1_stats, i), f_get_bit(ny1_bk, i), st_ny1, bk_ny1, false, false)
                ok := false
            
            // Current Session bit-unpacked
            int hist_s = tgt_idx==0?f_get_code(asia_stats, i): tgt_idx==1?f_get_code(london_stats, i): tgt_idx==2?f_get_code(ny1_stats, i): f_get_code(ny2_stats, i)
            int hist_b = tgt_idx==0?f_get_bit(asia_bk, i): tgt_idx==1?f_get_bit(london_bk, i): tgt_idx==2?f_get_bit(ny1_bk, i): f_get_bit(ny2_bk, i)
            int live_s = tgt_idx==0?st_asia: tgt_idx==1?st_lon: tgt_idx==2?st_ny1: st_ny2
            bool live_b = tgt_idx==0?bk_asia: tgt_idx==1?bk_lon: tgt_idx==2?bk_ny1: bk_ny2
            bool is_pend = (tgt_idx==0 and not fin_asia) or (tgt_idx==1 and not fin_lon) or (tgt_idx==2 and not fin_ny1) or (tgt_idx==3 and not fin_ny2)
            
            if ok and f_match(hist_s, hist_b, live_s, live_b, is_pend, false)
                total_cnt += 1
                _ht = array.get(hod_times, i), _lt = array.get(lod_times, i), _hp = array.get(hod_pcts, i), _lp = array.get(lod_pcts, i)
                
                // Select session-indexed arrays for this historical day
                int[] cur_p12h = tgt_idx==0?t_p12h_a: tgt_idx==1?t_p12h_l: tgt_idx==2?t_p12h_n1: t_p12h_n2
                int[] cur_p12m = tgt_idx==0?t_p12m_a: tgt_idx==1?t_p12m_l: tgt_idx==2?t_p12m_n1: t_p12m_n2
                int[] cur_p12l = tgt_idx==0?t_p12l_a: tgt_idx==1?t_p12l_l: tgt_idx==2?t_p12l_n1: t_p12l_n2
                int[] cur_asia = tgt_idx==0?t_asia_a: tgt_idx==1?t_asia_l: tgt_idx==2?t_asia_n1: t_asia_n2
                int[] cur_lon = tgt_idx==0?t_lon_a: tgt_idx==1?t_lon_l: tgt_idx==2?t_lon_n1: t_lon_n2
                int[] cur_ny1m = tgt_idx==0?t_ny1m_a: tgt_idx==1?t_ny1m_l: tgt_idx==2?t_ny1m_n1: t_ny1m_n2
                int[] cur_midnight = tgt_idx==0?t_midnight_a: tgt_idx==1?t_midnight_l: tgt_idx==2?t_midnight_n1: t_midnight_n2
                int[] cur_0730 = tgt_idx==0?t_0730_a: tgt_idx==1?t_0730_l: tgt_idx==2?t_0730_n1: t_0730_n2
                int[] cur_pdh = tgt_idx==0?t_pdh_a: tgt_idx==1?t_pdh_l: tgt_idx==2?t_pdh_n1: t_pdh_n2
                int[] cur_pdl = tgt_idx==0?t_pdl_a: tgt_idx==1?t_pdl_l: tgt_idx==2?t_pdl_n1: t_pdl_n2
                int[] cur_pdm = tgt_idx==0?t_pdm_a: tgt_idx==1?t_pdm_l: tgt_idx==2?t_pdm_n1: t_pdm_n2

                _p12h = f_get_bit(cur_p12h, i), _p12m = f_get_bit(cur_p12m, i), _p12l = f_get_bit(cur_p12l, i)
                _casia = f_get_bit(cur_asia, i), _clon = f_get_bit(cur_lon, i), _cny1m = f_get_bit(cur_ny1m, i)
                _cmidnight = f_get_bit(cur_midnight, i), _c0730 = f_get_bit(cur_0730, i)
                _cpdh = f_get_bit(cur_pdh, i), _cpdl = f_get_bit(cur_pdl, i), _cpdm = f_get_bit(cur_pdm, i)

                if hist_s == 1
                    c_lt += 1, array.push(lt_ht, _ht), array.push(lt_lt, _lt), array.push(lt_hp, _hp), array.push(lt_lp, _lp)
                    lt_t_p12h += _p12h, lt_t_p12m += _p12m, lt_t_p12l += _p12l, lt_t_asia += _casia, lt_t_lon += _clon, lt_t_ny1m += _cny1m, lt_t_midnight += _cmidnight, lt_t_0730 += _c0730, lt_t_pdh += _cpdh, lt_t_pdl += _cpdl, lt_t_pdm += _cpdm
                else if hist_s == 2
                    c_lf += 1, array.push(lf_ht, _ht), array.push(lf_lt, _lt), array.push(lf_hp, _hp), array.push(lf_lp, _lp)
                    lf_t_p12h += _p12h, lf_t_p12m += _p12m, lf_t_p12l += _p12l, lf_t_asia += _casia, lf_t_lon += _clon, lf_t_ny1m += _cny1m, lf_t_midnight += _cmidnight, lf_t_0730 += _c0730, lf_t_pdh += _cpdh, lf_t_pdl += _cpdl, lf_t_pdm += _cpdm
                else if hist_s == 3
                    c_st += 1, array.push(st_ht, _ht), array.push(st_lt, _lt), array.push(st_hp, _hp), array.push(st_lp, _lp)
                    st_t_p12h += _p12h, st_t_p12m += _p12m, st_t_p12l += _p12l, st_t_asia += _casia, st_t_lon += _clon, st_t_ny1m += _cny1m, st_t_midnight += _cmidnight, st_t_0730 += _c0730, st_t_pdh += _cpdh, st_t_pdl += _cpdl, st_t_pdm += _cpdm
                else if hist_s == 4
                    c_sf += 1, array.push(sf_ht, _ht), array.push(sf_lt, _lt), array.push(sf_hp, _hp), array.push(sf_lp, _lp)
                    sf_t_p12h += _p12h, sf_t_p12m += _p12m, sf_t_p12l += _p12l, sf_t_asia += _casia, sf_t_lon += _clon, sf_t_ny1m += _cny1m, sf_t_midnight += _cmidnight, sf_t_0730 += _c0730, sf_t_pdh += _cpdh, sf_t_pdl += _cpdl, sf_t_pdm += _cpdm
        last_tgt_idx := tgt_idx
        last_st_asia := st_asia
        last_st_lon := st_lon
        last_st_ny1 := st_ny1
        last_st_ny2 := st_ny2
        last_bk_asia := bk_asia
        last_bk_lon := bk_lon
        last_bk_ny1 := bk_ny1
        last_bk_ny2 := bk_ny2

        // Viz Logic
        t_start_d = time[bar_index - bi_day_start]
        t_0600 = t_start_d + 12 * 3600000
        t_asia_end = t_start_d + 8 * 3600000 // approx 02:00
        t_lon_end = t_start_d + 14 * 3600000 // approx 08:00
        t_midnight = t_start_d + 6 * 3600000 // 00:00
        t_0730 = t_start_d + 13 * 3600000 + 30 * 60000 // 07:30
        
        v_p12 = time >= t_0600
        v_asia = time >= t_asia_end
        v_lon = time >= t_lon_end
        v_mid = time >= t_midnight
        v_0730 = time >= t_0730
        v_pd = true 
    
        table.clear(tbl_res, 0, 0, 15, 4)
        table.cell(tbl_res, 0, 0, cached_title, bgcolor=color.black, text_color=color.white, text_size=sz)
        table.cell(tbl_res, 1, 0, "Stats", bgcolor=color.black, text_color=color.white, text_size=sz)
        table.cell(tbl_res, 2, 0, "LOD Time", bgcolor=color.black, text_color=color.white, text_size=sz)
        table.cell(tbl_res, 3, 0, "HOD Time", bgcolor=color.black, text_color=color.white, text_size=sz)
        table.cell(tbl_res, 4, 0, "LOD Dist", bgcolor=color.black, text_color=color.white, text_size=sz)
        table.cell(tbl_res, 5, 0, "HOD Dist", bgcolor=color.black, text_color=color.white, text_size=sz)
        table.cell(tbl_res, 6, 0, "P12H", bgcolor=color.black, text_color=color.white, text_size=sz)
        table.cell(tbl_res, 7, 0, "P12M", bgcolor=color.black, text_color=color.white, text_size=sz)
        table.cell(tbl_res, 8, 0, "P12L", bgcolor=color.black, text_color=color.white, text_size=sz)
        table.cell(tbl_res, 9, 0, "Asia Mid", bgcolor=color.black, text_color=color.white, text_size=sz)
        table.cell(tbl_res, 10, 0, "Lon Mid", bgcolor=color.black, text_color=color.white, text_size=sz)
        table.cell(tbl_res, 11, 0, "Midnight", bgcolor=color.black, text_color=color.white, text_size=sz)
        table.cell(tbl_res, 12, 0, "07:30", bgcolor=color.black, text_color=color.white, text_size=sz)
        table.cell(tbl_res, 13, 0, "PDH", bgcolor=color.black, text_color=color.white, text_size=sz)
        table.cell(tbl_res, 14, 0, "PDM", bgcolor=color.black, text_color=color.white, text_size=sz)
        table.cell(tbl_res, 15, 0, "PDL", bgcolor=color.black, text_color=color.white, text_size=sz)

        f_render_row_adv(tbl_res, 1, "Long True", c_lt, total_cnt, color.green, sz, lt_ht, lt_lt, lt_hp, lt_lp, lt_t_p12h, lt_t_p12m, lt_t_p12l, lt_t_asia, lt_t_lon, lt_t_midnight, lt_t_0730, lt_t_pdh, lt_t_pdl, lt_t_pdm, d_open, true, false, v_p12, v_asia, v_lon, v_mid, v_0730, v_pd)
        f_render_row_adv(tbl_res, 2, "Long False", c_lf, total_cnt, color.gray, sz, lf_ht, lf_lt, lf_hp, lf_lp, lf_t_p12h, lf_t_p12m, lf_t_p12l, lf_t_asia, lf_t_lon, lf_t_midnight, lf_t_0730, lf_t_pdh, lf_t_pdl, lf_t_pdm, d_open, false, true, v_p12, v_asia, v_lon, v_mid, v_0730, v_pd)
        f_render_row_adv(tbl_res, 3, "Short True", c_st, total_cnt, color.red, sz, st_ht, st_lt, st_hp, st_lp, st_t_p12h, st_t_p12m, st_t_p12l, st_t_asia, st_t_lon, st_t_midnight, st_t_0730, st_t_pdh, st_t_pdl, st_t_pdm, d_open, false, false, v_p12, v_asia, v_lon, v_mid, v_0730, v_pd)
        f_render_row_adv(tbl_res, 4, "Short False", c_sf, total_cnt, color.gray, sz, sf_ht, sf_lt, sf_hp, sf_lp, sf_t_p12h, sf_t_p12m, sf_t_p12l, sf_t_asia, sf_t_lon, sf_t_midnight, sf_t_0730, sf_t_pdh, sf_t_pdl, sf_t_pdm, d_open, false, true, v_p12, v_asia, v_lon, v_mid, v_0730, v_pd)
        f_draw_price_model(st_asia, st_lon, st_ny1, st_ny2, pd_m, d_open, bi_day_start, open_asia, open_lon, open_ny, m_lt_t, m_lt_h, m_lt_l, m_lf_t, m_lf_h, m_lf_l, m_st_t, m_st_h, m_st_l, m_sf_t, m_sf_h, m_sf_l)

    // Histogram Calls
    if hist_outcome != "None" and barstate.islast
        t_start_d = time[bar_index - bi_day_start]
        int[] h_times = array.new_int(0)
        int[] l_times = array.new_int(0)
        color c_hist = color.gray
        
        if hist_outcome == "Long True"
            h_times := lt_ht, l_times := lt_lt
        else if hist_outcome == "Long False"
            h_times := lf_ht, l_times := lf_lt
        else if hist_outcome == "Short True"
            h_times := st_ht, l_times := st_lt
        else if hist_outcome == "Short False"
            h_times := sf_ht, l_times := sf_lt
            
        // Draw HOD histogram Up from P12 High (Use PM High Color)
        f_draw_time_hist(h_times, p12_h, color.new(c_pm_high, 50), true, t_start_d)
        // Draw LOD histogram Down from P12 Low (Use PM Low Color)
        f_draw_time_hist(l_times, p12_l, color.new(c_pm_low, 50), false, t_start_d)
"""

    with open(OUT_DIR / "ProfilerIndicator.pine", "w", encoding='utf-8') as f:
        f.write(ind_header + ind_body)
    print(f"Generated {OUT_DIR / 'ProfilerIndicator.pine'}")

def main():
    print("Loading data...")
    profiler, hod_lod, touches = load_data("NQ1")
    if not profiler:
        print("Warning: Profiler data missing")
        return
    print("Generating Pine Scripts...")
    generate_scripts(profiler, hod_lod, touches) 
    print("Success!")

if __name__ == "__main__":
    main()
