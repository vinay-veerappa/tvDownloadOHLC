import pandas as pd
import numpy as np

def validate_4h_overlap():
    adjusted_1h_file = r"C:\Users\vinay\tvDownloadOHLC\data\SP_adjusted_1h.csv"
    es1_4h_file = r"C:\Users\vinay\tvDownloadOHLC\data\ES1_4h.parquet"
    
    print("Loading Adjusted 1H Data...")
    df_adj = pd.read_csv(adjusted_1h_file)
    df_adj['datetime'] = pd.to_datetime(df_adj['datetime'])
    df_adj.set_index('datetime', inplace=True)
    
    print("Loading ES1 4H Data...")
    df_es4 = pd.read_parquet(es1_4h_file)
    
    # Standardize Datetime
    if 'time' in df_es4.columns:
         if pd.api.types.is_numeric_dtype(df_es4['time']):
             df_es4['datetime'] = pd.to_datetime(df_es4['time'], unit='s')
         else:
             df_es4['datetime'] = pd.to_datetime(df_es4['time'])
    elif isinstance(df_es4.index, pd.DatetimeIndex):
        df_es4['datetime'] = df_es4.index
        
    if df_es4['datetime'].dt.tz is not None:
        df_es4['datetime'] = df_es4['datetime'].dt.tz_convert(None)
    df_es4.set_index('datetime', inplace=True)
    
    print(f"ES4 Range: {df_es4.index.min()} to {df_es4.index.max()}")
    
    # Try different offsets for resampling 1H -> 4H to match ES4 structure
    offsets = ['0h', '1h', '2h', '3h']
    best_corr = -1
    best_offset = None
    best_match = None
    
    print("\nScanning for best alignment offset...")
    
    for offset in offsets:
        # Resample 1H to 4H with offset
        # base/origin default is usually start of day
        # 'closed' might matter (left/right)
        resampled = df_adj.resample('4h', offset=offset).agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last'
        }).dropna()
        
        # Intersect
        common = resampled.index.intersection(df_es4.index)
        
        if len(common) > 100:
            match_res = resampled.loc[common]
            match_es4 = df_es4.loc[common]
            
            corr = match_res['close'].corr(match_es4['close'])
            diff = (match_res['close'] - match_es4['close']).abs().mean()
            
            print(f"Offset {offset}: Overlap={len(common)}, Corr={corr:.5f}, AvgDiff={diff:.2f}")
            
            if corr > best_corr:
                best_corr = corr
                best_offset = offset
                best_match = (match_res, match_es4)
        else:
            print(f"Offset {offset}: Insufficient Overlap ({len(common)})")

    if best_match:
        res, es4 = best_match
        print(f"\n--- Best Match: Offset {best_offset} ---")
        print(f"Correlation: {best_corr:.6f}")
        
        diffs = res['close'] - es4['close']
        print("\n--- Difference Stats (Adjusted - ES1) ---")
        print(diffs.describe())
        
        print("\n--- Sample Comparison ---")
        cmb = pd.DataFrame({'Adj_1h_to_4h': res['close'], 'ES1_4h': es4['close'], 'Diff': diffs})
        print(cmb.head(10))
        
        # Check strictness
        exact = (diffs.abs() < 1.0).sum()
        print(f"\nMatches within 1.0 point: {exact} / {len(diffs)} ({exact/len(diffs):.1%})")
        
        # Check if the ES1 4H data is strictly identical to ES1 1D data implies 
        # that our adjusted data (synced to 1D) should match 4H well.
    else:
        print("\nFAILED to find good alignment.")

if __name__ == "__main__":
    validate_4h_overlap()
