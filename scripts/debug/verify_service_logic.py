
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(r"c:\Users\vinay\tvDownloadOHLC")

from api.services.profiler_service import ProfilerService

def test_service():
    print("Testing ProfilerService.get_daily_hod_lod...")
    
    # 1. Test Default (Adjusted)
    res_adj = ProfilerService.get_daily_hod_lod("NQ1", unadjusted=False)
    if "error" in res_adj:
        print(f"Error Adjusted: {res_adj}")
    else:
        sample_date = "2024-05-06"
        val = res_adj.get(sample_date, {}).get('daily_open')
        print(f"Adjusted Sample (2024-05-06) Open: {val}")

    # 2. Test Unadjusted
    res_unadj = ProfilerService.get_daily_hod_lod("NQ1", unadjusted=True)
    if "error" in res_unadj:
        print(f"Error Unadjusted: {res_unadj}")
    else:
        sample_date = "2024-05-06"
        val = res_unadj.get(sample_date, {}).get('daily_open')
        print(f"Unadjusted Sample (2024-05-06) Open: {val}")
        
    # Validation logic
    # Adjusted open should be different from Unadjusted logic if backadjustment exists.
    # NQ1 backadjustment is likely negative/smaller in past or different.
    # Wait, 2024 is recent. Difference might be small.
    # Let's check a very old date.
    
    old_date = "1999-07-01" # From earlier inspection
    val_adj_old = res_adj.get(old_date, {}).get('daily_open')
    val_unadj_old = res_unadj.get(old_date, {}).get('daily_open')
    
    print(f"1999-07-01 Adjusted Open: {val_adj_old}")
    print(f"1999-07-01 Unadjusted Open: {val_unadj_old}")
    
    if val_adj_old is not None and val_unadj_old is not None:
        if val_adj_old != val_unadj_old:
            print("SUCCESS: Parameters return different data sets!")
        else:
            print("FAILURE: Parameters return same data set!")

if __name__ == "__main__":
    test_service()
