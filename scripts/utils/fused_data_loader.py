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
DERIVED_DIR = os.path.join(DATA_DIR, "derived")
REGIME_DIR = os.path.join(DERIVED_DIR, "regimes")

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
    Load fused OHLCV data for a ticker with robust normalization.
    """
    # 1. Paths
    live_ticker = TICKER_MAP.get(ticker, ticker)
    live_path = os.path.join(LIVE_DIR, f"live_storage_{live_ticker}.parquet")
    hist_path = os.path.join(DATA_DIR, f"{ticker}_{timeframe}.parquet")
    
    dfs = []
    
    # 2. Load and Normalize Live
    if os.path.exists(live_path):
        df_l = pd.read_parquet(live_path)
        if not df_l.empty:
            # Force epoch ms to datetime
            df_l['datetime'] = pd.to_datetime(df_l['time'], unit='ms')
            df_l = df_l.set_index('datetime')
            dfs.append(df_l)
            print(f"  [Live Storage] Loaded {len(df_l)} rows")

    # 3. Load and Normalize Hist
    if require_historical or not dfs:
        if os.path.exists(hist_path):
            df_h = pd.read_parquet(hist_path)
            if not df_h.empty:
                # Historical index is already naive datetime
                df_h.index = pd.to_datetime(df_h.index)
                dfs.append(df_h)
                print(f"  [Historical]   Loaded {len(df_h)} rows")

    if not dfs: return pd.DataFrame()
    
    # 4. Critical: Unify then deduplicate
    combined = pd.concat(dfs)
    combined = combined[~combined.index.duplicated(keep='last')]
    combined = combined.sort_index()
    
    print(f"  [Fused]        Total: {len(combined)} rows | Range: {combined.index.min()} to {combined.index.max()}")
    return combined

def _normalize_index(df):
    """Ensure DataFrame has a DatetimeIndex named 'datetime'."""
    # If index is already DatetimeIndex, we're good
    if isinstance(df.index, pd.DatetimeIndex):
        df.index.name = 'datetime'
        return df
    
    # 2. Check for integer epochs (Live Storage)
    if 'time' in df.columns:
        # Check if it looks like epoch milliseconds
        time_val = df['time'].iloc[0]
        if time_val > 1e11: # Milliseconds
            df['datetime'] = pd.to_datetime(df['time'], unit='ms')
        elif time_val > 1e8: # Seconds
            df['datetime'] = pd.to_datetime(df['time'], unit='s')
        else:
            df['datetime'] = pd.to_datetime(df['time'])
        df = df.set_index('datetime')
        return df
    
    # 3. Handle other datetime columns
    if 'datetime' in df.columns:
        df['datetime'] = pd.to_datetime(df['datetime'])
        df.set_index('datetime', inplace=True)
    elif 'date' in df.columns:
        df['datetime'] = pd.to_datetime(df['date'])
        df.set_index('datetime', inplace=True)
    # 3. Handle 'time' column (Epoch ms/s)
    if 'time' in df.columns:
        # Live Storage uses 'time' column with epoch float/int
        time_val = df['time'].iloc[0]
        if time_val > 1e11: # Milliseconds (e.g. 1735772400000.0)
            df['datetime'] = pd.to_datetime(df['time'], unit='ms')
        elif time_val > 1e8: # Seconds
            df['datetime'] = pd.to_datetime(df['time'], unit='s')
        else:
            df['datetime'] = pd.to_datetime(df['time'])
        df.set_index('datetime', inplace=True)
        return df
    
    # 4. Find other datetime columns
    # Try first column if it looks like datetime
    first_col = df.columns[0]
    try:
        df['datetime'] = pd.to_datetime(df[first_col])
        df.set_index('datetime', inplace=True)
    except:
        pass
    
    return df
