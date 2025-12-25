"""
Merge NinjaTrader ES data - fills in missing July 2025 gap
Only adds new/updated data, doesn't duplicate existing rows
"""

import pandas as pd
from pathlib import Path
import shutil
from datetime import datetime

# Paths
NEW_CSV = Path("data/NinjaTrader/24Dec2025/ES Thursday 857.csv")
EXISTING_PARQUET = Path("data/ES1_1m.parquet")
BACKUP_PARQUET = Path(f"data/backup/ES1_1m_pre_merge_{datetime.now().strftime('%Y%m%d_%H%M%S')}.parquet")
OUTPUT_PARQUET = Path("data/ES1_1m.parquet")

print("=" * 60)
print("ES 1m Data Merge Script")
print("=" * 60)

# 1. Load existing parquet
print("\n1. Loading existing parquet...")
existing_df = pd.read_parquet(EXISTING_PARQUET)
print(f"   Existing rows: {len(existing_df):,}")
print(f"   Date range: {existing_df.index.min()} to {existing_df.index.max()}")

# 2. Load new CSV
print("\n2. Loading new NinjaTrader CSV...")
new_df = pd.read_csv(NEW_CSV, usecols=['Date', 'Time', 'Open', 'High', 'Low', 'Close', 'Volume'])

# Parse datetime and set timezone
new_df['Datetime'] = pd.to_datetime(new_df['Date'] + ' ' + new_df['Time'], format='%m/%d/%Y %H:%M:%S')
# NinjaTrader exports in Eastern Time
new_df['Datetime'] = new_df['Datetime'].dt.tz_localize('America/New_York')
new_df = new_df.set_index('Datetime')
new_df = new_df[['Open', 'High', 'Low', 'Close', 'Volume']]
new_df.columns = ['open', 'high', 'low', 'close', 'volume']

# Add 'time' column (Unix timestamp)
new_df['time'] = new_df.index.astype('int64') // 10**9

print(f"   New CSV rows: {len(new_df):,}")
print(f"   Date range: {new_df.index.min()} to {new_df.index.max()}")

# 3. Identify new rows (not in existing)
print("\n3. Finding new rows...")
new_indices = new_df.index.difference(existing_df.index)
new_rows = new_df.loc[new_indices]
print(f"   New rows to add: {len(new_rows):,}")

if len(new_rows) > 0:
    print(f"   New data range: {new_rows.index.min()} to {new_rows.index.max()}")
    
    # Show by month
    print("\n   New rows by month:")
    monthly = new_rows.groupby(new_rows.index.to_period('M')).size()
    for period, count in monthly.items():
        print(f"   {period}: {count:,} rows")
else:
    print("   No new rows found!")
    exit(0)

# 4. Backup existing
print("\n4. Creating backup...")
BACKUP_PARQUET.parent.mkdir(parents=True, exist_ok=True)
shutil.copy(EXISTING_PARQUET, BACKUP_PARQUET)
print(f"   Backed up to: {BACKUP_PARQUET}")

# 5. Merge
print("\n5. Merging data...")
merged_df = pd.concat([existing_df, new_rows])
merged_df = merged_df.sort_index()
merged_df = merged_df[~merged_df.index.duplicated(keep='last')]  # Remove any duplicates
print(f"   Merged rows: {len(merged_df):,}")

# 6. Save
print("\n6. Saving merged parquet...")
merged_df.to_parquet(OUTPUT_PARQUET)
print(f"   Saved to: {OUTPUT_PARQUET}")

# 7. Verify
print("\n7. Verification...")
verify_df = pd.read_parquet(OUTPUT_PARQUET)
print(f"   Final rows: {len(verify_df):,}")
print(f"   Date range: {verify_df.index.min()} to {verify_df.index.max()}")

# Check July 2025 specifically
jul_mask = (verify_df.index >= '2025-07-01') & (verify_df.index <= '2025-07-31')
jul_count = len(verify_df[jul_mask])
print(f"   July 2025 rows: {jul_count:,}")

print("\n" + "=" * 60)
print("Merge complete!")
print("=" * 60)
