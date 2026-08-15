"""
Verify Pine and Python CISD level calculation on NQ data for the exact chart timeframe.
"""
import sys
from pathlib import Path
_root_dir = str(Path(__file__).resolve().parents[2])
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

import pandas as pd
import numpy as np
from scripts.libs_py.cisd import compute_cisd
from scripts.libs_py.data.resampler import resample_ohlcv

# Load NQ 1m data
df = pd.read_parquet("data/-NQ_1m.parquet")
df_15m = resample_ohlcv(df, "15min")

res_15m = compute_cisd(df_15m)
merged = pd.concat([df_15m, res_15m], axis=1)

print("Recent 15m CISD events and armed levels:")
events = merged[merged["cisd_event"] != 0]
print(events[["open", "high", "low", "close", "cisd_event", "cisd_state", "active_bull_level", "active_bear_level"]].tail(20))
