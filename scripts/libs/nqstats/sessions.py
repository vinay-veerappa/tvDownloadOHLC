"""
NQ1 Statistics Logic - Session Definition and Range Extraction
Based on NQStats Unified Bias Algorithm.
"""

import pandas as pd
import numpy as np
from datetime import time, datetime, timedelta

# NQStats Official Killzone Windows (US/Eastern)
# Unified Bias Algorithm Official Windows (US/Eastern)
DEFAULT_SESSION_CONFIG = {
    'Asia': {'start': time(18, 0), 'end': time(2, 0)},
    'London': {'start': time(3, 0), 'end': time(8, 0)},
    'Pre-NY': {'start': time(8, 0), 'end': time(9, 30)},
    'IB': {'start': time(9, 30), 'end': time(10, 30)},
    'RTH': {'start': time(9, 30), 'end': time(16, 0)},
    'NY_AM': {'start': time(9, 30), 'end': time(12, 0)},
}

PROFILER_BOX_CONFIG = {
    'AsiaBox': {'start': time(18, 0), 'end': time(19, 30)},
    'LondonBox': {'start': time(2, 30), 'end': time(3, 30)},
    'NY1Box': {'start': time(7, 30), 'end': time(8, 30)},
    'NY2Box': {'start': time(11, 30), 'end': time(12, 30)},
}


def get_nq_session_ranges(ohlc: pd.DataFrame, session_name: str, config: dict, 
                          precalc_times=None, precalc_dates=None) -> pd.DataFrame:
    """
    Extract high, low, open, close, and midpoint for a specific NQ session.
    Calculated vectorially across the entire DataFrame.
    """
    if session_name not in config:
        raise ValueError(f"Unknown session: {session_name}")
        
    s_config = config[session_name]
    start_t, end_t = s_config['start'], s_config['end']
    
    # Ensure index is localized to US/Eastern
    df = ohlc.tz_convert('US/Eastern') if ohlc.index.tz else ohlc
    times = precalc_times if precalc_times is not None else df.index.time
    
    # Create mask for the session
    if start_t < end_t:
        mask = (times >= start_t) & (times < end_t)
        groups = precalc_dates if precalc_dates is not None else df.index.date
    else:
        # Overnight sessions (Asia 18:00 - 02:00)
        mask = (times >= start_t) | (times < end_t)
        # For overnight, groups must be date + 1 for PM hours
        pm_mask = (times >= start_t)
        group_dates = pd.Series(precalc_dates if precalc_dates is not None else df.index.date, index=df.index)
        group_dates.loc[pm_mask] = group_dates.loc[pm_mask] + pd.Timedelta(days=1)
        groups = group_dates

    # PERFORMANCE OPTIMIZATION:
    # Instead of multiple groupby().transform() calls on the entire DataFrame (O(N)),
    # we operate only on the relevant subset to extract the per-group metrics, 
    # then map them back to the full index.
    
    subset = df.loc[mask, ['open', 'high', 'low', 'close']]
    sub_groups = groups[mask] if isinstance(groups, pd.Series) else pd.Series(groups, index=df.index)[mask]
    
    # Aggregate only once
    agg = subset.groupby(sub_groups).agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last'
    })
    
    # Reindex to full groups to use vectorized mapping
    full_groups = pd.Series(groups, index=df.index)
    res_map = agg.reindex(full_groups.values)
    res_map.index = df.index
    
    prefix = session_name.lower()
    return pd.DataFrame({
        f"{prefix}_open": res_map['open'],
        f"{prefix}_high": res_map['high'],
        f"{prefix}_low": res_map['low'],
        f"{prefix}_mid": (res_map['high'] + res_map['low']) / 2,
        f"{prefix}_close": res_map['close'],
        f"{prefix}_active": np.where(mask, 1, 0)
    }, index=df.index)

def extract_all_sessions(df_et: pd.DataFrame, 
                         killzone_config: dict = DEFAULT_SESSION_CONFIG, 
                         box_config: dict = PROFILER_BOX_CONFIG) -> pd.DataFrame:
    """
    Wrapper to extract ALL relevant session ranges for a ticker.
    Automatically handles pre-calculation for performance.
    """
    times = df_et.index.time
    dates = df_et.index.date
    results = []
    
    # 1. Standard Killzones
    for sess in killzone_config.keys():
        results.append(get_nq_session_ranges(df_et, sess, killzone_config, times, dates))
        
    # 2. Profiler Boxes
    for sess in box_config.keys():
        results.append(get_nq_session_ranges(df_et, sess, box_config, times, dates))
    
    return pd.concat(results, axis=1)
