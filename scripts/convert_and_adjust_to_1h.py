import pandas as pd
import numpy as np
import os

def process_adjustment():
    # Input Files
    raw_1m_file = r"C:\Users\vinay\tvDownloadOHLC\data\SP_1m_verification.csv"
    ref_daily_file = r"C:\Users\vinay\tvDownloadOHLC\data\ES1_1D.parquet"
    output_file_1h = r"C:\Users\vinay\tvDownloadOHLC\data\SP_adjusted_1h.csv"
    
    print("Loading Raw 1m Data...")
    df_raw = pd.read_csv(raw_1m_file)
    df_raw['datetime'] = pd.to_datetime(df_raw['datetime'])
    df_raw.set_index('datetime', inplace=True)
    
    # Store Raw 'date' for merging
    df_raw['date'] = df_raw.index.date
    
    print("Aggregating Raw to Daily for Sync...")
    # Agg to daily to find the "Raw Close"
    raw_daily = df_raw.resample('1D').agg({
        'close': 'last'
    }).dropna()
    raw_daily['date'] = raw_daily.index.date
    # raw_daily now has [date, close] where close is raw
    
    print("Loading Reference Daily Data (Back-Adjusted)...")
    df_ref = pd.read_parquet(ref_daily_file)
    
    # Standardize Reference Datetime
    if 'time' in df_ref.columns:
        if pd.api.types.is_numeric_dtype(df_ref['time']):
             df_ref['datetime'] = pd.to_datetime(df_ref['time'], unit='s')
        else:
             df_ref['datetime'] = pd.to_datetime(df_ref['time'])
    elif isinstance(df_ref.index, pd.DatetimeIndex):
        df_ref['datetime'] = df_ref.index
        
    # Localize removal
    if df_ref['datetime'].dt.tz is not None:
        df_ref['datetime'] = df_ref['datetime'].dt.tz_convert(None)
        
    df_ref['date'] = df_ref['datetime'].dt.date
    
    # We only need reference close
    ref_daily = df_ref[['date', 'close']].copy()
    ref_daily.rename(columns={'close': 'ref_close'}, inplace=True)
    
    print(f"Syncing {len(raw_daily)} raw days with Reference...")
    
    # Merge Raw Daily + Reference Daily
    # This gives us: date, raw_close, ref_close
    merged_daily = pd.merge(raw_daily, ref_daily, on='date', how='inner')
    
    # Calculate OFFSET (Delta)
    # Ref = Raw + Delta  => Delta = Ref - Raw
    merged_daily['delta'] = merged_daily['ref_close'] - merged_daily['close']
    
    print(f"Matched Days: {len(merged_daily)}")
    print(f"Avg Adjustment: {merged_daily['delta'].mean():.2f}")
    
    # Now merge 'delta' back to intraday dataframe
    # Using merge on 'date' column
    print("Applying Adjustment to Intraday Data...")
    
    # To merge efficiently, ensure date type matches
    # df_raw has 'date' column (object or date)
    # merged_daily has 'date'
    
    # We need to broadcast the daily delta to all 1m bars of that day
    # Reset index to preserve datetime
    df_raw.reset_index(inplace=True) 
    
    df_adjusted = pd.merge(df_raw, merged_daily[['date', 'delta']], on='date', how='inner')
    
    # Apply Delta
    cols_to_adjust = ['open', 'high', 'low', 'close']
    for col in cols_to_adjust:
        df_adjusted[col] = df_adjusted[col] + df_adjusted['delta']
        
    # Restore Index
    df_adjusted.set_index('datetime', inplace=True)
    
    print("Resampling to 1 Hour...")
    # Resample
    df_1h = df_adjusted.resample('1h').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }).dropna()
    
    # Cleanup columns
    final_output = df_1h[['open', 'high', 'low', 'close', 'volume']]
    
    print(f"Saving {len(final_output)} 1H bars to {output_file_1h}...")
    final_output.to_csv(output_file_1h)
    
    print("Preview:")
    print(final_output.head())
    print("\nTail:")
    print(final_output.tail())

if __name__ == "__main__":
    process_adjustment()
