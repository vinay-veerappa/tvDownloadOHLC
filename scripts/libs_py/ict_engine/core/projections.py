import pandas as pd
import numpy as np
from .validation import validate_ohlc

@validate_ohlc(input_type="ohlc")
def sd_projections(ohlc: pd.DataFrame, anchor_high: float, anchor_low: float, direction: int = 1) -> pd.DataFrame:
    """
    Standard Deviation Projections.
    Measures the 'Manipulation Leg' (0-1) and projects SDs (-2, -2.5, -4).
    Commonly used for Exit Targets.

    Parameters
    ----------
    ohlc : pd.DataFrame
        OHLC data.
    anchor_high : float
        High of the manipulation leg.
    anchor_low : float
        Low of the manipulation leg.
    direction : int
        1 for bullish expansion (projecting up from anchor_high),
        -1 for bearish expansion (projecting down from anchor_low).
    """
    delta = np.abs(anchor_high - anchor_low)
    
    if direction >= 1:
        sd_2 = anchor_high + (delta * 2.0)
        sd_2_5 = anchor_high + (delta * 2.5)
        sd_4 = anchor_high + (delta * 4.0)
    else:
        sd_2 = anchor_low - (delta * 2.0)
        sd_2_5 = anchor_low - (delta * 2.5)
        sd_4 = anchor_low - (delta * 4.0)
    
    return pd.DataFrame({
        "sd_2": sd_2,
        "sd_2_5": sd_2_5,
        "sd_4": sd_4
    }, index=ohlc.index)
