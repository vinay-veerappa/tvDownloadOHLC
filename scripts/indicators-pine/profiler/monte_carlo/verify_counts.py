
import json
import numpy as np
from pathlib import Path
import sys

# Replicate Pine Script Bit-Unpacking Logic
def f_get_bit(val, i):
    # val is a 50-bit integer (or 15 values of 3 bits, or 15 values of 1 bit)
    # The Pine generator packs 15 values per int.
    # bits = 1 (for broken), bits = 3 (for status codes)
    
    # In generate_profiler_pine.py:
    # current = (current * (2**bits)) + (int(val) & ((1 << bits) - 1))
    # This stores the LATEST value in the lowest bits.
    
    # Wait, let's look at f_get_bit in ProfilerIndicator.pine:
    # val = array.get(arr, math.floor(i / 15))
    # pos = 14 - (i % 15)
    # math.floor(val / math.pow(2, pos)) % 2
    
    # This implies the HIGHEST bits are the EARLIEST values.
    # My pack_bits logic:
    # current = (current * (2**bits)) + val
    # This also makes the earliest values the highest bits.
    return (val >> (14 - (i % 15))) & 1

def f_get_code(val, i):
    # status codes are 3 bits (0-7)
    return (val >> (3 * (14 - (i % 15)))) & 7

def verify_counts():
    # Load the JSON that was used to generate the libraries
    with open("data/NQ1_profiler.json", "r") as f:
        sessions = json.load(f)
    
    # Group sessions by date
    days_data = {}
    for s in sessions:
        d = s['date']
        if d not in days_data: days_data[d] = {"Asia": 0, "Asia_BK": 0, "Lon": 0}
        
        status_code = 0
        s_low = s['status'].lower() if s['status'] else ""
        if "long true" in s_low: status_code = 1
        elif "long false" in s_low: status_code = 2
        elif "short true" in s_low: status_code = 3
        elif "short false" in s_low: status_code = 4
        
        if s['session'] == 'Asia':
            days_data[d]['Asia'] = status_code
            days_data[d]['Asia_BK'] = 1 if s.get('broken') else 0
        elif s['session'] == 'London':
            days_data[d]['Lon'] = status_code
            
    # These are the dates in order
    sorted_dates = sorted(days_data.keys())
    
    # User Filter: Asia LT (1) Broken (1), London Short (let's check 3 and 4)
    pine_matches = 0
    for d in sorted_dates:
        a_s = days_data[d]['Asia']
        a_b = days_data[d]['Asia_BK']
        l_s = days_data[d]['Lon']
        
        # Asia LT Broken
        if a_s == 1 and a_b == 1:
            # London Short (any short: 3 or 4)
            if l_s == 3 or l_s == 4:
                pine_matches += 1
                
    print(f"Pine Filtering Logic Match Count: {pine_matches}")

    # Now compare with Service (Calculated in previous step)
    # verify_values.py used: filters = {"Asia": "Long True", "London": "Short"}
    # Prefix match on "Short" matches 3 and 4.
    
if __name__ == "__main__":
    verify_counts()
