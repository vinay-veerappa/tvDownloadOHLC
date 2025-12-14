import pandas as pd
import numpy as np

def validate_daily_spx():
    csv_file = r"C:\Users\vinay\tvDownloadOHLC\data\SP_1m_verification.csv"
    # Changed target to SPX (Cash Index)
    parquet_file = r"C:\Users\vinay\tvDownloadOHLC\data\SPX_1D.parquet"
    
    print("Loading 1m CSV...")
    df_1m = pd.read_csv(csv_file)
    df_1m['datetime'] = pd.to_datetime(df_1m['datetime'])
    df_1m.set_index('datetime', inplace=True)
    
    print("Aggregating 1m to Daily...")
    df_daily_agg = df_1m.resample('1D').agg({
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'open': 'first',
        'volume': 'sum'
    }).dropna()
    df_daily_agg['date'] = df_daily_agg.index.date
    
    print(f"Aggregated Rows: {len(df_daily_agg)}")
    
    print(f"Loading SPX Parquet: {parquet_file}")
    if not os.path.exists(parquet_file):
        print("SPX Parquet not found!")
        return

    df_old = pd.read_parquet(parquet_file)
    
    if 'time' in df_old.columns:
        if pd.api.types.is_numeric_dtype(df_old['time']):
             df_old['datetime'] = pd.to_datetime(df_old['time'], unit='s')
        else:
             df_old['datetime'] = pd.to_datetime(df_old['time'])
    elif isinstance(df_old.index, pd.DatetimeIndex):
        df_old['datetime'] = df_old.index
        
    if df_old['datetime'].dt.tz is not None:
        df_old['datetime'] = df_old['datetime'].dt.tz_convert(None)
        
    df_old['date'] = df_old['datetime'].dt.date
    df_old.set_index('date', inplace=True)
    
    print(f"Reference Rows: {len(df_old)}")
    
    # Comparison
    common_dates = df_daily_agg['date'].isin(df_old.index)
    df_matched = df_daily_agg[common_dates].copy()
    
    merged = df_matched.join(df_old, on='date', rsuffix='_ref')
    
    merged['close_diff'] = merged['close'] - merged['close_ref']
    
    print("\n--- Validation Statistics (Absolute Diff) ---")
    print(merged['close_diff'].abs().describe())
    
    close_ok = (merged['close_diff'].abs() < 2.0).sum() # 2 points tolerance for Index
    print(f"\nClose Price Matches (< 2.0 diff): {close_ok} / {len(merged)} ({close_ok/len(merged):.1%})")
    
    print("\n--- Sample Mismatches ---")
    bad = merged.nlargest(10, 'close_diff')
    for idx, row in bad.iterrows():
        print(f"{row['date']}: Own Close={row['close']:.2f}, Ref={row['close_ref']:.2f}, Diff={row['close_diff']:.2f}")

    # Also checking if constant offset?
    print(f"\nMean Diff: {merged['close_diff'].mean():.2f}")

import os
if __name__ == "__main__":
    validate_daily_spx()
