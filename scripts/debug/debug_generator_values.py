
import json
from pathlib import Path

def check_values():
    ticker = "NQ1"
    fname_prof = Path(f"data/{ticker}_profiler.json")
    fname_hl = Path(f"data/{ticker}_daily_hod_lod_unadjusted.json")
    
    print(f"Loading {fname_prof}...")
    with open(fname_prof, "r") as f:
        profiler = json.load(f)
        
    print(f"Loading {fname_hl}...")
    with open(fname_hl, "r") as f:
        hod_lod = json.load(f)
        
    data_map = {}
    
    # Init from Profiler (Status source)
    for s in profiler:
        date = s.get('date')
        if not date: continue
        d_int = int(date.replace('-', ''))
        
        # Only care about Long True
        status = s.get('status')
        if status != "Long True": continue
            
        data_map[d_int] = {
            'date': date,
            'status': status,
            'hod_p': 0.0
        }
        
    print(f"Found {len(data_map)} Long True days in Profiler.")
    
    # Merge HOD Source
    zeros = 0
    matched = 0
    
    for date_str, stats in hod_lod.items():
        if not date_str or not date_str[0].isdigit(): continue
        d_int = int(date_str.replace('-', ''))
        
        if d_int in data_map:
            d_open = stats.get('daily_open')
            d_high = stats.get('hod_price')
            
            if d_open and d_open > 0 and d_high is not None:
                val = round((d_high - d_open) / d_open * 100, 2)
                data_map[d_int]['hod_p'] = val
                matched += 1
            else:
                print(f"Invalid data for {date_str}: Open={d_open}, High={d_high}")

    # Check Zeros
    vals = []
    for d, v in data_map.items():
        hp = v['hod_p']
        vals.append(hp)
        if hp == 0.0:
            zeros += 1
            # Print first few zeros
            if zeros < 5:
                print(f"Zero HOD for {v['date']}. Status: {v['status']}")
                
    print(f"Total Long True: {len(data_map)}")
    print(f"Matched with HOD data: {matched}")
    print(f"Total Zeros: {zeros}")
    print(f"Percentage Zeros: {zeros / len(data_map) * 100:.2f}%")
    
    # Calc Median of non-zeros
    non_zeros = [x for x in vals if abs(x) > 0.001]
    non_zeros.sort()
    if non_zeros:
        mid = len(non_zeros) // 2
        print(f"Median (Non-Zero): {non_zeros[mid]}")
    else:
        print("No non-zero values.")
        
    # Calc Median of ALL
    vals.sort()
    mid = len(vals) // 2
    print(f"Median (All): {vals[mid]}")

if __name__ == "__main__":
    check_values()
