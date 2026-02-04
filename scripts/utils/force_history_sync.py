
import asyncio
import os
import sys
import pandas as pd
from datetime import datetime

# Import stream_chart (ensure sys path is correct if needed)
sys.path.append(r'c:\Users\vinay\tvDownloadOHLC\scripts\streaming')
import stream_chart
from stream_chart import get_client, update_historical_files

# Mock DATA_DIR in stream_chart to use a test dir?
# Or just run on real data if safe.
# Let's run on real to fix the stale NQ1_1d.

# Setup Client
print("Auth...")
client = get_client()

if client:
    print("Testing Update NQ...")
    # This should trigger fetch for NQ1_1d if stale
    # and 1W
    update_historical_files(client, "/NQ")
    
    print("\n--- Check 1d File ---")
    path_1d = r"c:\Users\vinay\tvDownloadOHLC\data\NQ1_1d.parquet"
    if os.path.exists(path_1d):
        df = pd.read_parquet(path_1d)
        print(f"Last Bar: {df.index[-1]}")
    else:
        print("1d file missing.")
        
else:
    print("Failed to auth.")
