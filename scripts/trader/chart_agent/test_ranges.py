"""Test new session ranges."""
import pandas as pd
from zoneinfo import ZoneInfo
from scripts.trader.signals.session_ranges import compute_all_session_ranges
from scripts.utils.fused_data_loader import load_fused_data

et_tz = ZoneInfo("America/New_York")
df = load_fused_data("ES1", timeframe="1m", require_historical=False)
if df.index.tz is None:
    df.index = pd.DatetimeIndex(df.index).tz_localize("UTC").tz_convert("US/Eastern")
else:
    df.index = df.index.tz_convert("US/Eastern")

target = pd.Timestamp("2026-08-04", tz="US/Eastern")
ranges = compute_all_session_ranges(df, target, et_tz)

for name, r in ranges.items():
    if r:
        h = r.get("high", 0)
        l = r.get("low", 0)
        mid = r.get("mid", 0)
        rng = r.get("range", 0)
        print(f"{name:12s}  H={h:8.2f}  L={l:8.2f}  Mid={mid:8.2f}  Range={rng:6.2f}")
    else:
        print(f"{name:12s}  (no data)")