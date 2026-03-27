import pandas as pd
import numpy as np
from datetime import datetime
from .validation import validate_ohlc

# Official ICT Killzones (New York / ET Standard)
KILLZONES = {
    "asian": ("20:00", "00:00"),
    "london_open": ("02:00", "05:00"),
    "ny_open": ("08:30", "11:00"),
    "london_close": ("10:00", "12:00")
}

# Official ICT Macros (New York / ET Standard)
MACROS = {
    "london_macro_1": ("02:33", "03:00"),
    "london_macro_2": ("04:03", "04:30"),
    "ny_am_macro": ("08:50", "09:10"),
    "ny_morning_macro": ("09:50", "10:10"),
    "ny_mid_morning_macro": ("10:50", "11:10"),
    "ny_lunch_macro_1": ("11:50", "12:10"),
    "ny_lunch_macro_2": ("13:10", "13:40"),
    "ny_last_hour_macro": ("15:15", "15:45")
}

# RTH Sessions (ET) - Gap detection ranges
RTH_SESSIONS = {
    "NQ1": ("09:30", "16:15"),
    "ES1": ("09:30", "16:15"),
    "YM1": ("09:30", "16:15"),
    "RTY1": ("09:30", "16:15"),
    "CL1": ("09:00", "14:30"),
    "GC1": ("08:20", "13:30"),
}

@validate_ohlc(input_type="ohlc")
def get_session_data(ohlc: pd.DataFrame, session_name: str, timezone: str = "US/Eastern") -> pd.DataFrame:
    """
    Vectorized session detection for Killzones.
    Normalized to US/Eastern to match institutional standards.
    """
    if session_name not in KILLZONES:
        raise ValueError(f"Unknown session: {session_name}")
        
    start, end = KILLZONES[session_name]
    start_t = datetime.strptime(start, "%H:%M").time()
    end_t = datetime.strptime(end, "%H:%M").time()
    
    # Ensure index is localized and converted to US/Eastern
    if ohlc.index.tz is not None:
        et_df = ohlc.tz_convert(timezone)
    else:
        # Assume UTC if no tz found and convert
        et_df = ohlc.tz_localize('UTC').tz_convert(timezone)
        
    times = et_df.index.time
    
    # Check if time falls within the window (handle overnight sessions)
    if start_t < end_t:
        mask = (times >= start_t) & (times <= end_t)
    else:
        mask = (times >= start_t) | (times <= end_t)
        
    session_active = np.where(mask, 1, 0)
    
    # High/Low for the specific session
    high = et_df["high"].where(mask).groupby(et_df.index.date).transform("max")
    low = et_df["low"].where(mask).groupby(et_df.index.date).transform("min")
    
    return pd.DataFrame({
        "active": session_active,
        "session_high": high,
        "session_low": low
    }, index=ohlc.index)

@validate_ohlc(input_type="ohlc")
def get_macro_data(ohlc: pd.DataFrame, macro_name: str, timezone: str = "US/Eastern") -> pd.DataFrame:
    """
    Vectorized macro window detection.
    Default timezone is US/Eastern as ICT macros are anchored in New York time.
    """
    if macro_name not in MACROS:
        raise ValueError(f"Unknown macro: {macro_name}. Available: {list(MACROS.keys())}")
        
    start, end = MACROS[macro_name]
    start_t = datetime.strptime(start, "%H:%M").time()
    end_t = datetime.strptime(end, "%H:%M").time()
    
    # Convert index to timezone if needed and get time
    if ohlc.index.tz is not None:
        et_df = ohlc.tz_convert(timezone)
    else:
        # Assume UTC if no tz found and convert
        et_df = ohlc.tz_localize('UTC').tz_convert(timezone)
        
    times = et_df.index.time
    
    # Check if time falls within the window
    if start_t < end_t:
        mask = (times >= start_t) & (times <= end_t)
    else:
        mask = (times >= start_t) | (times <= end_t)
        
    macro_active = np.where(mask, 1, 0)
    
    # Macro High/Low
    high = ohlc["high"].where(mask).groupby(ohlc.index.date).transform("max")
    low = ohlc["low"].where(mask).groupby(ohlc.index.date).transform("min")
    
    return pd.DataFrame({
        "active": macro_active,
        "macro_high": high,
        "macro_low": low
    }, index=ohlc.index)
