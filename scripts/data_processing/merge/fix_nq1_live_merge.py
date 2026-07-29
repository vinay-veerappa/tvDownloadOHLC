"""
Fix NQ1_1m.parquet: replace all 2025+ data with live_storage back-adjusted NT8 data.

ROOT CAUSE:
  - The historical 'time' column is corrupted from 2025-01-01 onwards
    (live time in seconds was divided by 1000, losing 3 digits)
  - The 2025+ OHLC values are from the OLD NT8 import, NOT the new back-adjusted data
  - The live_storage has the CORRECT back-adjusted NT8 data (2025+)

FIX:
  1. Keep historical data up to 2024-12-31 23:59 (where 'time' is valid)
  2. Append live_storage data from 2025-01-01 onwards
  3. Convert live 'time' (already unix seconds) — keep as-is
  4. Strip tz from live index to match historical (tz-naive ET)
  5. Ensure columns match: [open, high, low, close, volume, time]
  6. Drop the 'timestamp' column from live (not in historical schema)
  7. Deduplicate by index (keep live data on overlap)
"""
import pandas as pd
import numpy as np
from pathlib import Path
import shutil
import time as time_mod

DATA_DIR = Path("data")
HIST_PATH = DATA_DIR / "NQ1_1m.parquet"
LIVE_PATH = DATA_DIR / "live" / "live_storage_-NQ.parquet"
BACKUP_PATH = DATA_DIR / "backup" / "NQ1_1m_pre_live_merge.parquet"

CUTOFF = pd.Timestamp("2025-01-01")  # Replace everything from this date

print("=" * 80)
print("NQ1_1m.parquet LIVE MERGE FIX")
print("=" * 80)

# 1. Backup
print(f"\n1. Backing up to {BACKUP_PATH}...")
BACKUP_PATH.parent.mkdir(parents=True, exist_ok=True)
shutil.copy(HIST_PATH, BACKUP_PATH)
print(f"   Done ({BACKUP_PATH.stat().st_size / 1e6:.1f} MB)")

# 2. Load historical
print(f"\n2. Loading historical NQ1_1m.parquet...")
t0 = time_mod.time()
df_hist = pd.read_parquet(HIST_PATH)
print(f"   {len(df_hist):,} rows, {df_hist.index.min()} -> {df_hist.index.max()} ({time_mod.time()-t0:.1f}s)")

# 3. Load live
print(f"\n3. Loading live live_storage_-NQ.parquet...")
t0 = time_mod.time()
df_live = pd.read_parquet(LIVE_PATH)
print(f"   {len(df_live):,} rows ({time_mod.time()-t0:.1f}s)")

# 4. Convert live to historical schema
print(f"\n4. Converting live to historical schema...")

# Live 'time' is unix SECONDS, historical 'time' is also unix seconds (pre-2025)
# Live index is tz-aware ET, historical index is tz-naive ET
# Strip tz from live index to match
live_index = pd.to_datetime(df_live["timestamp"], utc=True).dt.tz_convert("America/New_York").dt.tz_localize(None)

df_live_clean = pd.DataFrame({
    "open": df_live["open"].values,
    "high": df_live["high"].values,
    "low": df_live["low"].values,
    "close": df_live["close"].values,
    "volume": df_live["volume"].astype(float).values,
    "time": df_live["time"].values,  # Already unix seconds
}, index=live_index)
df_live_clean.index.name = "datetime"
df_live_clean = df_live_clean.sort_index()

# Remove duplicates in live (keep last)
before = len(df_live_clean)
df_live_clean = df_live_clean[~df_live_clean.index.duplicated(keep="last")]
print(f"   Live deduped: {before} -> {len(df_live_clean)} rows")
print(f"   Live range: {df_live_clean.index.min()} -> {df_live_clean.index.max()}")
print(f"   Live time[0]: {df_live_clean['time'].iloc[0]} (as UTC: {pd.Timestamp(df_live_clean['time'].iloc[0], unit='s', tz='UTC')})")

# 5. Split historical: keep pre-2025, discard 2025+
print(f"\n5. Splitting historical at {CUTOFF}...")
hist_keep = df_hist[df_hist.index < CUTOFF]
print(f"   Keeping: {len(hist_keep):,} rows (up to {hist_keep.index.max()})")
print(f"   Discarding: {len(df_hist) - len(hist_keep):,} rows (from {CUTOFF} onwards)")

# Verify the kept data has valid 'time' column
last_kept_time = hist_keep["time"].iloc[-1]
print(f"   Last kept 'time' value: {last_kept_time} (valid: {last_kept_time > 1_000_000_000})")

# 6. Concatenate
print(f"\n6. Merging historical (pre-2025) + live (2025+)...")
df_merged = pd.concat([hist_keep, df_live_clean])
df_merged = df_merged.sort_index()

# Deduplicate on index (keep live data where overlap exists)
before = len(df_merged)
df_merged = df_merged[~df_merged.index.duplicated(keep="last")]
print(f"   Merged: {before} -> {len(df_merged):,} rows (removed {before - len(df_merged)} duplicates)")

# 7. Validate
print(f"\n7. Validation:")
print(f"   Range: {df_merged.index.min()} -> {df_merged.index.max()}")
print(f"   Cols: {list(df_merged.columns)}")

# Check time column is valid everywhere
time_valid = df_merged["time"] > 1_000_000_000
invalid_count = (~time_valid).sum()
print(f"   'time' column invalid rows: {invalid_count} (should be 0)")

if invalid_count > 0:
    # Show where invalid rows are
    invalid = df_merged[~time_valid]
    print(f"   Invalid rows range: {invalid.index.min()} -> {invalid.index.max()}")
    print(f"   Sample invalid time values: {invalid['time'].head(5).tolist()}")

# Check seam: last pre-2025 bar and first 2025 bar
seam_pre = df_merged.loc[df_merged.index < CUTOFF].iloc[-1]
seam_post = df_merged.loc[df_merged.index >= CUTOFF].iloc[0]
print(f"\n   Seam check:")
print(f"   Last pre-2025: {df_merged.loc[df_merged.index < CUTOFF].index[-1]} close={seam_pre['close']:.2f}")
print(f"   First 2025+:   {df_merged.loc[df_merged.index >= CUTOFF].index[0]} close={seam_post['close']:.2f}")

# Spot check 2025-01-02 09:30 (should now match live)
spot = df_merged.loc["2025-01-02"].between_time("09:30", "09:30")
if not spot.empty:
    print(f"\n   Spot check 2025-01-02 09:30: O={spot['open'].iloc[0]:.2f} C={spot['close'].iloc[0]:.2f} V={spot['volume'].iloc[0]}")
    print(f"   (Should match live: O=22259.75 C=22253.75 V=4590)")

# Spot check 2026-06-04 09:30
spot2 = df_merged.loc["2026-06-04"].between_time("09:30", "09:30")
if not spot2.empty:
    print(f"   Spot check 2026-06-04 09:30: O={spot2['open'].iloc[0]:.2f} C={spot2['close'].iloc[0]:.2f} V={spot2['volume'].iloc[0]}")

# 8. Save
print(f"\n8. Saving to {HIST_PATH}...")
t0 = time_mod.time()
df_merged.to_parquet(HIST_PATH)
print(f"   Saved {len(df_merged):,} rows ({time_mod.time()-t0:.1f}s)")

print(f"\n{'=' * 80}")
print("MERGE COMPLETE")
print(f"{'=' * 80}")
print(f"  Original: {len(df_hist):,} rows")
print(f"  Merged:   {len(df_merged):,} rows")
print(f"  Backup:   {BACKUP_PATH}")