import pandas as pd
import numpy as np
from .validation import validate_ohlc

@validate_ohlc(input_type="ohlc")
def sd_projections(ohlc: pd.DataFrame, anchor_high: float, anchor_low: float) -> pd.DataFrame:
    """
    Standard Deviation Projections.
    Measures the 'Manipulation Leg' (0-1) and projects SDs (-2, -2.5, -4).
    Commonly used for Exit Targets.
    """
    # 1. Measure Range (Delta)
    delta = np.abs(anchor_high - anchor_low)
    
    # 2. Project Levels (Assuming Bullish Expansion from a Bearish Sweep)
    # The Manipulation was Down (anchor_high -> anchor_low)
    # The Projection is Up
    sd_neg_2 = anchor_high + (delta * 2.0)
    sd_neg_2_5 = anchor_high + (delta * 2.5)
    sd_neg_4 = anchor_high + (delta * 4.0)
    
    # Negative SDs (For targets in opposite direction)
    sd_2 = anchor_low - (delta * 2.0)
    sd_4 = anchor_low - (delta * 4.0)
    
    return pd.DataFrame({
        "sd_2": sd_2,
        "sd_2_5": sd_neg_2_5, # High targets
        "sd_4": sd_neg_4
    }, index=ohlc.index)
