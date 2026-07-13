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


def get_gap_consequent_encroachment(gaps_df: pd.DataFrame) -> pd.Series:
    """Calculates the 50% midpoint (Consequent Encroachment) of detected gaps."""
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


@validate_ohlc(input_type="ohlc")
def detect_gap_fills(ohlc: pd.DataFrame, gaps_df: pd.DataFrame) -> pd.DataFrame:
    """Track when opening gaps (NWOG/NDOG/RTH) get filled by subsequent price.

    A gap is considered **filled** when price trades back into the gap zone
    (between ``gap_top`` and ``gap_bottom``). For a gap up (open > prev close),
    fill occurs when ``low <= gap_top``. For a gap down (open < prev close),
    fill occurs when ``high >= gap_bottom``.

    Parameters
    ----------
    ohlc : pd.DataFrame
        OHLC data at any timeframe (should be the same data used to detect
        the gaps, or a finer timeframe for more precise fill detection).
    gaps_df : pd.DataFrame
        Output from ``detect_opening_gaps`` or ``detect_rth_gaps`` — must
        contain ``gap_top`` and ``gap_bottom`` columns, with non-NaN values
        at the bar where the gap opened.

    Returns
    -------
    pd.DataFrame with the same index as ``gaps_df``, adding:
        filled        — 1 if the gap has been filled, 0 otherwise
        fill_time     — timestamp of the bar that first filled the gap
        fill_price    — price at which the gap was filled (midpoint of the
                        filling bar's range that overlaps the gap)
    """
    high = ohlc["high"].values
    low = ohlc["low"].values
    gap_top = gaps_df["gap_top"].values
    gap_bottom = gaps_df["gap_bottom"].values

    # Identify bars where a gap opened
    gap_open_mask = ~np.isnan(gap_top)
    gap_open_indices = np.where(gap_open_mask)[0]

    filled = np.zeros(len(ohlc), dtype=np.int64)
    fill_time = np.full(len(ohlc), np.nan, dtype=object)
    fill_price = np.full(len(ohlc), np.nan, dtype=float)

    for idx in gap_open_indices:
        g_top = gap_top[idx]
        g_bot = gap_bottom[idx]
        # Determine gap direction: gap up if open_price > close_price (gap_top == open_price)
        # We check if price returns to the gap zone
        # Gap up: fill when low <= gap_top (price comes back down into gap)
        # Gap down: fill when high >= gap_bottom (price comes back up into gap)
        is_gap_up = g_top > g_bot  # simplified: gap exists

        # Search forward from the bar after the gap
        if is_gap_up:
            # Price needs to come back down to gap_top to fill
            search_high = high[idx + 1:]
            search_low = low[idx + 1:]
            # Fill when low penetrates gap_top (enters the gap zone)
            fill_mask = search_low <= g_top
        else:
            search_high = high[idx + 1:]
            fill_mask = search_high >= g_bot

        if np.any(fill_mask):
            fill_idx = np.argmax(fill_mask) + idx + 1
            filled[idx] = 1
            fill_time[idx] = ohlc.index[fill_idx]
            # Fill price = the gap midpoint (consequent encroachment) where price first entered
            fill_price[idx] = (g_top + g_bot) / 2.0

    # Convert fill_time to datetime where set, NaN otherwise
    fill_time_series = pd.Series(fill_time, index=ohlc.index)
    fill_time_series = pd.to_datetime(fill_time_series, errors="coerce", utc=False)

    return pd.DataFrame({
        "filled": filled,
        "fill_time": fill_time_series,
        "fill_price": fill_price,
    }, index=ohlc.index)
