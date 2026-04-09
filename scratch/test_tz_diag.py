import pandas as pd
import duckdb
from scripts.edgeful.data_loader import load_bars_duckdb
import zoneinfo

ET_TZ = zoneinfo.ZoneInfo("US/Eastern")

def test_tz():
    print("--- Testing Timezone Conversion ---")
    # Load a single day for index ES1
    df = load_bars_duckdb("ES1", start_date="2024-03-01", end_date="2024-03-01")
    if df.empty:
        print("No data found.")
        return
        
    print(f"Sample row:\n{df.head(1).to_string()}")
    
    # Check if dt_et matches the hour_et/minute_et
    sample = df.iloc[0]
    dt_et = sample['dt_et']
    hour_et = sample['hour_et']
    minute_et = sample['minute_et']
    
    print(f"Timestamp: {dt_et}")
    print(f"Extracted Hour/Min: {hour_et}:{minute_et}")
    
    # If dt_et is '2024-03-01 00:00:00-05:00' but hour_et is 5 (UTC hour), we have a shift.
    # We want dt_et.hour == hour_et
    if dt_et.hour == hour_et:
        print("✅ Timezone alignment correct.")
    else:
        print(f"❌ Timezone alignment MISMATCH: TS Hour={dt_et.hour}, SQL Hour={hour_et}")

if __name__ == "__main__":
    test_tz()
