import pandas as pd
import numpy as np

def validate_offset_1h():
    # Sources
    raw_1m = r"C:\Users\vinay\tvDownloadOHLC\data\SP_1m_verification.csv"
    ref_daily = r"C:\Users\vinay\tvDownloadOHLC\data\ES1_1D.parquet"
    spx_1h_target = r"C:\Users\vinay\tvDownloadOHLC\data\SPX_1h.parquet"
    
    print("1. Loading Raw 1m & Ref Daily...")
    df_raw = pd.read_csv(raw_1m, parse_dates=['datetime'], index_col='datetime')
    # Use normalized datetime for merge key just in case
    df_raw['date_key'] = df_raw.index.floor('D')
    
    df_ref = pd.read_parquet(ref_daily)
    if 'time' in df_ref.columns:
         if pd.api.types.is_numeric_dtype(df_ref['time']):
             df_ref['datetime'] = pd.to_datetime(df_ref['time'], unit='s')
         else:
             df_ref['datetime'] = pd.to_datetime(df_ref['time'])
    elif isinstance(df_ref.index, pd.DatetimeIndex):
        df_ref['datetime'] = df_ref.index
        
    if df_ref['datetime'].dt.tz is not None:
        df_ref['datetime'] = df_ref['datetime'].dt.tz_convert(None)
    
    # Floor to Day for key
    df_ref['date_key'] = df_ref['datetime'].dt.floor('D')
    df_ref.set_index('date_key', inplace=True)
    
    # 2. Daily Delta
    raw_daily = df_raw.resample('1D').last().dropna()
    raw_daily['date_key'] = raw_daily.index.floor('D')
    
    merged_daily = pd.merge(raw_daily[['close', 'date_key']], df_ref[['close']], left_on='date_key', right_index=True, suffixes=('_raw', '_ref'))
    merged_daily['delta'] = merged_daily['close_ref'] - merged_daily['close_raw']
    
    # 3. Apply to Intraday
    df_raw.reset_index(inplace=True)
    df_adj = pd.merge(df_raw, merged_daily[['delta']], left_on='date_key', right_index=True, how='inner')
    
    df_adj['close_adj'] = df_adj['close'] + df_adj['delta']
    df_adj.set_index('datetime', inplace=True)
    
    print("2. Resampling Adjusted Intraday to 1H (Offset 30min)...")
    # Resample
    df_1h_adj = df_adj.resample('1h', offset='30min').agg({'close_adj': 'last'}).dropna()
    
    print("3. Loading SPX 1H...")
    df_spx = pd.read_parquet(spx_1h_target)
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
    
    # 4. Compare
    common = df_1h_adj.index.intersection(df_spx.index)
    print(f"Overlapping Buckets: {len(common)}")
    
    if len(common) > 0:
        match_adj = df_1h_adj.loc[common]
        match_spx = df_spx.loc[common]
        
        spread = match_adj['close_adj'] - match_spx['close']
        corr = match_adj['close_adj'].corr(match_spx['close'])
        
        print(f"\nSpread Mean: {spread.mean():.2f}")
        print(f"Spread Std: {spread.std():.2f}")
        print(f"Correlation: {corr:.6f}")
        
    else:
        print("Still no overlap.")
        print(f"Adj Sample: {df_1h_adj.index[:3]}")
        print(f"SPX Sample: {df_spx.index[:3]}")

if __name__ == "__main__":
    validate_offset_1h()
