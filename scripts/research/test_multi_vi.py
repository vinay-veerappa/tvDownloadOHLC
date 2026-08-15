"""
Test multi-bar VI merger logic on NQ 15m data around 30,072 - 30,088 level.
"""
import sys
from pathlib import Path
_root_dir = str(Path(__file__).resolve().parents[2])
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

import pandas as pd
import numpy as np
from scripts.libs_py.data.resampler import resample_ohlcv

# Load NQ 1m data
df = pd.read_parquet("data/-NQ_1m.parquet")
df_15m = resample_ohlcv(df, "15min")

# Look at recent bars near 30,000 - 30,100
for i in range(2, len(df_15m)):
    o0, h0, l0, c0 = df_15m.iloc[i][["open", "high", "low", "close"]]
    o1, h1, l1, c1 = df_15m.iloc[i-1][["open", "high", "low", "close"]]
    o2, h2, l2, c2 = df_15m.iloc[i-2][["open", "high", "low", "close"]]
    
    # Bullish FVG
    is_bull_fvg = l0 > h2
    
    # VI 1-2 (Candle 2 to Candle 1)
    vi_12_bull = (min(o1, c1) > max(o2, c2)) and (h2 >= l1)
    vi_12_top = min(o1, c1) if vi_12_bull else np.nan
    vi_12_bot = max(o2, c2) if vi_12_bull else np.nan

    # VI 0-1 (Candle 1 to Candle 0)
    vi_01_bull = (min(o0, c0) > max(o1, c1)) and (h1 >= l0)
    vi_01_top = min(o0, c0) if vi_01_bull else np.nan
    vi_01_bot = max(o1, c1) if vi_01_bull else np.nan

    if is_bull_fvg:
        fvg_top = l0
        fvg_bot = h2
        has_vi = False
        final_top = fvg_top
        final_bot = fvg_bot
        
        if vi_12_bull and (vi_12_bot <= final_top + 4.0) and (vi_12_top >= final_bot - 4.0):
            final_top = max(final_top, vi_12_top)
            final_bot = min(final_bot, vi_12_bot)
            has_vi = True
            
        if vi_01_bull and (vi_01_bot <= final_top + 4.0) and (vi_01_top >= final_bot - 4.0):
            final_top = max(final_top, vi_01_top)
            final_bot = min(final_bot, vi_01_bot)
            has_vi = True

        if has_vi and (final_bot < 30100 and final_top > 30050):
            print(f"Time: {df_15m.index[i]} | Bull FVG: [{fvg_bot:.2f}, {fvg_top:.2f}] -> Merged Composite: [{final_bot:.2f}, {final_top:.2f}] (VI 1-2: {vi_12_bull}, VI 0-1: {vi_01_bull})")
