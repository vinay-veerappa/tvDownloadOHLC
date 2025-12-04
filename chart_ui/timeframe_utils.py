import pandas as pd
import re

def parse_timeframe(tf_str):
    """
    Parses a timeframe string like '1m', '4h', '1D', '30m'
    Returns (multiplier, unit) e.g. (1, 'm'), (4, 'h')
    """
    match = re.match(r"(\d+)([a-zA-Z]+)", tf_str)
    if not match:
        # Default or error?
        if tf_str == "D": return 1, "D"
        if tf_str == "W": return 1, "W"
        return None
    return int(match.group(1)), match.group(2)

def get_pandas_rule(tf_str):
    """
    Converts timeframe string to pandas resample rule.
    1m -> 1T
    1h -> 1H
    1D -> 1D
    1W -> 1W-FRI
    """
    mult, unit = parse_timeframe(tf_str)
    
    if unit in ['m', 'min']:
        return f"{mult}min"
    elif unit in ['h', 'H']:
        return f"{mult}h"
    elif unit in ['D', 'd']:
        return f"{mult}D"
    elif unit in ['W', 'w']:
        return f"{mult}W-FRI"
    elif unit in ['M']:
        return f"{mult}ME" # Month End
    return f"{mult}{unit}"

def resample_dataframe(df, rule):
    # Ensure index is datetime
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
        
    resampled = df.resample(rule, label='left', closed='left').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    })
    return resampled.dropna()

def find_best_base_file(requested_tf, available_files):
    """
    Determines the best source file to use for resampling.
    
    Strategy:
    - If exact match exists, use it.
    - If requested is Daily/Weekly/Monthly (>= 1D), try to use '1D' or '1W' to preserve settlement closes.
    - If requested is Intraday (< 1D), use '1m' for best precision, or '1h' if '1m' missing.
    """
    if requested_tf in available_files:
        return requested_tf
        
    req_mult, req_unit = parse_timeframe(requested_tf)
    
    # Daily or higher
    if req_unit in ['D', 'W', 'M']:
        # Prefer 1D for 2D, 3D, etc.
        if '1D' in available_files: return '1D'
        if '1W' in available_files and req_unit in ['W', 'M']: return '1W'
        # Fallback to intraday if no daily file (unlikely but possible)
        if '1h' in available_files: return '1h'
        if '1m' in available_files: return '1m'
        
    # Intraday (minutes or hours)
    if req_unit in ['m', 'min', 'h', 'H']:
        # Ideally use 1m for everything to get correct high/lows
        if '1m' in available_files: return '1m'
        # If 1m missing, use 5m, 15m, etc.
        if '5m' in available_files: return '5m'
        if '15m' in available_files: return '15m'
        if '1h' in available_files: return '1h'
        
    # Default: return whatever is available (maybe sorted by resolution?)
    return available_files[0] if available_files else None

