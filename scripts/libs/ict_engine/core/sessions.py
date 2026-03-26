import pandas as pd
import numpy as np
from datetime import datetime
from .validation import validate_ohlc

# Official ICT Killzones (UTC Standard)
KILLZONES = {
    "asian": ("00:00", "04:00"),
    "london_open": ("07:00", "09:00"),
    "ny_open": ("12:00", "15:00"),
    "london_close": ("15:00", "17:00")
}

@validate_ohlc(input_type="ohlc")
def get_session_data(ohlc: pd.DataFrame, session_name: str, timezone: str = "UTC") -> pd.DataFrame:
    """
    Vectorized session detection for Killzones.
    Checks if OHLC index (as time) falls within the session window.
    """
    if session_name not in KILLZONES:
        raise ValueError(f"Unknown session: {session_name}")
        
    start, end = KILLZONES[session_name]
    start_t = datetime.strptime(start, "%H:%M").time()
    end_t = datetime.strptime(end, "%H:%M").time()
    
    # Convert index to time objects (vectorized)
    times = ohlc.index.time
    
    # Check if time falls within the window (handle overnight sessions)
    if start_t < end_t:
        mask = (times >= start_t) & (times <= end_t)
    else:
        mask = (times >= start_t) | (times <= end_t)
        
    session_active = np.where(mask, 1, 0)
    
    # High/Low for the specific session
    high = ohlc["high"].where(mask).groupby(ohlc.index.date).transform("max")
    low = ohlc["low"].where(mask).groupby(ohlc.index.date).transform("min")
    
    return pd.DataFrame({
        "active": session_active,
        "session_high": high,
        "session_low": low
    }, index=ohlc.index)
