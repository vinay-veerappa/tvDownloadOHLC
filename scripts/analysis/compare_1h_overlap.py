import pandas as pd
import numpy as np

def compare_adjusted_vs_spx():
    adjusted_file = r"C:\Users\vinay\tvDownloadOHLC\data\SP_adjusted_1h.csv"
    spx_file = r"C:\Users\vinay\tvDownloadOHLC\data\SPX_1h.parquet"
    
    print("Loading Adjusted 1H...")
    df_adj = pd.read_csv(adjusted_file)
    df_adj['datetime'] = pd.to_datetime(df_adj['datetime'])
    df_adj.set_index('datetime', inplace=True)
    
    print("Loading SPX 1H...")
    df_spx = pd.read_parquet(spx_file)
    
    # Standardize SPX
    if 'time' in df_spx.columns:
         if pd.api.types.is_numeric_dtype(df_spx['time']):
             df_spx['datetime'] = pd.to_datetime(df_spx['time'], unit='s')
         else:
             df_spx['datetime'] = pd.to_datetime(df_spx['time'])
    elif isinstance(df_spx.index, pd.DatetimeIndex):
        df_spx['datetime'] = df_spx.index
        
    if df_spx['datetime'].dt.tz is not None:
        df_spx['datetime'] = df_spx['datetime'].dt.tz_convert(None)
        
    df_spx.set_index('datetime', inplace=True)
    
    # Intersect
    common_idx = df_adj.index.intersection(df_spx.index)
    print(f"Overlapping 1H Bars: {len(common_idx)}")
    
    if len(common_idx) == 0:
        print("No overlap found.")
        return
        
    adj_match = df_adj.loc[common_idx]
    spx_match = df_spx.loc[common_idx]
    
    # Compare
    # Calculate Spread
    spread = adj_match['close'] - spx_match['close']
    
    print("\n--- Comparison Stats (2014-2019) ---")
    print(f"Spread Mean (Adjusted Futures - SPX): {spread.mean():.2f}")
    print(f"Spread StdDev: {spread.std():.2f}")
    
    # Correlation
    corr = adj_match['close'].corr(spx_match['close'])
    print(f"Correlation: {corr:.6f}")
    
    print("\n--- Sample Data ---")
    combined = pd.DataFrame({
        'Generic_Adj': adj_match['close'],
        'SPX_Cash': spx_match['close'],
        'Spread': spread
    })
    print(combined.head(10))
    
    print("\n--- Interpretation ---")
    print("If Correlation is > 0.99, the movements are identical.")
    print("The Spread represents 'Fair Value' + 'Back Adjustment' scaling.")

if __name__ == "__main__":
    compare_adjusted_vs_spx()
