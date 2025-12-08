"""
VWAP Calculation Service with Advanced Settings

Supports:
- Anchor periods: session, week, month
- Custom anchor time (e.g., 09:30 for RTH start)
- Standard deviation bands
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import time
import pytz


def calculate_vwap_with_settings(
    df: pd.DataFrame,
    anchor: str = "session",
    anchor_time: str = "09:30",
    anchor_timezone: str = "America/New_York",
    bands: List[float] = None,
    source: str = "hlc3"
) -> Dict[str, List[Optional[float]]]:
    """
    Calculate VWAP with advanced settings.
    
    Args:
        df: DataFrame with columns [time, open, high, low, close, volume]
            where 'time' is Unix timestamp
        anchor: 'session' (daily), 'week', 'month'
        anchor_time: Time to reset VWAP (e.g., '09:30' for 9:30 AM)
        anchor_timezone: Timezone for anchor time (e.g., 'America/New_York')
        bands: List of standard deviation multipliers [1.0, 2.0, 3.0]
        source: Price source - 'hlc3', 'close', 'ohlc4'
    
    Returns:
        Dict with 'vwap', 'upper_1', 'lower_1', etc.
    """
    if bands is None:
        bands = [1.0]
    
    # Create datetime index
    df = df.copy()
    df['datetime'] = pd.to_datetime(df['time'], unit='s', utc=True)
    
    # Convert to anchor timezone
    tz = pytz.timezone(anchor_timezone)
    df['datetime_local'] = df['datetime'].dt.tz_convert(tz)
    
    # Calculate source price
    if source == 'hlc3':
        df['source'] = (df['high'] + df['low'] + df['close']) / 3
    elif source == 'ohlc4':
        df['source'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4
    else:  # close
        df['source'] = df['close']
    
    # Parse anchor time
    anchor_hour, anchor_minute = 9, 30  # Default RTH start
    if anchor_time:
        parts = anchor_time.split(':')
        anchor_hour = int(parts[0])
        anchor_minute = int(parts[1]) if len(parts) > 1 else 0
    
    # Create group keys based on anchor period
    if anchor == 'session':
        # Group by date, but a new group starts at anchor_time
        def get_session_group(dt):
            local_dt = dt
            # If before anchor time, belongs to previous day's session
            if local_dt.hour < anchor_hour or (local_dt.hour == anchor_hour and local_dt.minute < anchor_minute):
                return (local_dt - pd.Timedelta(days=1)).date()
            return local_dt.date()
        
        df['group'] = df['datetime_local'].apply(get_session_group)
    
    elif anchor == 'week':
        # Group by week number, starting at anchor_time on the first day of week
        df['group'] = df['datetime_local'].dt.to_period('W').apply(lambda x: x.start_time.date())
    
    elif anchor == 'month':
        # Group by month
        df['group'] = df['datetime_local'].dt.to_period('M').apply(lambda x: x.start_time.date())
    
    else:
        # No grouping - calculate VWAP over entire dataset
        df['group'] = 'all'
    
    # Calculate VWAP per group
    df['pv'] = df['source'] * df['volume']  # Price * Volume
    df['cum_pv'] = df.groupby('group')['pv'].cumsum()
    df['cum_vol'] = df.groupby('group')['volume'].cumsum()
    
    # VWAP = cumulative(price * volume) / cumulative(volume)
    df['vwap'] = df['cum_pv'] / df['cum_vol']
    
    # Handle division by zero
    df['vwap'] = df['vwap'].replace([np.inf, -np.inf], np.nan)
    
    result = {
        'vwap': [None if pd.isna(v) else v for v in df['vwap'].tolist()]
    }
    
    # Calculate standard deviation bands
    if bands:
        # Calculate squared deviation from VWAP
        df['dev_sq'] = ((df['source'] - df['vwap']) ** 2) * df['volume']
        df['cum_dev_sq'] = df.groupby('group')['dev_sq'].cumsum()
        
        # Standard deviation = sqrt(cumulative weighted variance)
        df['std'] = np.sqrt(df['cum_dev_sq'] / df['cum_vol'])
        
        for mult in bands:
            mult_str = str(mult).replace('.', '_')
            upper_key = f'vwap_upper_{mult_str}'
            lower_key = f'vwap_lower_{mult_str}'
            
            df[upper_key] = df['vwap'] + (df['std'] * mult)
            df[lower_key] = df['vwap'] - (df['std'] * mult)
            
            result[upper_key] = [None if pd.isna(v) else v for v in df[upper_key].tolist()]
            result[lower_key] = [None if pd.isna(v) else v for v in df[lower_key].tolist()]
    
    return result


def should_hide_vwap(timeframe: str) -> bool:
    """
    Check if VWAP should be hidden for this timeframe.
    VWAP doesn't make sense on daily or higher timeframes.
    """
    timeframe = timeframe.upper()
    # Hide for daily, weekly, monthly
    if 'D' in timeframe or 'W' in timeframe or 'M' in timeframe:
        return True
    return False
