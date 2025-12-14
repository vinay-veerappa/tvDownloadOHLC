import pandas as pd
import numpy as np

def debug_1h_timestamps():
    adjusted_file = r"C:\Users\vinay\tvDownloadOHLC\data\SP_adjusted_1h.csv"
    spx_file = r"C:\Users\vinay\tvDownloadOHLC\data\SPX_1h.parquet"
    
    print("Loading Adjusted...")
    df_adj = pd.read_csv(adjusted_file)
    df_adj['datetime'] = pd.to_datetime(df_adj['datetime'])
    print(f"Adj Sample: {df_adj['datetime'].head(3).tolist()}")
    
    print("\nLoading SPX...")
    df_spx = pd.read_parquet(spx_file)
    
    if 'time' in df_spx.columns:
         if pd.api.types.is_numeric_dtype(df_spx['time']):
             df_spx['datetime'] = pd.to_datetime(df_spx['time'], unit='s')
         else:
             df_spx['datetime'] = pd.to_datetime(df_spx['time'])
    elif isinstance(df_spx.index, pd.DatetimeIndex):
        df_spx['datetime'] = df_spx.index
    
    if 'datetime' in df_spx.columns:
        if df_spx['datetime'].dt.tz is not None:
             df_spx['datetime'] = df_spx['datetime'].dt.tz_convert(None)
        print(f"SPX Sample: {df_spx['datetime'].head(3).tolist()}")
        print(f"SPX Range: {df_spx['datetime'].min()} - {df_spx['datetime'].max()}")
        
        print("\nIntersection Attempt (Exact)...")
        common = df_adj[df_adj['datetime'].isin(df_spx['datetime'])]
        print(f"Exact Matches: {len(common)}")
        
        # Check if maybe SPX is 14:30 and Adj is 14:00?
        print("\nChecking Hour Alignment:")
        print(f"Adj First Hour: {df_adj['datetime'].iloc[0].minute}")
        print(f"SPX First Hour: {df_spx['datetime'].iloc[0].minute}")

if __name__ == "__main__":
    debug_1h_timestamps()
