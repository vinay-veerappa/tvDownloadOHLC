import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from .validation import validate_ohlc
from .sessions import RTH_SESSIONS

@validate_ohlc(input_type="ohlc")
def detect_opening_gaps(ohlc: pd.DataFrame, timezone: str = "US/Eastern") -> pd.DataFrame:
    """
    Detects NDOG (New Day Opening Gap) and NWOG (New Week Opening Gap).
    
    Reference logic from generate_ict_nwog_ndog.py:
    - Anchors on the SESSION OPEN (18:00 ET).
    - Identifies gaps > 45 minutes leading into an 18:00 ET candle.
    - NWOG if previous candle closed on Friday (weekday 4).
    - NDOG if previous candle closed on Mon-Thu (0, 1, 2, 3).
    """
    if ohlc.index.tz is None:
        # Assume UTC if not provided, then convert to ET for gap logic
        df_et = ohlc.tz_localize("UTC").tz_convert(timezone)
    else:
        df_et = ohlc.tz_convert(timezone)

    # Time difference to identify gaps
    time_diff = df_et.index.to_series().diff()
    
    # Mask for potential gap starts (18:00 ET open after a >45m gap)
    is_session_open = (df_et.index.hour == 18) & (df_et.index.minute == 0)
    significant_gap = (time_diff > pd.Timedelta(minutes=45))
    
    gap_starts = is_session_open & significant_gap
    
    # Vectorized extraction of close/open around gaps
    curr_open = ohlc["open"].values
    prev_close = np.roll(ohlc["close"].values, 1)
    
    # Weekday of the PREVIOUS candle
    # We shift the index to align with prev_close
    prev_weekdays = df_et.index.to_series().shift(1).dt.weekday
    
    # Logic for NWOG/NDOG
    is_nwog = gap_starts & (prev_weekdays == 4)
    is_ndog = gap_starts & (prev_weekdays.isin([0, 1, 2, 3]))
    
    # Gap Boundaries
    top = np.where(gap_starts, np.maximum(curr_open, prev_close), np.nan)
    bottom = np.where(gap_starts, np.minimum(curr_open, prev_close), np.nan)
    
    return pd.DataFrame({
        "nwog": np.where(is_nwog, 1, 0),
        "ndog": np.where(is_ndog, 1, 0),
        "gap_top": top,
        "gap_bottom": bottom
    }, index=ohlc.index)

@validate_ohlc(input_type="ohlc")
def get_gap_consequent_encroachment(gaps_df: pd.DataFrame) -> pd.Series:
    """
    Calculates the 50% midpoint (Consequent Encroachment) of the detected gaps.
    """
    ce = (gaps_df["gap_top"] + gaps_df["gap_bottom"]) / 2
    return pd.Series(ce, index=gaps_df.index, name="gap_ce")

@validate_ohlc(input_type="ohlc")
def detect_rth_gaps(ohlc: pd.DataFrame, ticker: str = "ES1", timezone: str = "US/Eastern") -> pd.DataFrame:
    """
    RTH Gap - Regular Trading Hours Gap detection.
    Gap = Today's Open (e.g., 09:30) - Previous Day's Close (e.g., 16:15).
    """
    if ohlc.index.tz is None:
        df_et = ohlc.tz_localize("UTC").tz_convert(timezone)
    else:
        df_et = ohlc.tz_convert(timezone)
    
    config = RTH_SESSIONS.get(ticker, RTH_SESSIONS["ES1"])
    open_t_str, close_t_str = config
    open_time = datetime.strptime(open_t_str, "%H:%M").time()
    close_time = datetime.strptime(close_t_str, "%H:%M").time()
    
    # Identify Open and Close bars
    is_rth_open = (df_et.index.hour == open_time.hour) & (df_et.index.minute == open_time.minute)
    is_rth_close = (df_et.index.hour == close_time.hour) & (df_et.index.minute == close_time.minute)
    
    # Extract RTH Close prices and propagate (forward fill)
    # The shift(1) ensures that at 09:30 today, we strictly see the YESTERDAY 16:15 close.
    rth_closes = ohlc["close"].where(is_rth_close).ffill().shift(1)
    
    # RTH Gaps marked only at the Open bar
    rth_gap_mask = is_rth_open
    
    # Gap boundaries
    top = np.where(rth_gap_mask, np.maximum(ohlc["open"], rth_closes), np.nan)
    bottom = np.where(rth_gap_mask, np.minimum(ohlc["open"], rth_closes), np.nan)
    
    return pd.DataFrame({
        "rth_gap": np.where(rth_gap_mask, 1, 0),
        "gap_top": top,
        "gap_bottom": bottom
    }, index=ohlc.index)
