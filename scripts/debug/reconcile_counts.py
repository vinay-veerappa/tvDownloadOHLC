import json
from pathlib import Path

# Session Time Ranges (ET)
SESSION_RANGES = {
    'Asia': ('18:00', '02:00'),
    'London': ('02:00', '07:00'),
    'NY1': ('08:00', '12:00'),
    'NY2': ('12:00', '16:00'),
    'Daily': ('18:00', '17:00'),
    'P12': ('06:00', '17:00'),
}

def time_in_range(t_str, start_str, end_str):
    """Check if time string HH:MM is within session range (handles midnight crossing)."""
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

def p12h_touched_in_session(touch_times, session):
    """Check if P12H was touched during the specified session."""
    if not touch_times:
        return False
    
    start, end = SESSION_RANGES.get(session, ('00:00', '23:59'))
    
    for ts in touch_times:
        if time_in_range(ts, start, end):
            return True
    return False

def load_data(ticker="NQ1"):
    p_prof = Path(f"data/{ticker}_profiler.json")
    p_touches = Path(f"data/{ticker}_level_touches.json")
    
    if not p_prof.exists() or not p_touches.exists():
        print("Data missing")
        return None, None
        
    with open(p_prof, "r") as f: prof = json.load(f)
    with open(p_touches, "r") as f: touches = json.load(f)
    return prof, touches

def main():
    prof_data, touch_data = load_data()
    if not prof_data: return

    # Build Day Map
    day_map = {}
    for entry in prof_data:
        d = entry.get("date")
        d_clean = d.replace("-", "") if d else ""
        if not d_clean: continue
        
        if d_clean not in day_map: day_map[d_clean] = {"sessions": {}, "touches": {}}
        
        sess = entry.get("session")
        stat = entry.get("status", "").lower()
        bk = entry.get("broken", False)
        
        # Parse Status Code
        code = 0
        if "long" in stat:
            code = 1 if "true" in stat else 2
        elif "short" in stat:
            code = 3 if "true" in stat else 4
        
        day_map[d_clean]["sessions"][sess] = {"code": code, "broken": bk}

    # Add Touch Data (with touch_times for session filtering)
    for d_str, t_val in touch_data.items():
        if not d_str[0].isdigit(): continue
        d_int_str = d_str.replace("-", "")
        if d_int_str in day_map:
            p12h_data = t_val.get("p12h", {})
            day_map[d_int_str]["touches"]["p12h_times"] = p12h_data.get("touch_times", [])
            day_map[d_int_str]["touches"]["p12h_touched"] = p12h_data.get("touched", False)

    # Simulation Config
    f_asia_code = 3 # Short True
    f_asia_bk = True 
    f_lon_code = 4 # Short False
    f_lon_bk = True
    
    tgt_sess = "NY1"
    
    print(f"--- SIMULATION: Session-Specific P12H Probability ---")
    print(f"Filter: Asia=Short True (Bk), London=Short False (Bk)")
    print(f"Target Session: {tgt_sess}")
    
    matches = []
    
    for d, data in day_map.items():
        sess = data["sessions"]
        
        # Check Asia
        asia = sess.get("Asia")
        if not asia: continue
        if asia["code"] != f_asia_code: continue
        if f_asia_bk and not asia["broken"]: continue 
        
        # Check London
        lon = sess.get("London")
        if not lon: continue
        if lon["code"] != f_lon_code: continue
        if f_lon_bk and not lon["broken"]: continue
        
        matches.append(d)
        
    print(f"Matching Days: {len(matches)}")
    
    # Calculate Probabilities for NY1 Outcomes
    outcomes = {1:0, 2:0, 3:0, 4:0}
    p12h_hits_daily = {1:0, 2:0, 3:0, 4:0}  # Any time of day
    p12h_hits_session = {1:0, 2:0, 3:0, 4:0}  # Within target session
    
    for d in matches:
        data = day_map[d]
        ny1 = data["sessions"].get("NY1")
        if not ny1: continue
        
        c = ny1["code"]
        if c == 0: continue
        
        outcomes[c] += 1
        
        # Check P12H Touch (Daily: any time)
        if data["touches"].get("p12h_touched"):
            p12h_hits_daily[c] += 1
        
        # Check P12H Touch (Session-Specific)
        touch_times = data["touches"].get("p12h_times", [])
        if p12h_touched_in_session(touch_times, tgt_sess):
            p12h_hits_session[c] += 1
            
    print("\nNY1 Outcomes:")
    print(f"Long True:  {outcomes[1]}")
    print(f"Long False: {outcomes[2]}")
    print(f"Short True: {outcomes[3]}")
    print(f"Short False:{outcomes[4]}")
    
    print(f"\n--- P12H Probability (Daily - Any Time) ---")
    for code, label in [(1, "Long True"), (2, "Long False"), (3, "Short True"), (4, "Short False")]:
        tot = outcomes[code]
        if tot > 0:
            pct = (p12h_hits_daily[code] / tot) * 100
            print(f"  {label}: {pct:.2f}% ({p12h_hits_daily[code]}/{tot})")
    
    print(f"\n--- P12H Probability (During {tgt_sess} Session Only) ---")
    for code, label in [(1, "Long True"), (2, "Long False"), (3, "Short True"), (4, "Short False")]:
        tot = outcomes[code]
        if tot > 0:
            pct = (p12h_hits_session[code] / tot) * 100
            print(f"  {label}: {pct:.2f}% ({p12h_hits_session[code]}/{tot})")

if __name__ == "__main__":
    main()
