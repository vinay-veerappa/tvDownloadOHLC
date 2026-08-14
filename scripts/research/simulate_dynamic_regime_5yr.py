import sys
from pathlib import Path
import numpy as np
import pandas as pd

_root_dir = str(Path(__file__).resolve().parents[2])
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

from scripts.libs_py.data.loader import DataLoader
from scripts.trading_framework.config.config_loader import load_config

app_cfg = load_config()
loader = DataLoader(app_cfg)
df = loader.load_price("NQ1")

if df.index.tz is None:
    df.index = df.index.tz_localize("UTC")
df = df.tz_convert("America/New_York")

df['hour'] = df.index.hour
df['minute'] = df.index.minute
df['timeHHMM'] = df['hour'] * 100 + df['minute']

# Filter to RTH Morning Window (09:30 to 10:30 ET)
morn = df[(df['timeHHMM'] >= 930) & (df['timeHHMM'] <= 1030)].copy()

# Compute 14-bar ATR
morn['tr'] = np.maximum(
    morn['high'] - morn['low'],
    np.maximum(
        abs(morn['high'] - morn['close'].shift(1)),
        abs(morn['low'] - morn['close'].shift(1))
    )
)
morn['atr14'] = morn['tr'].rolling(14).mean()

print(f"Total 5-Year Morning Bars: {len(morn):,}")
print("=" * 105)
print(f"{'YEAR':<6} | {'MEDIAN NQ PRICE':<17} | {'1M ATR(14)':<12} | {'10PT STOP AS % OF 1M ATR':<26} | {'RECOMMENDED ATR-SCALED STOP':<28}")
print("=" * 105)
for y, g in morn.groupby(morn.index.year):
    avg_atr = g['atr14'].mean()
    med_close = g['close'].median()
    ratio = (10.0 / avg_atr) * 100
    rec_sl = avg_atr * 0.75  # Standard 0.75x 1m ATR
    print(f"{y:<6} | {med_close:>15,.0f} | {avg_atr:>10.2f} pt | {ratio:>24.1f}% | {rec_sl:>26.2f} pt")
print("=" * 105)
