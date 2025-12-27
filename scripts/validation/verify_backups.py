
import pandas as pd
from pathlib import Path

BACKUP_DIR = Path("data/backup")

files_to_check = [
    "ES1_1m.parquet.20251215_174849.bak",
    "NQ1_1m.parquet.20251216_103757.bak"
]

print(f"{'File':<40} | {'Timezone':<20}")
print("-" * 65)

for fname in files_to_check:
    p_file = BACKUP_DIR / fname
    if p_file.exists():
        try:
            df = pd.read_parquet(p_file)
            tz = str(df.index.tz) if df.index.tz else "None (Naive)"
            print(f"{fname:<40} | {tz:<20}")
        except Exception as e:
            print(f"{fname:<40} | Error: {e}")
    else:
        print(f"{fname:<40} | Not Found")
