
import pandas as pd
from pathlib import Path
import pytz

def check_gap(ticker):
    path = Path(f"data/{ticker}_1m.parquet")
    if not path.exists():
        print(f"{ticker}: Not found")
        return

    df = pd.read_parquet(path)
    if df.index.tz is None:
        df.index = df.index.tz_localize('UTC').tz_convert('US/Eastern')
    else:
        df.index = df.index.tz_convert('US/Eastern')

    # Filter for Hour 15 (15:00-15:59)
    df_15 = df[df.index.hour == 15]
    count_15 = len(df_15)
    
    # Filter for Hour 14 and 16 for context
    count_14 = len(df[df.index.hour == 14])
    count_16 = len(df[df.index.hour == 16])
    
    print(f"--- {ticker} Rows ---")
    print(f"  Hour 14: {count_14}")
    print(f"  Hour 15: {count_15}")
    print(f"  Hour 16: {count_16}")
    
    if count_15 > 0:
        print("  Sample 15:XX timestamps:")
        print(df_15.index[:5])

for t in ["ES1", "RTY1", "NQ1"]:
    check_gap(t)
