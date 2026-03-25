"""
OHLC Resampling Service

This module ports the TypeScript resampling logic from web/lib/resampling.ts
to Python to ensure consistent aggregation between frontend chart display
and backend backtesting.

IMPORTANT: This logic MUST match the TypeScript implementation exactly!
Any changes here should be mirrored in resampling.ts and vice versa.
"""

import re
import pandas as pd
from typing import Optional


def parse_timeframe_to_seconds(tf: str) -> int:
    """
    Parse timeframe string into seconds.
    
    Examples:
        "1m" -> 60
        "5m" -> 300
        "1h" -> 3600
        "1D" -> 86400
        "240" -> 14400 (numeric = minutes)
    
    Must match TypeScript: parseTimeframeToSeconds()
    """
    # Check for resolution string (number only) - default to minutes
    if re.match(r'^\d+$', tf):
        return int(tf) * 60
    
    # Match: number + unit (m, h, d, w, D, W, M)
    match = re.match(r'^(\d+)([mhdwMDW])$', tf, re.IGNORECASE)
    if not match:
        return 0
    
    num = int(match.group(1))
    unit = match.group(2)
    
    # Use exact case for m/M distinction
    if unit == 'm':
        return num * 60
    elif unit in ('h', 'H'):
        return num * 60 * 60
    elif unit in ('d', 'D'):
        return num * 60 * 60 * 24
    elif unit in ('w', 'W'):
        return num * 60 * 60 * 24 * 7
    elif unit == 'M':
        return num * 60 * 60 * 24 * 30  # Approximate month
    else:
        return 0


def can_resample(from_tf: str, to_tf: str) -> bool:
    """
    Check if resampling from source to target is allowed.
    
    Rules:
    - Target must be larger than source
    - Daily/Weekly/Monthly (D, W, M) targets are NOT allowed
      (must use native data files for accurate settlement times)
    
    Must match TypeScript: canResample()
    """
    from_seconds = parse_timeframe_to_seconds(from_tf)
    to_seconds = parse_timeframe_to_seconds(to_tf)
    
    if to_seconds <= from_seconds:
        return False
    
    # Forbid D, W, M targets
    if re.search(r'[DWM]$', to_tf):
        return False
    if re.search(r'[dw]$', to_tf):
        return False
    
    return True


def resample_ohlc(df: pd.DataFrame, from_tf: str, to_tf: str) -> pd.DataFrame:
    """
    Aggregate lower timeframe data into higher timeframe buckets.
    
    Aggregation rules (MUST match TypeScript exactly):
    - open: first candle's open
    - high: max of all highs
    - low: min of all lows
    - close: last candle's close
    - volume: sum of all volumes
    
    Must match TypeScript: resampleOHLC()
    
    Args:
        df: DataFrame with columns [time, open, high, low, close, volume]
        from_tf: Source timeframe (e.g., "1m")
        to_tf: Target timeframe (e.g., "5m")
    
    Returns:
        Resampled DataFrame
    """
    from_seconds = parse_timeframe_to_seconds(from_tf)
    to_seconds = parse_timeframe_to_seconds(to_tf)
    
    # Validation
    if from_seconds == 0 or to_seconds == 0:
        print(f"Invalid timeframes: {from_tf} -> {to_tf}")
        return pd.DataFrame()
    
    if to_seconds <= from_seconds:
        # Target is smaller or equal, return original
        return df.copy()
    
    # Prohibit resampling to D/W/M
    if re.search(r'[DWMdw]$', to_tf):
        print(f"Resampling to {to_tf} is not supported (Daily/Weekly require native data)")
        return pd.DataFrame()
    
    if df.empty:
        return df.copy()
    
    # Calculate bucket for each row
    df = df.copy()
    df['bucket'] = (df['time'] // to_seconds) * to_seconds
    
    # Aggregate
    resampled = df.groupby('bucket').agg({
        'time': 'first',  # Will be replaced with bucket
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }).reset_index(drop=True)
    
    # Set time to bucket start
    resampled['time'] = df.groupby('bucket')['bucket'].first().values
    
    return resampled
