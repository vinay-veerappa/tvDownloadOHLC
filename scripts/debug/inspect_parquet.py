
import pandas as pd
import datetime
import pytz
import os

# Try NQ1 first, then ES1
PARQUET_FILE = r"c:\Users\vinay\tvDownloadOHLC\data\NQ1_1m.parquet"
if not os.path.exists(PARQUET_FILE):
    print(f"{PARQUET_FILE} not found, checking ES1...")
    PARQUET_FILE = r"c:\Users\vinay\tvDownloadOHLC\data\ES1_1m.parquet"

def check_parquet():
    if not os.path.exists(PARQUET_FILE):
        print(f"No parquet file found at {PARQUET_FILE}")
        return

    print(f"Reading {PARQUET_FILE}...")
    try:
        df = pd.read_parquet(PARQUET_FILE)
    except Exception as e:
        print(f"Error reading parquet: {e}")
        return

    # Check columns
    print(f"Columns: {df.columns}")
    
    # Assume 'time' column exists and is either int (Unix) or datetime
    if 'time' not in df.columns:
        if 'date' in df.columns:
            df['time'] = df['date'] # Handle potential naming difference
        else:
            print("No 'time' column found.")
            return

    # Convert to datetime if it's unix timestamp (check first value)
    first_val = df['time'].iloc[0]
    is_unix = False
    
    # Check if it's already datetime
    if pd.api.types.is_datetime64_any_dtype(df['time']):
        print("Detected Datetime column.")
        df['dt_utc'] = df['time'].dt.tz_localize('UTC') if df['time'].dt.tz is None else df['time']
    else:
        # Numeric - try to guess unit
        # 2025 in seconds ~ 1.7e9
        # 2025 in ms ~ 1.7e12
        # 2025 in ns ~ 1.7e18
        val = float(first_val)
        unit = 's'
        if val > 1e16: unit = 'ns'
        elif val > 1e13: unit = 'us'
        elif val > 1e10: unit = 'ms'
        
        print(f"Detected Numeric timestamps. Guessing unit: {unit} (Value: {val})")
        df['dt_utc'] = pd.to_datetime(df['time'], unit=unit, utc=True)

    est = pytz.timezone('US/Eastern')
    df['dt_est'] = df['dt_utc'].dt.tz_convert(est)
    
    # Filter for Nov 24, 2025
    target_date = datetime.date(2025, 11, 24)
    day_data = df[df['dt_est'].dt.date == target_date]
    
    print(f"Found {len(day_data)} rows for {target_date}")
    
    if len(day_data) == 0:
        # Print range
        print("\nDate not found. Range of file:")
        print(f"Start: {df['dt_utc'].min()} | End: {df['dt_utc'].max()}")
        # convert to EST
        print(f"Start EST: {df['dt_est'].min()} | End EST: {df['dt_est'].max()}")
        return

    # Filter for pertinent times (12:00 EST to 19:00 EST)
    # If the user sees it at 13:00 EST, that's pertinent.
    # If the real gap is 17:00-18:00 EST, that's pertinent.
    
    mask = (day_data['dt_est'].dt.hour >= 12) & (day_data['dt_est'].dt.hour <= 19)
    subset = day_data[mask]
    
    print("\n--- Parquet Data (12:00 - 19:00 EST) ---")
    for idx, row in subset.iterrows():
        # Print every 60th row to avoid spam, unless it's the gap edge
        h = row['dt_est'].hour
        m = row['dt_est'].minute
        
        should_print = False
        if 16 <= h <= 18: should_print = True # Detailed print around gap
        elif m == 0: should_print = True # Hourly otherwise
        
        if should_print:
            print(f"Unix: {row['time']} | UTC: {row['dt_utc']} | EST: {row['dt_est']} | Price: {row['close']}")

if __name__ == "__main__":
    check_parquet()
