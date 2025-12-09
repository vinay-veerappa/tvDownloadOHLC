import pandas as pd
from api.services.data_loader import load_parquet

def check_parquet():
    print("Loading NQ1_1m.parquet...")
    df = load_parquet("NQ1", "1m")
    if df is None:
        print("Could not load dataframe.")
        return

    print(f"Loaded {len(df)} rows.")
    
    # Check last row
    last_row = df.iloc[-1]
    first_row = df.iloc[0]
    
    print(f"First timestamp (unix): {first_row['time']}")
    print(f"Last timestamp (unix): {last_row['time']}")
    
    # Convert to readable
    print(f"First Date: {pd.to_datetime(first_row['time'], unit='s')}")
    print(f"Last Date: {pd.to_datetime(last_row['time'], unit='s')}")

if __name__ == "__main__":
    check_parquet()
