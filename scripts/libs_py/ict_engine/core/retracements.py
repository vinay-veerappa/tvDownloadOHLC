import pandas as pd
import numpy as np
from .validation import validate_ohlc

@validate_ohlc(input_type="ohlc")
def calculate_retracements(ohlc: pd.DataFrame, swings: pd.DataFrame) -> pd.DataFrame:
    """
    Vectorized Retracement Engine.
    Tracks the 'Impulse Leg' from the last confirmed swing high/low.
    Calculates Fibonacci levels (0.5 equilibrium, 0.618, 0.705, 0.786 OTE).
    """
    high = ohlc["high"].values
    low = ohlc["low"].values
    
    last_high = swings["level"].where(swings["shl"] == 1).ffill().values
    last_low = swings["level"].where(swings["shl"] == -1).ffill().values
    
    # Track timestamps/indices of last SH vs last SL to determine trend direction
    sh_indices = np.where(swings["shl"] == 1, np.arange(len(ohlc)), -1)
    sl_indices = np.where(swings["shl"] == -1, np.arange(len(ohlc)), -1)
    
    last_sh_idx = pd.Series(sh_indices).replace(-1, np.nan).ffill().values
    last_sl_idx = pd.Series(sl_indices).replace(-1, np.nan).ffill().values
    
    # Bullish leg if SH occurred after SL
    is_bullish_leg = np.nan_to_num(last_sh_idx) >= np.nan_to_num(last_sl_idx)
    
    current_range = np.abs(last_high - last_low)
    current_range[current_range == 0] = np.nan
    
    bullish_retracement = (last_high - low) / current_range
    bearish_retracement = (high - last_low) / current_range
    
    equilibrium = (last_high + last_low) / 2.0
    
    # OTE (Optimal Trade Entry) Fib levels
    ote_618 = np.where(is_bullish_leg, last_high - (current_range * 0.618), last_low + (current_range * 0.618))
    ote_705 = np.where(is_bullish_leg, last_high - (current_range * 0.705), last_low + (current_range * 0.705))
    ote_786 = np.where(is_bullish_leg, last_high - (current_range * 0.786), last_low + (current_range * 0.786))
    
    current_retr = np.where(is_bullish_leg, bullish_retracement, bearish_retracement)
    
    return pd.DataFrame({
        "equilibrium": equilibrium,
        "current_retracement": current_retr,
        "ote_618": ote_618,
        "ote_705": ote_705,
        "ote_786": ote_786,
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
