
import pandas as pd
from pathlib import Path

FILE_PATH = Path("data/NQ1_1m.parquet")

def convert():
    print(f"Loading {FILE_PATH}...")
    df = pd.read_parquet(FILE_PATH)
    
    current_tz = df.index.tz
    print(f"Current Timezone: {current_tz}")
    
    if str(current_tz) == "America/New_York":
        print("Converting NY -> UTC -> Naive...")
        # Convert to UTC
        df.index = df.index.tz_convert("UTC")
        # Strip TZ (Naive)
        df.index = df.index.tz_localize(None)
        
        # Save
        print("Saving...")
        df.to_parquet(FILE_PATH)
        print("✅ NQ1_1m.parquet is now Naive UTC.")
        
    elif current_tz is None:
        print("Already Naive. Verifying random sample...")
        print(df.tail(3))
        # If naive, assume it IS UTC (unless it's NY-Naive which is dangerous)
        # Given our recent merge converted User->UTC->NY, if it was NY it would be aware.
        # If it says Naive, it's likely already correct or we need deep inspection.
        # But earlier log said "Adjusting Timezone: New(None) -> Old(America/New_York)", so it WAS NY.
        pass
    else:
        print(f"Unexpected TZ: {current_tz}. Converting to UTC -> Naive.")
        df.index = df.index.tz_convert("UTC")
        df.index = df.index.tz_localize(None)
        df.to_parquet(FILE_PATH)
        print("✅ NQ1_1m.parquet corrected to Naive UTC.")

if __name__ == "__main__":
    convert()
