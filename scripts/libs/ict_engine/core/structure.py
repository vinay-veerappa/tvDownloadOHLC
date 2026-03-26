import pandas as pd
import numpy as np
from .validation import validate_ohlc

@validate_ohlc(input_type="ohlc")
def detect_swings(ohlc: pd.DataFrame, swing_length: int = 5) -> pd.DataFrame:
    """
    Swing Highs and Lows Detection (Fractals)
    """
    high = ohlc["high"].values
    low = ohlc["low"].values
    
    rolling_max = ohlc["high"].rolling(window=2 * swing_length + 1, center=True).max()
    rolling_min = ohlc["low"].rolling(window=2 * swing_length + 1, center=True).min()
    
    swing_high = (high == rolling_max)
    swing_low = (low == rolling_min)
    
    shl_type = np.zeros(len(ohlc))
    shl_type[swing_high] = 1
    shl_type[swing_low] = -1
    
    level = np.where(swing_high, high, np.where(swing_low, low, np.nan))
    
    return pd.DataFrame({
        "shl": shl_type,
        "level": level
    }, index=ohlc.index)

@validate_ohlc(input_type="ohlc")
def detect_structure_breaks(ohlc: pd.DataFrame, swings: pd.DataFrame) -> pd.DataFrame:
    """
    BOS and MSS Detection.
    BOS: Continuation break of structure.
    MSS: Market structure shift (Trend reversal).
    """
    close = ohlc["close"].values
    
    # 1. Track the last confirmed swing levels
    last_sh = swings["level"].where(swings["shl"] == 1).ffill().values
    last_sl = swings["level"].where(swings["shl"] == -1).ffill().values
    
    # 2. Basic Breaches
    break_high = (close > last_sh)
    break_low = (close < last_sl)
    
    # Classification logic (BOS vs MSS)
    # This requires tracking the sequence of Highs/Lows
    
    return pd.DataFrame({
        "break_high": break_high,
        "break_low": break_low,
        "level_h": last_sh,
        "level_l": last_sl
    }, index=ohlc.index)

@validate_ohlc(input_type="ohlc")
def detect_cisd(ohlc: pd.DataFrame, swings: pd.DataFrame) -> pd.DataFrame:
    """
    CISD - Change in State of Delivery
    """
    close = ohlc["close"].values
    open_ = ohlc["open"].values
    high = ohlc["high"].values
    low = ohlc["low"].values
    
    last_sh = swings["level"].where(swings["shl"] == 1).ffill().values
    last_sl = swings["level"].where(swings["shl"] == -1).ffill().values
    
    sweep_high = (high > last_sh) & (close <= last_sh)
    sweep_low = (low < last_sl) & (close >= last_sl)
    
    extreme_open = np.full(len(ohlc), np.nan)
    extreme_open[sweep_high] = open_[sweep_high]
    extreme_open[sweep_low] = open_[sweep_low]
    
    curr_extreme_open = pd.Series(extreme_open).ffill().values
    
    # Bullish Shift (State change)
    bullish_shift = (close > curr_extreme_open) & (pd.Series(sweep_low).ffill().values)
    bearish_shift = (close < curr_extreme_open) & (pd.Series(sweep_high).ffill().values)
    
    cisd_type = np.zeros(len(ohlc))
    cisd_type[bullish_shift] = 1
    cisd_type[bearish_shift] = -1
    
    return pd.DataFrame({
        "cisd": cisd_type,
        "extreme_ref": curr_extreme_open
    }, index=ohlc.index)
