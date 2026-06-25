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

def load_parquet(ticker: str, timeframe: str, t_end: Optional[float] = None, columns: Optional[list] = None) -> Optional[pd.DataFrame]:
    """
    Load OHLCV data from Parquet file merged with live storage data in memory.
    
    Args:
        ticker: e.g., "ES1", "NQ1" or "ES1!" (will be stripped)
        timeframe: e.g., "5m", "1h", "1D", "1wk" (maps "1W" -> "1wk")
        t_end: Optional timestamp limit (used to skip live fusion for purely historical slices)
        columns: Optional list of columns to load from disk (e.g. ['time', 'high', 'low']).
    
    Returns:
        DataFrame with columns: time, open, high, low, close, volume (or a subset if columns specified)
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

    # Ignore column selective loading if resampling is needed (resampling requires OHLCV columns)
    clean_tf = timeframe.replace('m', '')
    if columns is not None and clean_tf not in ['1', '1m']:
        columns = None
        
    live_ticker = TICKER_MAP.get(clean_ticker, clean_ticker)
    live_path = DATA_DIR / "live" / f"live_storage_{live_ticker}.parquet"
    
    # Generate stable cache keys
    fused_key = f"fused_{clean_ticker}_{timeframe}"
    if columns is not None:
        fused_key += "_cols_" + "_".join(sorted(columns))
        
    live_mtime = 0.0
    if live_path.exists():
        try:
            live_mtime = os.path.getmtime(live_path)
        except Exception:
            pass
            
    # 1. Check for fully cached fused dataframe
    if fused_key in _FUSED_CACHE:
        cached_df, cached_mtime = _FUSED_CACHE[fused_key]
        if cached_mtime == live_mtime:
            return cached_df.copy()
            
        # 2. Try incremental append in-memory to avoid copying 6.5M rows
        if not cached_df.empty and live_path.exists():
            try:
                cache_key_live = f"live_{live_ticker}"
                if columns is not None:
                    cache_key_live += "_cols_" + "_".join(sorted(columns))
                    
                if cache_key_live in _LIVE_STORAGE_CACHE and _LIVE_STORAGE_CACHE[cache_key_live][1] == live_mtime:
                    df_l = _LIVE_STORAGE_CACHE[cache_key_live][0]
                else:
                    live_cols = columns if columns is not None else ['time', 'open', 'high', 'low', 'close', 'volume']
                    df_l = pd.read_parquet(live_path, columns=live_cols)
                    _LIVE_STORAGE_CACHE[cache_key_live] = (df_l, live_mtime)
                
                if df_l is not None and not df_l.empty:
                    last_cached_time_ms = int(cached_df['time'].iloc[-1] * 1000)
                    new_live = df_l[df_l['time'] > last_cached_time_ms].copy()
                    
                    live_min_time_ms = df_l['time'].min()
                    live_max_time_ms = df_l['time'].max()
                    
                    # Ensure live data begins before/at last cached time (no gaps)
                    # and that live storage hasn't been reset/trimmed
                    if live_max_time_ms > last_cached_time_ms and live_min_time_ms <= last_cached_time_ms:
                        if not new_live.empty:
                            new_live['datetime'] = pd.to_datetime(new_live['time'], unit='ms')
                            new_live = new_live.set_index('datetime')
                            
                            # Resample if needed
                            if clean_tf not in ['1', '1m']:
                                rule = parse_timeframe_to_pandas(timeframe)
                                new_live_resampled = new_live.resample(rule).agg({
                                    'time': 'first',
                                    'open': 'first',
                                    'high': 'max',
                                    'low': 'min',
                                    'close': 'last',
                                    'volume': 'sum'
                                }).dropna()
                            else:
                                new_live_resampled = new_live
                                
                            if not new_live_resampled.empty:
                                new_live_resampled['time'] = new_live_resampled.index.astype('int64') // 10**9
                                live_cols_to_slice = columns if columns is not None else ['time', 'open', 'high', 'low', 'close', 'volume']
                                new_live_resampled = new_live_resampled[live_cols_to_slice]
                                
                                updated_df = pd.concat([cached_df, new_live_resampled]).reset_index(drop=True)
                                _FUSED_CACHE[fused_key] = (updated_df, live_mtime)
                                return updated_df.copy()
                        else:
                            _FUSED_CACHE[fused_key] = (cached_df, live_mtime)
                            return cached_df.copy()
            except Exception as e:
                print(f"[data_loader] Incremental append failed, falling back to full fusion: {e}")
        
    filename = f"{clean_ticker}_{timeframe}.parquet"
    filepath = DATA_DIR / filename
    
    if not filepath.exists():
        print(f"File not found: {filepath}")
        return None
    
    cache_key = f"{clean_ticker}_{timeframe}"
    if columns is not None:
        cache_key += "_cols_" + "_".join(sorted(columns))
        
    if cache_key in _HISTORICAL_CACHE:
        df = _HISTORICAL_CACHE[cache_key]
    else:
        df = pd.read_parquet(filepath, columns=columns)
        
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
        if columns is not None:
            expected_cols = [c for c in expected_cols if c in columns]
            
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
            if columns is not None:
                cache_key_live += "_cols_" + "_".join(sorted(columns))
                
            if cache_key_live in _LIVE_STORAGE_CACHE and _LIVE_STORAGE_CACHE[cache_key_live][1] == mtime:
                df_l = _LIVE_STORAGE_CACHE[cache_key_live][0].copy()
            else:
                live_cols = columns if columns is not None else ['time', 'open', 'high', 'low', 'close', 'volume']
                df_l = pd.read_parquet(live_path, columns=live_cols)
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
                df_l['datetime'] = pd.to_datetime(df_l['time'], unit='ms')
                df_l = df_l.set_index('datetime')
                
                # Resample live data if target is not 1m
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
                live_cols_to_slice = columns if columns is not None else ['time', 'open', 'high', 'low', 'close', 'volume']
                df_l_resampled = df_l_resampled[live_cols_to_slice]
                
                # Optimized merge: split using searchsorted to avoid copying 6.5M rows
                if not df.empty and not df_l_resampled.empty:
                    min_live_time = df_l_resampled['time'].min()
                    split_idx = df['time'].searchsorted(min_live_time)
                    
                    df_before = df.iloc[:split_idx]
                    df_overlap = df.iloc[split_idx:]
                    
                    # Concat and deduplicate only the overlapping part
                    merged_overlap = pd.concat([df_overlap, df_l_resampled])
                    merged_overlap = merged_overlap.drop_duplicates(subset=['time'], keep='last')
                    merged_overlap = merged_overlap.sort_values('time')
                    
                    df = pd.concat([df_before, merged_overlap]).reset_index(drop=True)
                elif not df_l_resampled.empty:
                    df = df_l_resampled.copy()
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
