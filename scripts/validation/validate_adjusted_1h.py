import pandas as pd
import numpy as np
import os

def validate_adjusted_vs_daily():
    adjusted_1h_file = r"C:\Users\vinay\tvDownloadOHLC\data\SP_adjusted_1h.csv"
    ref_daily_file = r"C:\Users\vinay\tvDownloadOHLC\data\ES1_1D.parquet"
    
    print("Loading Adjusted 1H CSV...")
    df_1h = pd.read_csv(adjusted_1h_file)
    df_1h['datetime'] = pd.to_datetime(df_1h['datetime'])
    df_1h.set_index('datetime', inplace=True)
    
    print("Aggregating Adjusted 1H to Daily...")
    # Resample to Daily
    df_daily_agg = df_1h.resample('1D').agg({
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'open': 'first',
        'volume': 'sum'
    }).dropna()
    df_daily_agg['date'] = df_daily_agg.index.date
    
    print(f"Aggregated Rows: {len(df_daily_agg)}")
    
    print("Loading Reference Daily Data (Back-Adjusted)...")
    df_ref = pd.read_parquet(ref_daily_file)
    
    # Standardize
    if 'time' in df_ref.columns:
         if pd.api.types.is_numeric_dtype(df_ref['time']):
             df_ref['datetime'] = pd.to_datetime(df_ref['time'], unit='s')
         else:
             df_ref['datetime'] = pd.to_datetime(df_ref['time'])
    elif isinstance(df_ref.index, pd.DatetimeIndex):
        df_ref['datetime'] = df_ref.index
        
    if df_ref['datetime'].dt.tz is not None:
        df_ref['datetime'] = df_ref['datetime'].dt.tz_convert(None)
        
    df_ref['date'] = df_ref['datetime'].dt.date
    df_ref.set_index('date', inplace=True)
    
    print(f"Reference Rows: {len(df_ref)}")
    
    # Validation
    print("\nMatching Dates...")
    common_dates = df_daily_agg['date'].isin(df_ref.index)
    df_matched = df_daily_agg[common_dates].copy()
    
    print(f"Overlapping Days: {len(df_matched)}")
    
    merged = df_matched.join(df_ref, on='date', rsuffix='_ref')
    
    # Diff
    merged['close_diff'] = merged['close'] - merged['close_ref']
    merged['high_diff'] = merged['high'] - merged['high_ref']
    merged['low_diff'] = merged['low'] - merged['low_ref']
    
    print("\n--- Validation Statistics (Absolute Diff) ---")
    print(merged[['close_diff', 'high_diff', 'low_diff']].abs().describe())
    
    # Strict Check
    # Close should be 0.0 because we calculated the shift based on close
    close_exact = (merged['close_diff'].abs() < 0.001).sum()
    print(f"\nExact Close Matches: {close_exact} / {len(merged)} ({close_exact/len(merged):.1%})")
    
    # High/Low might differ slightly if the daily bar had better granularity than our 1H sample?
    # Or if the daily bar High/Low happened outside the range of our ticks (unlikely if ticks are full session)
    # Actually, ticks were 24/7 potentially? SP.csv seemed full session.
    
    print("\n--- Sample diffs ---")
    print(merged[['close', 'close_ref', 'close_diff']].head(5))
    
    if close_exact == len(merged):
        print("\nSUCCESS: All adjusted closes match the reference daily closes exactly.")
    else:
        print("\nWARNING: Some closes do not match.")

if __name__ == "__main__":
    validate_adjusted_vs_daily()
