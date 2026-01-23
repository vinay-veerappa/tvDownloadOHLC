"""
Unified Data Loader for Analysis Scripts.

This module provides a single function to load fused OHLCV data from:
1. Live Storage Parquet (Recent, ~1 year) - PRIMARY
2. Historical Parquet (Deep History, 2006-2024) - FALLBACK (if more data needed)

Usage:
    from fused_data_loader import load_fused_data
    df = load_fused_data("NQ1")  # Returns full DataFrame (Live + Historical)
"""

import os
import pandas as pd

DATA_DIR = "c:/Users/vinay/tvDownloadOHLC/data"
LIVE_DIR = os.path.join(DATA_DIR, "live")

# Ticker -> Schwab Symbol Mapping (for live storage filenames)
TICKER_MAP = {
    "ES1": "-ES",
    "NQ1": "-NQ",
    "RTY1": "-RTY",
    "YM1": "-YM",
    "CL1": "-CL",
    "GC1": "-GC",
    # Equities and indices use their own symbol
}

def load_fused_data(ticker, timeframe="1m", require_historical=False):
    """
    Load fused OHLCV data for a ticker.
    
    Args:
        ticker: Application ticker (e.g., NQ1, ES1, SPY)
        timeframe: Timeframe (default: 1m). Live storage is always 1m.
        require_historical: If True, always load and fuse historical data.
                           If False, only load historical if Live Storage is empty/missing.
    
    Returns:
        pd.DataFrame with 'datetime' index and OHLCV columns.
    """
    
    # 1. Determine Live Storage Path
    live_ticker = TICKER_MAP.get(ticker, ticker)
    live_path = os.path.join(LIVE_DIR, f"live_storage_{live_ticker}.parquet")
    
    # 2. Determine Historical Path
    hist_path = os.path.join(DATA_DIR, f"{ticker}_{timeframe}.parquet")
    
    dfs = []
    
    # 3. Load Live Storage (Primary)
    if os.path.exists(live_path):
        try:
            df_live = pd.read_parquet(live_path)
            df_live = _normalize_index(df_live)
            dfs.append(df_live)
            print(f"  [Live Storage] Loaded {len(df_live)} rows from {os.path.basename(live_path)}")
        except Exception as e:
            print(f"  [Live Storage] Error reading {live_path}: {e}")
    else:
        print(f"  [Live Storage] Not found: {live_path}")
        require_historical = True # Must load historical if live is missing
    
    # 4. Load Historical (Fallback or if required)
    # We load historical if:
    #   - require_historical is True (explicit)
    #   - Live Storage was missing/empty
    #   - Analysis requires data older than what Live holds (HTF analysis, backtests)
    if require_historical or len(dfs) == 0:
        if os.path.exists(hist_path):
            try:
                df_hist = pd.read_parquet(hist_path)
                df_hist = _normalize_index(df_hist)
                dfs.append(df_hist)
                print(f"  [Historical]   Loaded {len(df_hist)} rows from {os.path.basename(hist_path)}")
            except Exception as e:
                print(f"  [Historical]   Error reading {hist_path}: {e}")
        else:
            print(f"  [Historical]   Not found: {hist_path}")
    
    # 5. Fuse Data
    if not dfs:
        print(f"  [WARN] No data found for {ticker}")
        return pd.DataFrame()
    
    combined = pd.concat(dfs)
    combined = combined[~combined.index.duplicated(keep='last')] # Prefer live data
    combined.sort_index(inplace=True)
    
    print(f"  [Fused]        Total: {len(combined)} rows | Range: {combined.index.min()} to {combined.index.max()}")
    
    return combined

def _normalize_index(df):
    """Ensure DataFrame has a DatetimeIndex named 'datetime'."""
    # If index is already DatetimeIndex, we're good
    if isinstance(df.index, pd.DatetimeIndex):
        df.index.name = 'datetime'
        return df
    
    # Reset index if it's a RangeIndex or Int64Index (row numbers)
    if isinstance(df.index, (pd.RangeIndex, pd.Index)) and df.index.dtype in ['int64', 'int32']:
        df = df.reset_index(drop=True)
    
    # Find datetime column
    if 'datetime' in df.columns:
        df['datetime'] = pd.to_datetime(df['datetime'])
        df.set_index('datetime', inplace=True)
    elif 'date' in df.columns:
        df['datetime'] = pd.to_datetime(df['date'])
        df.set_index('datetime', inplace=True)
    elif 'time' in df.columns:
        # Live Storage uses 'time' column with epoch milliseconds
        time_col = df['time']
        # Check if it looks like epoch (large number)
        if time_col.iloc[0] > 1e10: # Milliseconds
            df['datetime'] = pd.to_datetime(time_col, unit='ms')
        elif time_col.iloc[0] > 1e9: # Seconds
            df['datetime'] = pd.to_datetime(time_col, unit='s')
        else:
            df['datetime'] = pd.to_datetime(time_col)
        df.set_index('datetime', inplace=True)
    else:
        # Try first column if it looks like datetime
        first_col = df.columns[0]
        try:
            df['datetime'] = pd.to_datetime(df[first_col])
            df.set_index('datetime', inplace=True)
        except:
            pass
    
    return df
