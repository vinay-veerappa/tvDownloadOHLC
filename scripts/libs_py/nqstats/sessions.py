"""
NQ1 Statistics Logic - Session Definition and Range Extraction
Based on NQStats Unified Bias Algorithm.
"""

import pandas as pd
import numpy as np
from datetime import time, datetime, timedelta
import pytz
from typing import Tuple, Optional, Union

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


def get_logical_trading_date(index: pd.DatetimeIndex) -> pd.Series:
    """
    Calculates logical trading date rolling at 18:00 ET, skipping weekends.
    Vectorized and ADR-001/ADR-004 compliant.
    """
    shifted = index + pd.Timedelta(hours=6)
    raw_dates = pd.Series(shifted.date, index=index)
    weekday = shifted.weekday
    days_to_add = np.where(weekday == 5, 2, np.where(weekday == 6, 1, 0))
    logical_dates = pd.to_datetime(raw_dates) + pd.to_timedelta(days_to_add, unit='D')
    return logical_dates.dt.date


def get_trading_date(ts):
    """
    Unified institutional trading-date helper (ADR-001).
    Trading day rolls at 18:00 ET; weekend dates snap forward to Monday.

    Accepts:
      - pd.Timestamp / datetime.datetime  → returns a single datetime.date
      - pd.DatetimeIndex                 → returns pd.Series[date]  (vectorized)
      - pd.Series of timestamps          → returns pd.Series[date]  (vectorized)
    """
    # ── Scalar branch ──────────────────────────────────────────────────────────
    if isinstance(ts, (pd.Timestamp, datetime)):
        shifted = pd.Timestamp(ts) + pd.Timedelta(hours=6)
        base = shifted.date()
        wd = shifted.weekday()
        if wd == 5:   # Saturday → Monday
            base += timedelta(days=2)
        elif wd == 6: # Sunday → Monday
            base += timedelta(days=1)
        return base

    # ── Vectorized branch (DatetimeIndex or Series) ────────────────────────────
    if isinstance(ts, pd.Series):
        idx = pd.DatetimeIndex(ts)
        orig_index = ts.index
    else:
        idx = ts
        orig_index = ts

    shifted = idx + pd.Timedelta(hours=6)
    raw_dates = pd.Series(shifted.date, index=orig_index)
    weekday = shifted.weekday
    days_to_add = np.where(weekday == 5, 2, np.where(weekday == 6, 1, 0))
    logical_dates = pd.to_datetime(raw_dates) + pd.to_timedelta(days_to_add, unit='D')
    return logical_dates.dt.date


def get_dst_flags(timestamps: pd.DatetimeIndex) -> Tuple[pd.Series, pd.Series]:
    """
    Given a DatetimeIndex in UTC or naive ET, returns us_dst and uk_dst boolean Series.
    Uses daily resolution mapping for maximum performance (ADR-017).
    """
    orig_idx = timestamps
    
    # Drop any NaT values first to avoid errors
    clean_ts = timestamps[~timestamps.isna()]
    if clean_ts.empty:
        empty_series = pd.Series(False, index=orig_idx)
        return empty_series, empty_series
        
    # Get unique normalized dates (daily level)
    unique_dates = clean_ts.normalize().unique()
    
    if clean_ts.tz is None:
        try:
            # We localize daily dates to America/New_York and convert to UTC
            daily_utc = unique_dates.tz_localize('America/New_York', ambiguous='NaT', nonexistent='shift_forward').tz_convert('UTC')
        except Exception:
            daily_utc = unique_dates.tz_localize('America/New_York', ambiguous='NaT', nonexistent='shift_forward').tz_convert('UTC')
    else:
        daily_utc = unique_dates.tz_convert('UTC')
        
    # Calculate DST status daily
    daily_ny = daily_utc.tz_convert('America/New_York')
    us_dst_daily = daily_ny.map(lambda x: x.dst().total_seconds() > 0 if x is not pd.NaT and x.dst() is not None else False)
    
    daily_ld = daily_utc.tz_convert('Europe/London')
    uk_dst_daily = daily_ld.map(lambda x: x.dst().total_seconds() > 0 if x is not pd.NaT and x.dst() is not None else False)
    
    # Create maps from daily dates
    us_map = dict(zip(unique_dates, us_dst_daily))
    uk_map = dict(zip(unique_dates, uk_dst_daily))
    
    # Vectorized mapping back to minute-level resolution
    normalized_dates = timestamps.normalize()
    us_dst = pd.Series(normalized_dates.map(us_map).fillna(False).astype(bool), index=orig_idx)
    uk_dst = pd.Series(normalized_dates.map(uk_map).fillna(False).astype(bool), index=orig_idx)
    
    return us_dst, uk_dst


def get_event_anchored_times(
    session: str, 
    us_dst: bool, 
    uk_dst: bool,
    default_start: Optional[time] = None,
    default_end: Optional[time] = None
) -> Tuple[time, time, int, str]:
    """
    Computes shifted ET hours for event-anchored foreign slots.
    Returns (start_time, end_time, et_window_offset_hours, dst_regime)
    """
    if session == "Tokyo IB":
        if us_dst:
            return time(20, 0), time(21, 0), 0, "aligned"
        else:
            return time(19, 0), time(20, 0), -1, "shifted"
            
    elif session == "London IB":
        if us_dst == uk_dst:
            return time(3, 0), time(4, 0), 0, "aligned"
        elif us_dst and not uk_dst:  # US EDT, UK GMT (March shoulder)
            return time(4, 0), time(5, 0), 1, "shifted"
        else:  # US EST, UK BST (October/November shoulder)
            return time(2, 0), time(3, 0), -1, "shifted"
            
    return default_start, default_end, 0, "aligned"


def normalize_to_eastern(df_or_index: Union[pd.DataFrame, pd.DatetimeIndex]) -> Union[pd.DataFrame, pd.DatetimeIndex]:
    """
    Standard timezone normalization helper (ADR-001).
    Ensures DatetimeIndex is timezone-naive America/New_York (Eastern Time).
    Supports both pd.DataFrame and pd.DatetimeIndex.
    """
    is_df = isinstance(df_or_index, pd.DataFrame)
    idx = df_or_index.index if is_df else df_or_index
    
    if idx.tz is not None:
        idx_normalized = idx.tz_convert('America/New_York').tz_localize(None)
    else:
        idx_normalized = idx
        
    if is_df:
        df_copy = df_or_index.copy()
        df_copy.index = idx_normalized
        return df_copy
    else:
        return idx_normalized


def get_time_mask(times: np.ndarray, start_t: time, end_t: time) -> np.ndarray:
    """Creates a time mask supporting overnight crossovers."""
    if start_t < end_t:
        return (times >= start_t) & (times < end_t)
    else:
        return (times >= start_t) | (times < end_t)


def get_time_mask_vectorized(bar_times: np.ndarray, start_times: np.ndarray, end_times: np.ndarray) -> np.ndarray:
    """Vectorized time mask supporting overnight crossovers on arrays of times."""
    overnight = start_times > end_times
    return np.where(
        overnight,
        (bar_times >= start_times) | (bar_times < end_times),
        (bar_times >= start_times) & (bar_times < end_times)
    )


