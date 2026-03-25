"""
VWAP Calculation Service with Advanced Settings

OPTIMIZED VERSION - Uses vectorized operations instead of .apply()

Supports:
- Anchor periods: session, week, month
- Custom anchor time (e.g., 09:30 for RTH start)
- Standard deviation bands
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
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
    
    if df.empty:
        return {'vwap': []}
    
    # Create working copy
    df = df.copy()
    
    # Handle missing volume - replace zeros and NaN with 1 for equal weighting
    # This prevents NaN when calculating VWAP for bars with missing/0 volume
    if 'volume' not in df.columns:
        df['volume'] = 1
    else:
        # Fill NaN with 0, then replace all zeros with 1
        df['volume'] = df['volume'].fillna(0).replace(0, 1)
    
    # Create datetime index
    df['datetime'] = pd.to_datetime(df['time'], unit='s', utc=True)
    
    # Convert to anchor timezone
    tz = pytz.timezone(anchor_timezone)
    df['datetime_local'] = df['datetime'].dt.tz_convert(tz)
    
    # Calculate source price (vectorized)
    if source == 'hlc3':
        source_price = (df['high'].values + df['low'].values + df['close'].values) / 3
    elif source == 'ohlc4':
        source_price = (df['open'].values + df['high'].values + df['low'].values + df['close'].values) / 4
    else:  # close
        source_price = df['close'].values
    
    df['source'] = source_price
    
    # Parse anchor time
    anchor_hour, anchor_minute = 9, 30  # Default RTH start
    if anchor_time:
        parts = anchor_time.split(':')
        anchor_hour = int(parts[0])
        anchor_minute = int(parts[1]) if len(parts) > 1 else 0
    
    # OPTIMIZED: Create group keys using vectorized operations
    if anchor == 'session':
        # Vectorized session grouping
        # Extract hour and minute as numpy arrays
        hours = df['datetime_local'].dt.hour.values
        minutes = df['datetime_local'].dt.minute.values
        dates = df['datetime_local'].dt.date.values
        
        # Determine if each row is before anchor time
        before_anchor = (hours < anchor_hour) | ((hours == anchor_hour) & (minutes < anchor_minute))
        
        # For rows before anchor, shift date back by 1 day
        # Convert dates to pandas for date arithmetic
        date_series = pd.Series(dates)
        shifted_dates = (pd.to_datetime(date_series) - pd.Timedelta(days=1)).dt.date.values
        
        # Use numpy where for vectorized conditional assignment
        df['group'] = np.where(before_anchor, shifted_dates, dates)
    
    elif anchor == 'week':
        # OPTIMIZED: Vectorized week grouping
        # Get the start of each week (Monday) directly
        # isocalendar gives (year, week, weekday) - weekday 1=Monday
        dt_local = df['datetime_local']
        
        # Calculate days since Monday (weekday: Mon=0, Sun=6 for .weekday())
        days_since_monday = dt_local.dt.weekday.values
        
        # Subtract days to get Monday of that week
        week_starts = (dt_local - pd.to_timedelta(days_since_monday, unit='D')).dt.date.values
        df['group'] = week_starts
    
    elif anchor == 'month':
        # OPTIMIZED: Vectorized month grouping
        # Get first day of each month
        df['group'] = df['datetime_local'].dt.to_period('M').dt.start_time.dt.date.values
    
    else:
        # No grouping - calculate VWAP over entire dataset
        df['group'] = 0  # Use integer for faster groupby
    
    # Calculate VWAP per group (already vectorized via pandas)
    volume = df['volume'].values
    pv = source_price * volume
    
    df['pv'] = pv
    df['cum_pv'] = df.groupby('group')['pv'].cumsum()
    df['cum_vol'] = df.groupby('group')['volume'].cumsum()
    
    # VWAP = cumulative(price * volume) / cumulative(volume)
    cum_vol = df['cum_vol'].values
    cum_pv = df['cum_pv'].values
    
    # Avoid division by zero with numpy
    with np.errstate(divide='ignore', invalid='ignore'):
        vwap = np.where(cum_vol > 0, cum_pv / cum_vol, np.nan)
    
    df['vwap'] = vwap
    
    # OPTIMIZED: Use numpy for result serialization
    def to_nullable_list(arr: np.ndarray) -> List[Optional[float]]:
        """Convert numpy array to list with None for NaN values."""
        result = arr.tolist()
        # Replace NaN with None (faster than list comprehension for large arrays)
        return [None if (isinstance(v, float) and np.isnan(v)) else v for v in result]
    
    result = {
        'vwap': to_nullable_list(vwap)
    }
    
    # Calculate standard deviation bands
    if bands:
        # Calculate squared deviation from VWAP (vectorized)
        dev_sq = ((source_price - vwap) ** 2) * volume
        df['dev_sq'] = dev_sq
        df['cum_dev_sq'] = df.groupby('group')['dev_sq'].cumsum()
        
        # Standard deviation = sqrt(cumulative weighted variance)
        cum_dev_sq = df['cum_dev_sq'].values
        with np.errstate(divide='ignore', invalid='ignore'):
            std = np.where(cum_vol > 0, np.sqrt(cum_dev_sq / cum_vol), np.nan)
        
        for mult in bands:
            mult_str = str(mult).replace('.', '_')
            upper_key = f'vwap_upper_{mult_str}'
            lower_key = f'vwap_lower_{mult_str}'
            
            upper = vwap + (std * mult)
            lower = vwap - (std * mult)
            
            result[upper_key] = to_nullable_list(upper)
            result[lower_key] = to_nullable_list(lower)
    
    return result


def should_hide_vwap(timeframe: str) -> bool:
    """
    Check if VWAP should be hidden for this timeframe.
    VWAP doesn't make sense on daily or higher timeframes.
    
    Examples:
        1m, 5m, 15m, 1h, 4h -> False (show VWAP)
        1D, D, 1W, W, 1M, M -> True (hide VWAP)
    """
    tf = timeframe.strip()
    
    # Check for daily patterns: 1D, D, 1d, d
    if tf.endswith('D') or tf.endswith('d'):
        return True
    
    # Check for weekly patterns: 1W, W, 1w, w
    if tf.endswith('W') or tf.endswith('w'):
        return True
    
    # Check for monthly patterns - only if it ends with M (not 1m, 5m which are minutes)
    # Monthly is typically just "M" or "1M" - digits followed by M
    if tf.endswith('M') and (tf == 'M' or (len(tf) >= 2 and tf[-2].isdigit())):
        return True
    
    return False

