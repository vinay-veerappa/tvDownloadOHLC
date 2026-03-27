import pandas as pd
import numpy as np
from .validation import validate_ohlc

@validate_ohlc(input_type="ohlc")
def calculate_retracements(ohlc: pd.DataFrame, swings: pd.DataFrame) -> pd.DataFrame:
    """
    Vectorized Retracement Engine.
    Tracks the 'Impulse Leg' from the last confirmed swing high/low.
    Calculates Fibonacci levels (0.5 equilibrium, 0.618, 0.705, 0.786).
    """
    high = ohlc["high"].values
    low = ohlc["low"].values
    
    # Track the extreme levels from the last confirmed swings
    last_high = swings["level"].where(swings["shl"] == 1).ffill().values
    last_low = swings["level"].where(swings["shl"] == -1).ffill().values
    
    # Calculate Range and Retracement %
    # If last High > last Low = Bullish Trend (we look for retracement back down)
    current_range = np.abs(last_high - last_low)
    
    # Avoid div by zero
    current_range[current_range == 0] = np.nan
    
    # Retracement % from the High (for Bullish) and from the Low (for Bearish)
    bullish_retracement = (last_high - low) / current_range
    bearish_retracement = (high - last_low) / current_range
    
    # Equilibrium (0.50)
    equilibrium = (last_high + last_low) / 2
    
    # OTE Zones (0.62 - 0.79)
    # Confirming the trend direction from the order of the last swings
    last_sh_idx = np.where(swings["shl"] == 1)[0]
    last_sl_idx = np.where(swings["shl"] == -1)[0]
    
    # (Simplified for now, will enhance with directional logic)
    
    return pd.DataFrame({
        "equilibrium": equilibrium,
        "current_retracement": np.where(last_high > last_low, bullish_retracement, bearish_retracement)
    }, index=ohlc.index)

@validate_ohlc(input_type="ohlc")
def detect_dealing_range(ohlc: pd.DataFrame, swings: pd.DataFrame) -> pd.DataFrame:
    """
    Dealing Range Narrative Detection.
    Identifies the Premium (above 0.5) and Discount (below 0.5) zones.
    - If price is in DISCOUNT -> Look for BUYS.
    - If price is in PREMIUM -> Look for SELLS.
    Used for filtering signals.
    """
    last_sh = swings["level"].where(swings["shl"] == 1).ffill().values
    last_sl = swings["level"].where(swings["shl"] == -1).ffill().values
    
    close = ohlc["close"].values
    equilibrium = (last_sh + last_sl) / 2
    
    # Identify type
    # A bar is in Discount if its Close is below equilibrium
    # (Simplified: using close)
    is_discount = (close < equilibrium)
    is_premium = (close > equilibrium)
    
    return pd.DataFrame({
        "equilibrium": equilibrium,
        "is_discount": is_discount,
        "is_premium": is_premium,
        "range_high": last_sh,
        "range_low": last_sl
    }, index=ohlc.index)
