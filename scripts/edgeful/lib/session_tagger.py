"""
Session and Trading Date Tagger

Tags each 1-minute bar with:
  - trading_date: Institutional trading date (rolls at 18:00 ET, handles weekends)
  - session: ASIA | LONDON | NY_PRE | NY_AM | NY_PM | ETH
  - is_rth: Boolean (09:30-16:00 ET)
  - day_of_week: 0=Monday, 4=Friday
  - minutes_into_session: Minutes elapsed since 09:30 (RTH) or -N before open

All operations use ET timezone; input DataFrame index must be datetime in ET (naive).
Per ADR-001: All times use America/New_York (ET).
"""

import pandas as pd
import numpy as np
from datetime import time as dt_time
import logging

logger = logging.getLogger(__name__)

# Session windows (ET)
SESSION_WINDOWS = {
    "ASIA": ("20:00", "02:00"),         # 20:00 - 02:00 ET (overnight setup)
    "LONDON": ("02:00", "08:00"),       # 02:00 - 08:00 ET (expansion)
    "NY_PRE": ("08:00", "09:30"),       # 08:00 - 09:30 ET (pre-market)
    "NY_AM": ("09:30", "12:00"),        # 09:30 - 12:00 ET (initial balance)
    "NY_LUNCH": ("12:00", "13:30"),     # 12:00 - 13:30 ET (lunch)
    "NY_PM": ("13:30", "16:00"),        # 13:30 - 16:00 ET (execution)
    "ETH": ("16:00", "20:00"),          # 16:00 - 20:00 ET (post-market)
}


def tag_session(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add session context columns to a DataFrame with ET datetime index.
    
    New columns (returned on a tagged copy):
      - trading_date: date (rolls at 18:00 ET, skips weekends)
      - session: ASIA | LONDON | NY_PRE | NY_AM | NY_LUNCH | NY_PM | ETH
      - is_rth: bool (09:30-16:00)
      - day_of_week: int (0=Mon, 4=Fri)
      - minutes_into_session: int (minutes since RTH open, -N before)
    
    Args:
        df: DataFrame with naive datetime index in ET timezone.
    
    Returns:
        Copy of the input DataFrame with session columns added.
    """
    if df.empty:
        logger.warning("tag_session: empty DataFrame")
        return df
    
    # Callers often pass filtered frames; work on a copy so column assignment is stable.
    df = df.copy()
    
    idx = df.index
    
    # 1. Extract hour/minute in ET (index is already naive ET per ADR-001)
    hours = idx.hour.values
    minutes = idx.minute.values
    minutes_of_day = hours * 60 + minutes
    
    # 2. Trading date with 18:00 ET rollover and weekend handling
    dates = idx.date
    trading_dates = []
    for i, dt in enumerate(idx):
        date = dt.date()
        weekday = dt.weekday()  # 0=Monday, 6=Sunday
        
        # Roll over at 18:00 ET
        if dt.hour >= 18:
            date = date + pd.Timedelta(days=1)
            weekday = (weekday + 1) % 7
        
        # Skip weekends
        while weekday in [5, 6]:  # 5=Saturday, 6=Sunday
            date = date + pd.Timedelta(days=1)
            weekday = (weekday + 1) % 7
        
        trading_dates.append(date)
    
    df["trading_date"] = trading_dates
    
    # 3. Session classification (ET-based windows)
    sessions = []
    for h, m in zip(hours, minutes):
        mom = h * 60 + m
        
        if 20 * 60 <= mom < 24 * 60:  # 20:00-23:59
            sessions.append("ASIA")
        elif 0 <= mom < 2 * 60:  # 00:00-02:00
            sessions.append("ASIA")
        elif 2 * 60 <= mom < 8 * 60:  # 02:00-08:00
            sessions.append("LONDON")
        elif 8 * 60 <= mom < 9.5 * 60:  # 08:00-09:30
            sessions.append("NY_PRE")
        elif 9.5 * 60 <= mom < 12 * 60:  # 09:30-12:00
            sessions.append("NY_AM")
        elif 12 * 60 <= mom < 13.5 * 60:  # 12:00-13:30
            sessions.append("NY_LUNCH")
        elif 13.5 * 60 <= mom < 16 * 60:  # 13:30-16:00
            sessions.append("NY_PM")
        else:  # 16:00-20:00
            sessions.append("ETH")
    
    df["session"] = pd.Categorical(
        sessions,
        categories=["ASIA", "LONDON", "NY_PRE", "NY_AM", "NY_LUNCH", "NY_PM", "ETH"],
        ordered=True
    )
    
    # 4. RTH flag (09:30-16:00)
    is_rth = (minutes_of_day >= 9.5 * 60) & (minutes_of_day < 16 * 60)
    df["is_rth"] = is_rth
    
    # 5. Day of week aligned to trading_date (not raw timestamp date)
    df["day_of_week"] = pd.to_datetime(df["trading_date"]).dt.weekday
    
    # 6. Minutes into RTH session (negative before 09:30)
    rth_start_mom = int(9.5 * 60)  # 570
    df["minutes_into_session"] = minutes_of_day - rth_start_mom
    
    logger.debug(
        f"Session tagging complete: {is_rth.sum()} RTH bars, {(~is_rth).sum()} non-RTH"
    )
    return df
