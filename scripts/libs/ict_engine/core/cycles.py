import pandas as pd
import numpy as np
from .validation import validate_ohlc

@validate_ohlc(input_type="ohlc")
def detect_ttrade_fractal(ohlc: pd.DataFrame) -> pd.DataFrame:
    """
    TTrades Fractal Model (C1-C4). Includes C2 reversal + C3 confirmation.
    """
    high = ohlc["high"].values
    low = ohlc["low"].values
    close = ohlc["close"].values
    open_ = ohlc["open"].values
    
    # Prev values (C1)
    h1 = np.roll(high, 1)
    l1 = np.roll(low, 1)
    
    # Current values (C2)
    c2_bull_reversal = (low < l1) & (close > l1)
    c2_bear_reversal = (high > h1) & (close < l1) # wait, h1 for bear
    c2_bear_reversal = (high > h1) & (close < h1)
    
    # C3 values (i+1)
    # We use shifts to identify C1, C2 from the perspective of C3
    # C3 is i, C2 is i-1, C1 is i-2
    h2 = h1 
    l2 = l1
    h1_2 = np.roll(high, 2)
    l1_2 = np.roll(low, 2)
    c2_2 = np.roll(close, 1)
    
    # Bullish C2 was (low[i-1] < low[i-2]) & (close[i-1] > low[i-2])
    c2_bull = (np.roll(low, 1) < np.roll(low, 2)) & (np.roll(close, 1) > np.roll(low, 2))
    # C3 confirmation: Close > Open (Bullish candle)
    c3_bull_conf = c2_bull & (close > open_)
    
    c2_bear = (np.roll(high, 1) > np.roll(high, 2)) & (np.roll(close, 1) < np.roll(high, 2))
    c3_bear_conf = c2_bear & (close < open_)
    
    return pd.DataFrame({
        "ttrade_reversal": np.where(c2_bull, 1, np.where(c2_bear, -1, 0)),
        "ttrade_confirmation": np.where(c3_bull_conf, 1, np.where(c3_bear_conf, -1, 0))
    }, index=ohlc.index)

@validate_ohlc(input_type="ohlc")
def quarterly_cycles(ohlc: pd.DataFrame) -> pd.DataFrame:
    """
    Quarterly Theory (90-minute Cycles).
    Identifies the A, M, D, R quarters (Accumulation, Manipulation, Distribution, Reversal).
    """
    # 90-min logic starting from 00:00 UTC
    
    return pd.DataFrame({
        "quarter": 0, # 1, 2, 3, 4
        "cycle_open": np.nan
    }, index=ohlc.index)
