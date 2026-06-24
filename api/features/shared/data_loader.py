"""
Data loader service - reads Parquet files from the data directory
"""

import os
import pandas as pd
from pathlib import Path
from typing import Optional


# Path to data directory - relative to project root
DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"

# In-Memory Cache to prevent reading Parquet from disk on every API call
_HISTORICAL_CACHE = {}
_LIVE_STORAGE_CACHE = {}
_FUSED_CACHE = {}

TICKER_MAP = {
    "ES1": "-ES",
    "NQ1": "-NQ",
    "RTY1": "-RTY",
    "YM1": "-YM",
    "CL1": "-CL",
    "GC1": "-GC",
}

def parse_timeframe_to_pandas(tf: str) -> str:
    clean_tf = tf.replace('m', '')
    if clean_tf.isdigit():
        return f"{clean_tf}min"
    lower = tf.lower()
    if lower.endswith('h'):
        return f"{lower[:-1]}H"
    if lower.endswith('d'):
        return f"{lower[:-1]}D"
    if lower.endswith('w'):
        return f"{lower[:-1]}W"
    if lower.endswith('m') and tf.isupper():
        return f"{tf[:-1]}M"
    return tf

def load_parquet(ticker: str, timeframe: str, t_end: Optional[float] = None) -> Optional[pd.DataFrame]:
    """
    Load OHLCV data from Parquet file merged with live storage data in memory.
    
    Args:
        ticker: e.g., "ES1", "NQ1" or "ES1!" (will be stripped)
        timeframe: e.g., "5m", "1h", "1D", "1wk" (maps "1W" -> "1wk")
        t_end: Optional timestamp limit (used to skip live fusion for purely historical slices)
    
    Returns:
        DataFrame with columns: time, open, high, low, close, volume
    """
    # Clean ticker: "ES1!" -> "ES1"
    clean_ticker = ticker.replace("!", "")
    
    # Handle aliases (e.g. "NQ" -> "NQ1", "ES" -> "ES1")
    # This ensures simple names map to the continuous contract file we have.
    aliases = {
        "NQ": "NQ1",
        "ES": "ES1", 
        "CL": "CL1",
        "RTY": "RTY1",
        "YM": "YM1",
        "GC": "GC1"
    }
    if clean_ticker in aliases:
        clean_ticker = aliases[clean_ticker]
        
    live_ticker = TICKER_MAP.get(clean_ticker, clean_ticker)
    live_path = DATA_DIR / "live" / f"live_storage_{live_ticker}.parquet"
    
    fused_key = f"fused_{clean_ticker}_{timeframe}"
    live_mtime = 0.0
    if live_path.exists():
        try:
            live_mtime = os.path.getmtime(live_path)
        except Exception:
            pass
            
    if fused_key in _FUSED_CACHE and _FUSED_CACHE[fused_key][1] == live_mtime:
        return _FUSED_CACHE[fused_key][0].copy()
        
    filename = f"{clean_ticker}_{timeframe}.parquet"
    filepath = DATA_DIR / filename
    
    if not filepath.exists():
        print(f"File not found: {filepath}")
        return None
    
    cache_key = f"{clean_ticker}_{timeframe}"
    if cache_key in _HISTORICAL_CACHE:
        df = _HISTORICAL_CACHE[cache_key]
    else:
        df = pd.read_parquet(filepath)
        
        # Handle datetime index - reset to column and convert to Unix timestamp
        if df.index.name in ['datetime', 'time', 'timestamp'] or (not df.index.empty and isinstance(df.index, pd.DatetimeIndex)):
            old_cols = set(df.columns)
            df = df.reset_index()
            new_cols = set(df.columns) - old_cols
            if new_cols:
                reset_col = list(new_cols)[0]
                if 'time' not in df.columns:
                    df = df.rename(columns={reset_col: 'time'})
                elif reset_col != 'time':
                    if df['time'].isna().all() or (df['time'].dtype == 'float64' and df['time'].isna().sum() > 0):
                        df = df.drop(columns=['time'])
                        df = df.rename(columns={reset_col: 'time'})
        
        if 'datetime' in df.columns:
            if 'time' in df.columns and 'datetime' != 'time':
                 df = df.drop(columns=['datetime'])
            elif 'time' not in df.columns:
                df = df.rename(columns={'datetime': 'time'})
        elif 'timestamp' in df.columns:
            if 'time' in df.columns and 'timestamp' != 'time':
                 df = df.drop(columns=['timestamp'])
            elif 'time' not in df.columns:
                 df = df.rename(columns={'timestamp': 'time'})
        
        if 'time' in df.columns and pd.api.types.is_datetime64_any_dtype(df['time']):
            df['time'] = df['time'].astype('int64') // 10**9
        
        if 'time' in df.columns:
            df = df.dropna(subset=['time'])

        expected_cols = ['time', 'open', 'high', 'low', 'close', 'volume']
        for col in expected_cols:
            if col not in df.columns:
                print(f"Missing column: {col}")
                return None
        
        df = df.sort_values('time').reset_index(drop=True)
        
        # Store in cache (no copy needed as this is a fresh df)
        _HISTORICAL_CACHE[cache_key] = df
        
    # ----------------------------------------------------
    # DYNAMIC IN-MEMORY LIVE STORAGE FUSION (PHASE 2 BACKEND)
    # ----------------------------------------------------
    live_ticker = TICKER_MAP.get(clean_ticker, clean_ticker)
    live_path = DATA_DIR / "live" / f"live_storage_{live_ticker}.parquet"
    
    if live_path.exists():
        try:
            mtime = os.path.getmtime(live_path)
            cache_key_live = f"live_{live_ticker}"
            if cache_key_live in _LIVE_STORAGE_CACHE and _LIVE_STORAGE_CACHE[cache_key_live][1] == mtime:
                df_l = _LIVE_STORAGE_CACHE[cache_key_live][0].copy()
            else:
                df_l = pd.read_parquet(live_path)
                _LIVE_STORAGE_CACHE[cache_key_live] = (df_l, mtime)
                df_l = df_l.copy()

            if not df_l.empty:
                # Filter to only keep candles after (last historical time - 2 hours) to avoid processing huge history
                if not df.empty:
                    last_hist_time_ms = int(df['time'].iloc[-1] * 1000)
                    overlap_threshold_ms = last_hist_time_ms - (7200 * 1000)
                    df_l = df_l[df_l['time'] >= overlap_threshold_ms].copy()

            if not df_l.empty:
                # Ensure the time column is datetime index for resampling
                # Live storage uses epoch ms (13-digit)
                df_l['datetime'] = pd.to_datetime(df_l['time'], unit='ms')
                df_l = df_l.set_index('datetime')
                
                # Resample live data if target is not 1m
                clean_tf = timeframe.replace('m', '')
                if clean_tf not in ['1', '1m']:
                    rule = parse_timeframe_to_pandas(timeframe)
                    df_l_resampled = df_l.resample(rule).agg({
                        'time': 'first',
                        'open': 'first',
                        'high': 'max',
                        'low': 'min',
                        'close': 'last',
                        'volume': 'sum'
                    }).dropna()
                else:
                    df_l_resampled = df_l
                
                # Convert resampled index back to Unix seconds
                df_l_resampled['time'] = df_l_resampled.index.astype('int64') // 10**9
                
                # Keep expected columns
                df_l_resampled = df_l_resampled[['time', 'open', 'high', 'low', 'close', 'volume']]
                
                # Merge and deduplicate (live overwrites historical)
                merged = pd.concat([df, df_l_resampled])
                merged = merged.drop_duplicates(subset=['time'], keep='last')
                df = merged.sort_values('time').reset_index(drop=True)
                print(f"[data_loader] Successfully fused {len(df_l_resampled)} live storage bars into {clean_ticker}_{timeframe}")
        except Exception as e:
            print(f"[data_loader] Failed to fuse live storage for {clean_ticker}: {e}")
    
    if df is not None:
        _FUSED_CACHE[fused_key] = (df.copy(), live_mtime)
    
    return df


def get_available_data() -> list:
    """List all available ticker/timeframe combinations"""
    if not DATA_DIR.exists():
        return []
    
    files = []
    for f in DATA_DIR.glob("*.parquet"):
        parts = f.stem.split("_")
        if len(parts) >= 2:
            base_ticker = parts[0]
            # Standardize: "ES1" -> "ES1!"
            # Strategy: If it ends in a digit, assume it's a future and add !
            if base_ticker and base_ticker[-1].isdigit():
                ticker = f"{base_ticker}!"
            else:
                ticker = base_ticker
                
            timeframe = "_".join(parts[1:])
            files.append({"ticker": ticker, "timeframe": timeframe})
    
    return files
