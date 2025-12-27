
import pandas as pd
from pathlib import Path

EXISTING_PARQUET = Path("data/ES1_1m.parquet")
try:
    df = pd.read_parquet(EXISTING_PARQUET)
    print(f"Existing Parquet Timezone: {df.index.tz}")
    print(f"Sample Index: {df.index[0]}")
except Exception as e:
    print(f"Error reading parquet: {e}")
