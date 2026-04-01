import pandas as pd
import os
from datetime import datetime

live_path = os.path.join('data', 'live', 'live_storage_-NQ.parquet')
if os.path.exists(live_path):
    df = pd.read_parquet(live_path)
    if not df.empty:
        last_ts = pd.to_datetime(df['time'].max(), unit='ms')
        print(f"LAST_TS_UTC: {last_ts}")
        print(f"DIFF_MINS: {(datetime.utcnow() - last_ts).total_seconds() / 60:.2f}")
    else:
        print("EMPTY")
else:
    print("NOT_FOUND")
