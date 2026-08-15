"""
Test Institutional HTF Liquidity Sweeps (1H, 4H, Daily Swings/PDH/PDL)
and HTF PD Array Delivery (1H, 4H, Daily FVGs/OBs) on NQ data.
"""
import sys
from pathlib import Path
_root_dir = str(Path(__file__).resolve().parents[2])
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

import pandas as pd
import numpy as np
from scripts.libs_py.data.resampler import resample_ohlcv
from scripts.libs_py.cisd import compute_cisd
from scripts.libs_py.fvg import compute_fvg

df_1m = pd.read_parquet("data/-NQ_1m.parquet")

# Resample to 15m, 1H, 4H, and 1D
df_15m = resample_ohlcv(df_1m, "15min")
df_1h = resample_ohlcv(df_1m, "1h")
df_4h = resample_ohlcv(df_1m, "4h")
df_1d = resample_ohlcv(df_1m, "1D")

# Compute 1H and 4H FVGs
fvg_1h = compute_fvg(df_1h, include_vi=True)
fvg_4h = compute_fvg(df_4h, include_vi=True)

# Compute 15m CISD
cisd_15m = compute_cisd(df_15m)

print("Data resampled successfully:")
print(f"15m bars: {len(df_15m)}, 1H bars: {len(df_1h)}, 4H bars: {len(df_4h)}, 1D bars: {len(df_1d)}")
print(f"1H FVGs found: {(fvg_1h['fvg_event'] != 0).sum()}, 4H FVGs found: {(fvg_4h['fvg_event'] != 0).sum()}")
print(f"15m CISD events found: {(cisd_15m['cisd_event'] != 0).sum()}")
