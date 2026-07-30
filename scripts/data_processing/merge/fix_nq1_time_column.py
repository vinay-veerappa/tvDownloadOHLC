"""
Fix the 'time' column in NQ1_1m.parquet — the live data was stored with
time in MILLISECONDS but the historical convention is SECONDS.
Convert post-2025 'time' from ms to seconds.
"""
import pandas as pd
from pathlib import Path

HIST_PATH = Path("data/NQ1_1m.parquet")

print("Loading NQ1_1m.parquet...")
df = pd.read_parquet(HIST_PATH)

# Check the issue
pre = df.loc[df.index < "2025-01-01", "time"]
post = df.loc[df.index >= "2025-01-01", "time"]

print(f"Pre-2025 time: min={pre.min()}, max={pre.max()} (SECONDS)")
print(f"Post-2025 time: min={post.min()}, max={post.max()} (MILLISECONDS — WRONG)")

# Convert post-2025 from ms to seconds
mask = df.index >= "2025-01-01"
df.loc[mask, "time"] = df.loc[mask, "time"] / 1000.0

# Verify
post_fixed = df.loc[df.index >= "2025-01-01", "time"]
print(f"\nPost-fix post-2025 time: min={post_fixed.min()}, max={post_fixed.max()}")
print(f"  As seconds: {pd.Timestamp(post_fixed.iloc[0], unit='s')}")
print(f"  Expected:   2025-01-01 23:00:00 (UTC) = 2025-01-01 18:00:00 ET")

# Verify continuity at seam
pre_last = df.loc[df.index < "2025-01-01", "time"].iloc[-1]
post_first = df.loc[df.index >= "2025-01-01", "time"].iloc[0]
print(f"\nSeam: pre_last={pre_last} ({pd.Timestamp(pre_last, unit='s')})")
print(f"      post_first={post_first} ({pd.Timestamp(post_first, unit='s')})")
print(f"      Gap: {post_first - pre_last} seconds ({(post_first - pre_last)/3600:.1f} hours)")

# Check all time values are now valid (> 1 billion for post-2001 timestamps)
all_valid = (df["time"] > 1_000_000_000).all()
print(f"\nAll time values valid: {all_valid}")

# Also check the index matches the time column for a few rows
print(f"\nSpot checks (index vs time as UTC):")
for i in [0, len(df)//2, -1]:
    idx = df.index[i]
    t = df["time"].iloc[i]
    t_as_utc = pd.Timestamp(t, unit="s", tz="UTC")
    t_as_et = t_as_utc.tz_convert("America/New_York")
    print(f"  index={idx} time_sec={t} -> UTC={t_as_utc} ET={t_as_et}")

print(f"\nSaving fixed NQ1_1m.parquet...")
df.to_parquet(HIST_PATH)
print(f"Done. {len(df):,} rows.")