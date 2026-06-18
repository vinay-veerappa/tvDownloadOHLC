import pandas as pd
import os
import glob

LIVE_DIR = r"c:\Users\vinay\tvDownloadOHLC\data\live"

def check_june_data():
    files = glob.glob(os.path.join(LIVE_DIR, "live_storage_*.parquet"))
    for f in files:
        symbol = os.path.basename(f).replace("live_storage_", "").replace(".parquet", "")
        print(f"\n--- Checking {symbol} ---")
        try:
            df = pd.read_parquet(f)
            df['timestamp'] = pd.to_datetime(df['time'], unit='ms')
            
            # Filter for June 2026
            june_df = df[(df['timestamp'].dt.month == 6) & (df['timestamp'].dt.year == 2026)]
            
            if june_df.empty:
                print("No data found for June 2026.")
            else:
                # Group by date and count rows
                counts = june_df.groupby(june_df['timestamp'].dt.date).size()
                print("Daily row counts for June 2026:")
                print(counts)
                
                # Check for expected trading days (Monday - Friday)
                start_date = pd.to_datetime('2026-06-01').date()
                end_date = pd.to_datetime('2026-06-18').date() # up to today
                
                expected_days = pd.bdate_range(start=start_date, end=end_date).date
                missing_days = [day for day in expected_days if day not in counts.index]
                if missing_days:
                    print("Missing expected trading days in June:")
                    for day in missing_days:
                        print(f"  - {day}")
                else:
                    print("No missing trading days detected so far in June.")
        except Exception as e:
            print(f"Error reading {symbol}: {e}")

if __name__ == "__main__":
    check_june_data()
