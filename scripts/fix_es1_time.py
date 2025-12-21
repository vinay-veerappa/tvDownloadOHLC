"""Fix ES1_1m parquet file - regenerate missing time column values from datetime index."""
import pandas as pd
import shutil
from datetime import datetime
from pathlib import Path

# Backup first
backup_name = f"ES1_1m.parquet.{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
shutil.copy('data/ES1_1m.parquet', f'data/backup/{backup_name}')
print(f'Backup created: {backup_name}')

# Load and fix
df = pd.read_parquet('data/ES1_1m.parquet')
print(f'Loaded {len(df)} rows')
print(f'NaN time values before: {df["time"].isna().sum()}')

# Regenerate time column from datetime index
df['time'] = df.index.astype('int64') // 10**9

print(f'NaN time values after: {df["time"].isna().sum()}')

# Save
df.to_parquet('data/ES1_1m.parquet')
print('Saved fixed parquet file')
