"""
Unified Data Loader for Analysis Scripts.

This module provides a single function to load fused OHLCV data from:
1. Live Storage Parquet (Recent, ~1 year) - PRIMARY
2. Historical Parquet (Deep History, 2006-2024) - FALLBACK (if more data needed)

Returns ET-naive DatetimeIndex with a `trade_date` column reflecting the
futures session (18:00 ET prior evening → 16:00 ET close rolls to next day).
Callers can slice by string ("2025-03-15 09:30:00") and group by trade_date
without re-implementing the overnight roll.

Usage:
    from fused_data_loader import load_fused_data
    df = load_fused_data("NQ1")  # Returns full DataFrame (Live + Historical)
"""

import os
import numpy as np
import pandas as pd

DATA_DIR = "c:/Users/vinay/tvDownloadOHLC/data"
LIVE_DIR = os.path.join(DATA_DIR, "live")
DERIVED_DIR = os.path.join(DATA_DIR, "derived")
REGIME_DIR = os.path.join(DERIVED_DIR, "regimes")

ET_TZ = "America/New_York"

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

# Futures RTH session boundaries (ET, naive after conversion)
RTH_OPEN = 930   # 09:30 ET
RTH_CLOSE = 1600 # 16:00 ET
ON_OPEN = 1800   # 18:00 ET (prior evening = start of next trading day)


def _to_et_naive(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize any DatetimeIndex to ET-naive (America/New_York, tz removed).

    Live storage epoch-ms is UTC; historical parquet may already be ET-naive.
    Handles both cases. After this, callers can string-slice ("2025-03-15 09:30")
    without worrying about timezone conversions.
    """
    if df.empty or not isinstance(df.index, pd.DatetimeIndex):
        return df

    if df.index.tz is not None:
        # tz-aware: convert to ET, strip tz
        df.index = df.index.tz_convert(ET_TZ).tz_localize(None)
    else:
        # tz-naive: assume UTC (live_storage epoch-ms convention) and convert
        df.index = df.index.tz_localize("UTC").tz_convert(ET_TZ).tz_localize(None)

    return df


def add_futures_trade_date(df: pd.DataFrame, col: str = "trade_date") -> pd.DataFrame:
    """Add a futures trading-day column (overnight session rolls to next calendar date).

    For futures, a trading day runs 18:00 ET (prior evening) → 16:00 ET (close).
    Bars at 18:00+ ET belong to the NEXT calendar date's trading session.
    This mirrors the canonical `session_date` in institutional_levels.py.

    After this, callers can `groupby(col)` to get per-session stats without
    re-implementing the overnight roll.
    """
    if df.empty or col in df.columns:
        return df

    hours = df.index.hour.values
    dates = df.index.date
    next_dates = (df.index + pd.Timedelta(days=1)).date
    df[col] = np.where(hours >= 18, next_dates, dates)
    return df


def load_fused_data(ticker, timeframe="1m", require_historical=False):
    """
    Load fused OHLCV data for a ticker with robust normalization.

    Returns ET-naive DatetimeIndex with a `trade_date` column (futures session).
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
            # Force epoch ms to datetime (UTC)
            df_l['datetime'] = pd.to_datetime(df_l['time'], unit='ms')
            df_l = df_l.set_index('datetime')
            dfs.append(df_l)
            print(f"  [Live Storage] Loaded {len(df_l)} rows")

    # 3. Load and Normalize Hist
    if require_historical or not dfs:
        if os.path.exists(hist_path):
            df_h = pd.read_parquet(hist_path)
            if not df_h.empty:
                # Historical index is already naive datetime (ET-naive)
                df_h.index = pd.to_datetime(df_h.index)
                dfs.append(df_h)
                print(f"  [Historical]   Loaded {len(df_h)} rows")

    if not dfs:
        return pd.DataFrame()

    # 4. Critical: Unify then deduplicate
    combined = pd.concat(dfs)
    combined = combined[~combined.index.duplicated(keep='last')]
    combined = combined.sort_index()

    # 5. Convert to ET-naive (handles UTC live storage + ET-naive historical)
    combined = _to_et_naive(combined)

    # 6. Add futures trade_date (overnight 18:00+ rolls to next day)
    combined = add_futures_trade_date(combined)

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
        df = df.set_index('datetime', inplace=False)
    elif 'date' in df.columns:
        df['datetime'] = pd.to_datetime(df['date'])
        df = df.set_index('datetime', inplace=False)
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
        df = df.set_index('datetime', inplace=False)
        return df

    # 4. Find other datetime columns
    # Try first column if it looks like datetime
    first_col = df.columns[0]
    try:
        df['datetime'] = pd.to_datetime(df[first_col])
        df = df.set_index('datetime', inplace=False)
    except:
        pass

    return df