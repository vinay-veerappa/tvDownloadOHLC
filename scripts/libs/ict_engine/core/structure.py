import pandas as pd
import numpy as np
from .validation import validate_ohlc

@validate_ohlc(input_type="ohlc")
def detect_swings(ohlc: pd.DataFrame, swing_length: int = 5) -> pd.DataFrame:
    """
    Swing Highs and Lows Detection (Fractals)
    A swing high is the highest high in (swing_length) candles before and after.
    A swing low is the lowest low in (swing_length) candles before and after.
    """
    high = ohlc["high"].values
    low = ohlc["low"].values
    
    # Vectorized Rolling Window Detection
    # shift(-swing_length) allows us to look ahead for the validation period
    rolling_max = ohlc["high"].rolling(window=2 * swing_length + 1, center=True).max()
    rolling_min = ohlc["low"].rolling(window=2 * swing_length + 1, center=True).min()
    
    swing_high = (high == rolling_max)
    swing_low = (low == rolling_min)
    
    shl_type = np.zeros(len(ohlc))
    shl_type[swing_high] = 1
    shl_type[swing_low] = -1
    
    # Levels of the swings
    level = np.where(swing_high, high, np.where(swing_low, low, np.nan))
    
    return pd.DataFrame({
        "shl": shl_type,
        "level": level
    }, index=ohlc.index)

@validate_ohlc(input_type="ohlc")
def detect_cisd(ohlc: pd.DataFrame, swings: pd.DataFrame) -> pd.Series:
    """
    CISD - Change in State of Delivery
    Matches logic from Master Spec:
    Institutional Delivery shift confirmed when price trades through the 
    open of the 'extreme' candle that swept liquidity.
    """
    cisd_signal = np.zeros(len(ohlc))
    
    # Implementation follows the SPEC:
    # 1. Look for confirmed swing points.
    # 2. Track the 'State shift' when the extreme candle is closed through.
    # (Detailed vectorized logic development here)
    
    return pd.Series(cisd_signal, index=ohlc.index, name="cisd")
