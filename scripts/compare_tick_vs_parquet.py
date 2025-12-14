import pandas as pd
import numpy as np
import random

def compare_data():
    csv_file = r"C:\Users\vinay\tvDownloadOHLC\data\SP_1m_verification.csv"
    parquet_file = r"C:\Users\vinay\tvDownloadOHLC\data\ES1_1m.parquet"
    
    print("Loading New CSV...")
    df_new = pd.read_csv(csv_file)
    df_new['datetime'] = pd.to_datetime(df_new['datetime'])
    df_new.set_index('datetime', inplace=True)
    
    print("Loading Existing Parquet...")
    df_old = pd.read_parquet(parquet_file)
    # Check index vs column
    if 'time' in df_old.columns:
        # Assuming 'time' is unix timestamp or datetime
        if pd.api.types.is_numeric_dtype(df_old['time']):
             df_old['datetime'] = pd.to_datetime(df_old['time'], unit='s')
        else:
             df_old['datetime'] = pd.to_datetime(df_old['time'])
        df_old.set_index('datetime', inplace=True)
        
    print("Resampling to 15min...")
    # Resample New
    new_15m = df_new.resample('15min').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last'
    }).dropna()
    
    # Resample Old
    old_15m = df_old.resample('15min').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last'
    }).dropna()
    
    print(f"New Rows: {len(new_15m)}")
    print(f"Old Rows: {len(old_15m)}")
    
    # Align
    common_idx = new_15m.index.intersection(old_15m.index)
    print(f"Overlapping Rows: {len(common_idx)}")
    
    if len(common_idx) == 0:
        print("No overlap found!")
        return

    aligned_new = new_15m.loc[common_idx]
    aligned_old = old_15m.loc[common_idx]
    
    # Compare
    diff = (aligned_new - aligned_old).abs()
    
    print("\n--- Statistics of Differences (Absolute) ---")
    print(diff.describe())
    
    # Random Samples
    print("\n--- 10 Random Samples Comparison ---")
    samples = sorted(random.sample(list(common_idx), min(10, len(common_idx))))
    
    print(f"{'Time':<20} | {'New Open':<10} {'Old Open':<10} | {'New High':<10} {'Old High':<10} | {'New Low':<10} {'Old Low':<10} | {'New Close':<10} {'Old Close':<10}")
    print("-" * 110)
    
    for t in samples:
        r_new = aligned_new.loc[t]
        r_old = aligned_old.loc[t]
        print(f"{str(t):<20} | {r_new.open:<10.2f} {r_old.open:<10.2f} | {r_new.high:<10.2f} {r_old.high:<10.2f} | {r_new.low:<10.2f} {r_old.low:<10.2f} | {r_new.close:<10.2f} {r_old.close:<10.2f}")

if __name__ == "__main__":
    compare_data()
