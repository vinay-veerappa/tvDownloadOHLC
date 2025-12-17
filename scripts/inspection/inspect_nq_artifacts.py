import pandas as pd
from pathlib import Path

def inspect_artifacts():
    path = Path("data/NQ1_1m.parquet")
    print(f"Loading {path}...")
    df = pd.read_parquet(path)
    
    # Filter for Dec 2025
    start_date = "2025-12-09"
    end_date = "2025-12-12"
    
    # Ensure index is datetime
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index) # Localize? UTC?
        
    mask = (df.index >= pd.Timestamp(start_date, tz=df.index.tz)) & \
           (df.index <= pd.Timestamp(end_date, tz=df.index.tz))
    
    subset = df[mask].copy()
    print(f"Subset {start_date} to {end_date}: {len(subset)} rows")
    
    if len(subset) == 0:
        print("No data in range!")
        return

    # Check for price outliers (rolling median deviation)
    subset['close_rolling'] = subset['close'].rolling(window=10, center=True).median()
    subset['diff'] = (subset['close'] - subset['close_rolling']).abs()
    
    # Identify outliers > 50 points difference from rolling median
    outliers = subset[subset['diff'] > 20]
    
    if len(outliers) > 0:
        print(f"\nPotential Outliers (>20 pts deviation): {len(outliers)}")
        print(outliers[['open', 'high', 'low', 'close', 'diff']].head(20))
        
        # Check specific suspect times from screenshot (approx)
        # Dec 10 03:00?
    else:
        print("No obvious price outliers found via rolling median.")

    # Check for duplicate timestamps (though index should be unique)
    print(f"\nDuplicate Index check: {subset.index.duplicated().sum()}")
    
    # Print sample around Dec 10 01:00 to 05:00
    sample_start = pd.Timestamp("2025-12-10 00:00", tz=df.index.tz)
    sample_end = pd.Timestamp("2025-12-10 06:00", tz=df.index.tz)
    
    sample = subset[(subset.index >= sample_start) & (subset.index <= sample_end)]
    if len(sample) > 0:
        print(f"\nSample Data {sample_start} - {sample_end}:")
        # Print spread out rows
        print(sample[['open', 'high', 'low', 'close']].iloc[::60]) # Every hour ish

if __name__ == "__main__":
    inspect_artifacts()
