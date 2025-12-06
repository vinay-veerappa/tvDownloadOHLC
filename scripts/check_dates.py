import pandas as pd
import sys

def check_dates(file_path):
    try:
        df = pd.read_parquet(file_path)
        df.reset_index(inplace=True)
        # Lowercase columns
        df.columns = [c.lower() for c in df.columns]
        
        if 'time' in df.columns:
            # Check if time is datetime or int
            if pd.api.types.is_datetime64_any_dtype(df['time']):
                print(f"Min Date: {df['time'].min()}")
                print(f"Max Date: {df['time'].max()}")
                print("Last 5 rows:")
                print(df['time'].tail().apply(lambda x: f"{x} -> {x.value // 10**9}"))
            else:
                 # Assume unix timestamp if int
                 if pd.api.types.is_integer_dtype(df['time']):
                     # Check if seconds or millis (roughly)
                     # 2024 is ~1.7e9 seconds. 
                     # If values are > 1e12, likely millis
                     if df['time'].max() > 10**11:
                         print("Assuming Milliseconds")
                         print(f"Min Date: {pd.to_datetime(df['time'].min(), unit='ms')}")
                         print(f"Max Date: {pd.to_datetime(df['time'].max(), unit='ms')}")
                     else:
                         print("Assuming Seconds")
                         print(f"Min Date: {pd.to_datetime(df['time'].min(), unit='s')}")
                         print(f"Max Date: {pd.to_datetime(df['time'].max(), unit='s')}")
        elif 'date' in df.columns:
             print(f"Min Date: {df['date'].min()}")
             print(f"Max Date: {df['date'].max()}")
        elif 'datetime' in df.columns:
             print(f"Min Date: {df['datetime'].min()}")
             print(f"Max Date: {df['datetime'].max()}")
        else:
            print("No time/date column found")
            print(df.columns)
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        check_dates(sys.argv[1])
    else:
        print("Usage: python check_dates.py <parquet_file>")
