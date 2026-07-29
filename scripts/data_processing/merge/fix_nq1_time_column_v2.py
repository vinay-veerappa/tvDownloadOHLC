"""
The live time column has MIXED units — some rows are seconds, some are milliseconds.
Need to detect and normalize: if time > 1e12, it's ms; if > 1e9, it's seconds.
"""
import pandas as pd
import numpy as np
from pathlib import Path

HIST_PATH = Path("data/NQ1_1m.parquet")

print("Loading NQ1_1m.parquet...")
df = pd.read_parquet(HIST_PATH)

# Check the post-2025 time values
post = df.loc[df.index >= "2025-01-01", "time"]
print(f"Post-2025 time stats:")
print(f"  min={post.min()}, max={post.max()}")
print(f"  Values > 1e12 (ms): {(post > 1e12).sum()} rows")
print(f"  Values > 1e9 and < 1e12 (sec): {((post > 1e9) & (post < 1e12)).sum()} rows")
print(f"  Values < 1e9 (corrupted): {(post < 1e9).sum()} rows")

# The issue: some live rows have time in ms, some in seconds
# Fix: convert ALL post-2025 time values to seconds
# If value > 1e12, divide by 1000 (ms -> sec)
# If value > 1e9, keep as-is (already sec)
# If value < 1e9, recompute from index

mask = df.index >= "2025-01-01"
post_times = df.loc[mask, "time"].copy()

# Convert ms to sec
ms_mask = post_times > 1e12
post_times[ms_mask] = post_times[ms_mask] / 1000.0
print(f"\nConverted {ms_mask.sum()} ms rows to seconds")

# Check for corrupted values (< 1e9) — recompute from index
corrupt_mask = post_times < 1e9
print(f"Corrupted values (< 1e9): {corrupt_mask.sum()} rows")

if corrupt_mask.sum() > 0:
    # Recompute from index: the index is ET naive, convert to UTC seconds
    corrupt_idx = post_times[corrupt_mask].index
    # ET is UTC-5 (EST) or UTC-4 (EDT). The 'time' column stores UTC seconds.
    # But looking at pre-2025: index=2006-01-05 13:58:00 (ET) time=1136469480
    # 1136469480 as UTC = 2006-01-05 13:58:00 UTC
    # So the 'time' column stores the index as if it were UTC (not ET!)
    # This means time = index.view('int64') // 1e9 approximately
    # Actually: pd.Timestamp('2006-01-05 13:58:00').timestamp() = 1136469480
    # But that treats the naive index as UTC. So 'time' = index treated as UTC.
    
    # Recompute: treat naive ET index as UTC and get unix seconds
    for ts in corrupt_idx[:5]:
        expected = int(pd.Timestamp(ts).timestamp())
        print(f"  {ts} -> recomputed time = {expected}")
    
    # Vectorized: convert naive datetime to unix seconds (treating as UTC)
    post_times[corrupt_mask] = corrupt_idx.astype('int64') // 1_000_000_000

# Write back
df.loc[mask, "time"] = post_times

# Verify
print(f"\nPost-fix verification:")
post_fixed = df.loc[mask, "time"]
print(f"  min={post_fixed.min()}, max={post_fixed.max()}")
print(f"  All > 1e9: {(post_fixed > 1e9).all()}")

# Check continuity: the 'time' should increase by 60 seconds per bar
# Check a sample day
sample = df.loc["2026-06-04"].head(5)
print(f"\n  2026-06-04 first 5 bars:")
for i in range(len(sample)):
    print(f"    index={sample.index[i]} time={sample['time'].iloc[i]} diff={sample['time'].iloc[i] - sample['time'].iloc[0]:.0f}")

# Check seam
pre_last = df.loc[df.index < "2025-01-01", "time"].iloc[-1]
post_first = df.loc[df.index >= "2025-01-01", "time"].iloc[0]
print(f"\n  Seam: pre_last={pre_last} post_first={post_first} gap={post_first-pre_last:.0f}s")

# Final validation: all time values valid
all_valid = (df["time"] > 1_000_000_000).all()
print(f"  All time valid: {all_valid}")

# Check that time matches index (treating index as UTC)
print(f"\n  Index vs time check (should match when treating index as UTC):")
for i in [0, -1000000, -1]:
    idx = df.index[i]
    t = df["time"].iloc[i]
    t_ts = pd.Timestamp(t, unit="s")
    print(f"    index={idx} time={t} time_as_ts={t_ts}")

print(f"\nSaving...")
df.to_parquet(HIST_PATH)
print(f"Done. {len(df):,} rows.")