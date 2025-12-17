import pandas as pd
import numpy as np

def debug_dates():
    csv_file = r"C:\Users\vinay\tvDownloadOHLC\data\SP_1m_verification.csv"
    parquet_file = r"C:\Users\vinay\tvDownloadOHLC\data\ES1_1m.parquet"
    
    print("Loading New CSV...")
    df_new = pd.read_csv(csv_file)
    df_new['datetime'] = pd.to_datetime(df_new['datetime'])
    
    print("Loading Existing Parquet...")
    df_old = pd.read_parquet(parquet_file)
    
    print(f"Old Columns: {df_old.columns}")
    print(f"Old Index: {df_old.index.name}")
    
    # Attempt to fix
    if 'time' in df_old.columns:
        if pd.api.types.is_numeric_dtype(df_old['time']):
             df_old['datetime'] = pd.to_datetime(df_old['time'], unit='s')
        else:
             df_old['datetime'] = pd.to_datetime(df_old['time'])
    elif isinstance(df_old.index, pd.DatetimeIndex):
        df_old['datetime'] = df_old.index
        
    print("\n--- Date Ranges ---")
    print(f"New Data (Tick): {df_new['datetime'].min()} to {df_new['datetime'].max()}")
    
    if 'datetime' in df_old.columns:
        print(f"Old Data (ES1):  {df_old['datetime'].min()} to {df_old['datetime'].max()}")
    else:
        print("Could not find datetime column in Old Data.")

if __name__ == "__main__":
    debug_dates()
