import pandas as pd
import numpy as np
from typing import Optional
from .validation import validate_ohlc

@validate_ohlc(input_type="ohlc")
def detect_ttrade_fractal(ohlc: pd.DataFrame) -> pd.DataFrame:
    """
    TTrades Fractal Model (C1-C4). Includes C2 reversal + C3 confirmation.
    C1: Anchor bar (i-2)
    C2: Reversal bar (i-1) - wicks beyond C1 extreme and closes back inside
    C3: Confirmation bar (i) - body closes in directional direction
    """
    high = ohlc["high"]
    low = ohlc["low"]
    close = ohlc["close"]
    open_ = ohlc["open"]
    
    # Shifts to prevent roll wrap-around
    low_1 = low.shift(1)  # C2 low
    low_2 = low.shift(2)  # C1 low
    high_1 = high.shift(1)# C2 high
    high_2 = high.shift(2)# C1 high
    close_1 = close.shift(1)
    
    # C2 Bullish Reversal: low[i-1] < low[i-2] & close[i-1] > low[i-2]
    c2_bull = (low_1 < low_2) & (close_1 > low_2) & low_2.notna()
    # C2 Bearish Reversal: high[i-1] > high[i-2] & close[i-1] < high[i-2]
    c2_bear = (high_1 > high_2) & (close_1 < high_2) & high_2.notna()
    
    # C3 Confirmation: C2 was active and C3 candle body direction confirms
    c3_bull_conf = c2_bull & (close > open_)
    c3_bear_conf = c2_bear & (close < open_)
    
    reversal_type = np.where(c2_bull, 1, np.where(c2_bear, -1, 0))
    confirmation_type = np.where(c3_bull_conf, 1, np.where(c3_bear_conf, -1, 0))
    
    return pd.DataFrame({
        "ttrade_reversal": reversal_type,
        "ttrade_confirmation": confirmation_type
    }, index=ohlc.index)

@validate_ohlc(input_type="ohlc")
def quarterly_cycles(ohlc: pd.DataFrame, timezone: str = "US/Eastern") -> pd.DataFrame:
    """
    Quarterly Theory (90-minute Cycles).
    Divides each 6-hour macro period into 4 x 90-minute quarters (Q1 Accumulation, Q2 Manipulation, Q3 Distribution, Q4 Reversal/Continuation).
    Anchored to 00:00, 06:00, 12:00, 18:00 ET.
    """
    if ohlc.index.tz is not None:
        et_df = ohlc.tz_convert(timezone)
    else:
        et_df = ohlc.tz_localize("UTC").tz_convert(timezone)
        
    minutes_from_midnight = et_df.index.hour * 60 + et_df.index.minute
    # Each 6-hour block (360 mins) has 4 x 90-min quarters
    quarter_in_block = (minutes_from_midnight % 360) // 90 + 1
    
    # Cycle Open: Open price at start of current 90-min quarter
    is_q_open = (minutes_from_midnight % 90 == 0)
    cycle_open = et_df["open"].where(is_q_open).ffill().values
    
    return pd.DataFrame({
        "quarter": quarter_in_block,
        "cycle_open": cycle_open
    }, index=ohlc.index)

@validate_ohlc(input_type="ohlc")
def detect_po3(ohlc: pd.DataFrame, timezone: str = "US/Eastern", session_mask: Optional[pd.Series] = None) -> pd.DataFrame:
    """
    Power of 3 (PO3) model: Accumulation, Manipulation, Distribution (AMD).
    Divides regular session (00:00 to 16:00 ET) into standard PO3 phases:
      - Accumulation: 00:00 - 05:00 ET (Asian & Early London)
      - Manipulation (Judas Swing): 05:00 - 09:30 ET (London & Pre-Market)
      - Distribution: 09:30 - 16:00 ET (NY AM & PM)
    """
    if ohlc.index.tz is not None:
        et_df = ohlc.tz_convert(timezone)
    else:
        et_df = ohlc.tz_localize("UTC").tz_convert(timezone)

    times = et_df.index.time
    
    acc_mask = (times >= pd.Timestamp("00:00").time()) & (times < pd.Timestamp("05:00").time())
    man_mask = (times >= pd.Timestamp("05:00").time()) & (times < pd.Timestamp("09:30").time())
    dis_mask = (times >= pd.Timestamp("09:30").time()) & (times < pd.Timestamp("16:00").time())
    
    phases = np.full(len(ohlc), "NONE", dtype=object)
    phases[acc_mask] = "ACCUMULATION"
    phases[man_mask] = "MANIPULATION"
    phases[dis_mask] = "DISTRIBUTION"
    
    is_day_open = (times == pd.Timestamp("00:00").time())
    day_open = et_df["open"].where(is_day_open).ffill().values

    return pd.DataFrame({
        "phase": phases,
        "opening_price": day_open
    }, index=ohlc.index)
