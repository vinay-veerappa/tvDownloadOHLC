import pandas as pd
import sys

def check_shift():
    print("--- Checking NQ1 for -5h Shift ---")
    try:
        df = pd.read_parquet('data/NQ1_1m.parquet')
        
        # Check Time Column
        if 'time' not in df.columns:
            print("ERROR: 'time' column missing from NQ1.")
            if isinstance(df.index, pd.DatetimeIndex):
                dt = df.index
            else:
                return
        else:
            dt = pd.to_datetime(df['time'], unit='s', utc=True)
            
        # Ensure Aware
        if dt.dt.tz is None:
            dt = dt.dt.tz_localize('UTC')
        
        # Determine NY hour
        dt_ny = dt.dt.tz_convert('America/New_York')
        
        # Filter Sunday
        sunday_data = dt_ny[dt_ny.dt.dayofweek == 6]
        
        print(f"Total Sunday Rows: {len(sunday_data)}")
        if len(sunday_data) > 0:
            print("Sunday Hourly Distribution:")
            print(sunday_data.dt.hour.value_counts().sort_index())
            
            # Diagnostic
            hours = sunday_data.dt.hour.values
            if 13 in hours:
                print("!! DETECTED DATA AT 13:00 EST ON SUNDAY !!")
                print("Likely -5h Shift (Real 18:00 -> 13:00)")
            elif 18 in hours:
                print("found Data at 18:00 EST. Looks Healthy (Starts at Open).")
                
        # Check ES1 for comparison
        print("\n--- Checking ES1 for Shift ---")
        df_es = pd.read_parquet('data/ES1_1m.parquet')
        dt_es = pd.to_datetime(df_es['time'], unit='s', utc=True)
        if dt_es.dt.tz is None: dt_es = dt_es.dt.tz_localize('UTC')
        dt_es_ny = dt_es.dt.tz_convert('America/New_York')
        sunday_es = dt_es_ny[dt_es_ny.dt.dayofweek == 6]
        print(f"ES1 Sunday Rows: {len(sunday_es)}")
        print("ES1 Hourly:")
        print(sunday_es.dt.hour.value_counts().sort_index())

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_shift()
