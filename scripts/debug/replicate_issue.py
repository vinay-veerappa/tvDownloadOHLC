
import json
from pathlib import Path

def replicate_bit_packing():
    # Simulate the bit-packing logic with 2 bits
    status_map = {
        "Long True": 1,
        "Long False": 2,
        "Short True": 3,
        "Short False": 4 # This requires 3 bits (100)
    }
    
    ticker = "NQ1"
    fname_prof = Path(f"data/{ticker}_profiler.json")
    
    print("Loading Profiler Data...")
    with open(fname_prof, "r") as f:
        profiler = json.load(f)
        
    print(f"Total Sessions: {len(profiler)}")
    
    corrupted_count = 0
    short_false_count = 0
    
    for s in profiler:
        status = s.get('status')
        if not status: continue
        
        # Original Logic
        code = 0
        sl = status.lower()
        if "long" in sl: code = 1 if "true" in sl else 2
        if "short" in sl: code = 3 if "true" in sl else 4
        
        if code == 4:
            short_false_count += 1
            
        # Simulate 2-bit packing (masking with 0b11 = 3)
        packed_val = code & 3
        
        if packed_val != code:
            corrupted_count += 1
            if corrupted_count < 5:
               print(f"status='{status}' code={code} (binary {bin(code)}) -> packed={packed_val} (binary {bin(packed_val)}) [CORRUPTED]")
               
    print(f"\nTotal Short False (Code 4): {short_false_count}")
    print(f"Total Corrupted by 2-bit packing: {corrupted_count}")
    
    if corrupted_count > 0:
        print("\nCONCLUSION: 2-bit packing corrupts 'Short False' (4) into 0 (None).")
        print("This causes 'Short False' days to disappear from the filter, skewing statistics.")
    else:
        print("\nNo corruption detected (unexpected).")

if __name__ == "__main__":
    replicate_bit_packing()
