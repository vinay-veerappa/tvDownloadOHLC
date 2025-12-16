
import pandas as pd
from pathlib import Path
import pytz

def check_2008_gap():
    ticker = "NQ1"
    path = Path(f"data/{ticker}_1m.parquet")
    if not path.exists():
        print(f"{ticker} parquet not found.")
        return

    df = pd.read_parquet(path)
    if df.index.tz is None:
        df.index = df.index.tz_localize('UTC').tz_convert('US/Eastern')
    else:
        df.index = df.index.tz_convert('US/Eastern')

    # Check 2008
    start_2008 = pd.Timestamp("2008-01-01", tz="US/Eastern")
    end_2008 = pd.Timestamp("2008-12-31", tz="US/Eastern")
    
    df_2008 = df[(df.index >= start_2008) & (df.index <= end_2008)]
    
    print(f"--- {ticker} 2008 Data Analysis ---")
    print(f"Total Rows in 2008: {len(df_2008)}")
    
    if len(df_2008) > 0:
        print(f"Range: {df_2008.index.min()} to {df_2008.index.max()}")
        
        # Check for large gaps > 1 day
        df_2008 = df_2008.sort_index()
        diffs = df_2008.index.to_series().diff()
        gaps = diffs[diffs > pd.Timedelta(days=2)]
        
        if len(gaps) > 0:
            print("\nSignificant Gaps (> 2 days) in 2008:")
            for date, delta in gaps.items():
                print(f"  Gap ending {date}: {delta}")
        else:
            print("\nNo gaps > 2 days found in 2008.")
    else:
        print("No data found for 2008.")

if __name__ == "__main__":
    check_2008_gap()
