import pandas as pd
import numpy as np

def validate_daily():
    csv_file = r"C:\Users\vinay\tvDownloadOHLC\data\SP_1m_verification.csv"
    parquet_file = r"C:\Users\vinay\tvDownloadOHLC\data\ES1_1D.parquet"
    
    print("Loading 1m CSV...")
    df_1m = pd.read_csv(csv_file)
    df_1m['datetime'] = pd.to_datetime(df_1m['datetime'])
    df_1m.set_index('datetime', inplace=True)
    
    print("Aggregating 1m to Daily...")
    # Resample to Daily. Using '1D' or '1d'? 
    # Important: Exchange time vs Calendar day.
    # The tick data showed 08:30 starts, suggesting RTH or similar?
    # Let's try simple calendar day aggregation first.
    df_daily_agg = df_1m.resample('1D').agg({
        'high': 'max',
        'low': 'min',
        'close': 'last', # Open might differ if we don't have full session
        'open': 'first',
        'volume': 'sum'
    }).dropna()
    
    # Extract just the date part for joining
    df_daily_agg['date'] = df_daily_agg.index.date
    
    print(f"Aggregated Rows: {len(df_daily_agg)}")
    
    print("Loading Existing Daily Parquet...")
    df_old = pd.read_parquet(parquet_file)
    
    if 'time' in df_old.columns:
        if pd.api.types.is_numeric_dtype(df_old['time']):
             df_old['datetime'] = pd.to_datetime(df_old['time'], unit='s')
        else:
             df_old['datetime'] = pd.to_datetime(df_old['time'])
    elif isinstance(df_old.index, pd.DatetimeIndex):
        df_old['datetime'] = df_old.index
        
    # Localize? The parquet might be TZ-aware or naive.
    if df_old['datetime'].dt.tz is not None:
        df_old['datetime'] = df_old['datetime'].dt.tz_convert(None) # Make naive for comparison
        
    df_old['date'] = df_old['datetime'].dt.date
    df_old.set_index('date', inplace=True)
    
    print(f"Reference Rows: {len(df_old)}")
    
    # Comparison
    print("\nMatching Dates...")
    common_dates = df_daily_agg['date'].isin(df_old.index)
    df_matched = df_daily_agg[common_dates].copy()
    
    print(f"Overlapping Days: {len(df_matched)}")
    
    if len(df_matched) == 0:
        print("No matches! Check Date zones?")
        print(f"Agg Sample: {df_daily_agg['date'].head()}")
        print(f"Ref Sample: {df_old.index[:5]}")
        return

    # Join
    merged = df_matched.join(df_old, on='date', rsuffix='_ref')
    
    # Check High/Low/Close Diff
    merged['high_diff'] = merged['high'] - merged['high_ref']
    merged['low_diff'] = merged['low'] - merged['low_ref']
    merged['close_diff'] = merged['close'] - merged['close_ref']
    
    print("\n--- Validation Statistics (Absolute Diff) ---")
    print(merged[['high_diff', 'low_diff', 'close_diff']].abs().describe())
    
    # Tolerance Check (e.g., < 1 point)
    close_ok = (merged['close_diff'].abs() < 1.0).sum()
    print(f"\nClose Price Matches (< 1.0 diff): {close_ok} / {len(merged)} ({close_ok/len(merged):.1%})")
    
    print("\n--- Sample Mismatches (Worst Close Diffs) ---")
    bad = merged.nlargest(10, 'close_diff')
    for idx, row in bad.iterrows():
        print(f"{row['date']}: Own Close={row['close']:.2f}, Ref={row['close_ref']:.2f}, Diff={row['close_diff']:.2f}")

if __name__ == "__main__":
    validate_daily()
