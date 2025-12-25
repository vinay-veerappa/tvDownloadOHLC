import pandas as pd

df = pd.read_parquet('data/ES1_1m.parquet')

# Filter to 2025
df_2025 = df.loc['2025-01-01':]

print(f"ES1 2025 data: {len(df_2025):,} rows")
print(f"Date range: {df_2025.index.min()} to {df_2025.index.max()}")

# Find ALL large price jumps (> 80 points in 1 minute is abnormal)
diffs = df_2025['close'].diff().abs()
anomalies = diffs[diffs > 80]

print(f"\n=== Price Anomalies (>80 pts jump): {len(anomalies)} ===")
for ts, val in anomalies.items():
    price = df_2025.loc[ts, 'close']
    prev_idx = df_2025.index.get_loc(ts) - 1
    if prev_idx >= 0:
        prev_price = df_2025.iloc[prev_idx]['close']
        print(f"  {ts}: {prev_price:.2f} -> {price:.2f} (Δ{val:.2f})")
