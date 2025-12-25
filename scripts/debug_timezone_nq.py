
import pandas as pd
from pathlib import Path

NQ_PARQUET = Path("data/NQ1_1m.parquet")
try:
    df = pd.read_parquet(NQ_PARQUET)
    print(f"NQ Parquet Timezone: {df.index.tz}")
    print(f"Sample Index (First): {df.index[0]}")
    print(f"Sample Index (Last): {df.index[-1]}")
except Exception as e:
    print(f"Error reading NQ parquet: {e}")
