"""Quick functional test of session_box_status.py — run from repo root."""
import sys
from pathlib import Path
_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import pandas as pd
from scripts.libs_py.profiler.session_box_status import (
    compute_box_status, compute_box_broken, compute_prev_day_shifts,
    get_latest_box_status, get_latest_prev_context
)
from scripts.libs_py.nqstats.sessions import extract_all_sessions
from scripts.utils.fused_data_loader import load_fused_data

# Load live NQ1 data
df = load_fused_data("NQ1", timeframe="1m", require_historical=False)
if df is None or df.empty:
    print("No live data available")
    exit()

# Normalize to ET
if df.index.tz is None:
    df.index = pd.DatetimeIndex(df.index).tz_localize("UTC").tz_convert("US/Eastern")
elif str(df.index.tz) != "US/Eastern":
    df.index = df.index.tz_convert("US/Eastern")

print(f"Loaded {len(df)} bars, {df.index[0]} to {df.index[-1]}")

# Extract session boxes
boxes = extract_all_sessions(df)
box_cols = [c for c in boxes.columns if "box" in c]
print(f"Box columns: {box_cols}")

# Compute status
status_df = compute_box_status(df, boxes)
status_cols = [c for c in status_df.columns]
print(f"Status columns: {status_cols}")

# Get latest
latest = get_latest_box_status(status_df)
print(f"Latest status: {latest}")

# Compute broken
broken_df = compute_box_broken(df, status_df)
broken_cols = [c for c in broken_df.columns]
print(f"Broken columns: {broken_cols}")

# Compute prev-day shifts
prev_df = compute_prev_day_shifts(status_df)
prev_cols = [c for c in prev_df.columns]
print(f"Prev columns: {prev_cols}")

# Get prev context
prev_ctx = get_latest_prev_context(prev_df)
print(f"Prev context: {prev_ctx}")

# Show unique statuses per box
for col in status_cols:
    vals = status_df[col].unique()
    print(f"  {col}: {sorted(vals)}")

print("\nAll OK!")
