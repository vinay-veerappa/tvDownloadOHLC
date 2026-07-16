import pandas as pd
import numpy as np
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent.parent))


import sys
from pathlib import Path

# Add project root to sys.path dynamically
_current_dir = Path(__file__).resolve().parent
while _current_dir.name and _current_dir.name != "scripts":
    _current_dir = _current_dir.parent
if _current_dir.name == "scripts":
    _root_dir = str(_current_dir.parent)
    if _root_dir not in sys.path:
        sys.path.insert(0, _root_dir)

from scripts.edgeful.data_loader import load_bars_duckdb, get_trading_date

def verify_consistency(instrument="ES1", limit=1000):
    print(f"--- Verifying Trading Date Consistency for {instrument} ---")
    
    # 1. Load data via DuckDB (contains SQL trading_date)
    df = load_bars_duckdb(instrument)
    
    # 2. Sample random bars
    sample = df.sample(min(limit, len(df)))
    
    # 3. Calculate Python trading_date
    sample['py_trading_date'] = sample.index.map(get_trading_date).map(lambda x: x if isinstance(x, pd.Timestamp) else pd.Timestamp(x))
    sample['py_trading_date'] = sample['py_trading_date'].dt.date
    
    # 4. Compare
    mismatches = sample[sample['trading_date'] != sample['py_trading_date']]
    
    if len(mismatches) == 0:
        print(f"SUCCESS: All {len(sample)} sampled bars match perfectly.")
    else:
        print(f"FAILURE: {len(mismatches)} mismatches found!")
        print(mismatches[['trading_date', 'py_trading_date']].head())
        
    # Check specific edge cases: Fridays and Sundays 18:00
    print("\n--- Checking Edge Cases (Friday/Sunday 18:00) ---")
    
    # Fri 18:00 ET -> should be next Monday
    # Find a Friday in the data
    fris = df[df.index.dayofweek == 4]
    if not fris.empty:
        fri_18 = fris[fris.index.hour >= 18].head(5)
        if not fri_18.empty:
            print("Friday 18:00+ Sample:")
            print(fri_18[['trading_date']])
            # Verify it's a Monday
            is_mon = pd.to_datetime(fri_18['trading_date']).dt.dayofweek == 0
            if is_mon.all():
                print("SUCCESS: Fri 18:00 mapped to Monday.")
            else:
                print("FAILURE: Fri 18:00 mapping FAILED.")
    
    # Sun 18:00 ET -> should be Monday
    suns = df[df.index.dayofweek == 6]
    if not suns.empty:
        sun_18 = suns[suns.index.hour >= 18].head(5)
        if not sun_18.empty:
            print("\nSunday 18:00+ Sample:")
            print(sun_18[['trading_date']])
            is_mon = pd.to_datetime(sun_18['trading_date']).dt.dayofweek == 0
            if is_mon.all():
                print("SUCCESS: Sun 18:00 mapped to Monday.")
            else:
                print("FAILURE: Sun 18:00 mapping FAILED.")

if __name__ == "__main__":
    verify_consistency()
