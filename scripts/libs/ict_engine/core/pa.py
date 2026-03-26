import pandas as pd
import numpy as np
from .validation import validate_ohlc

@validate_ohlc(input_type="ohlc")
def detect_fvg(ohlc: pd.DataFrame, join_consecutive: bool = False) -> pd.DataFrame:
    """
    FVG - Fair Value Gap Detection
    A gap is bullish if prev_high < next_low and curr_candle is bullish.
    A gap is bearish if prev_low > next_high and curr_candle is bearish.
    """
    low = ohlc["low"].values
    high = ohlc["high"].values
    close = ohlc["close"].values
    open_ = ohlc["open"].values
    
    # Vectorized check for Bullish/Bearish Gaps
    bull_gap = (np.roll(high, 1) < np.roll(low, -1)) & (close > open_)
    bear_gap = (np.roll(low, 1) > np.roll(high, -1)) & (close < open_)
    
    # Avoid first and last candles (where rolls are invalid for gaps)
    bull_gap[0] = bull_gap[-1] = False
    bear_gap[0] = bear_gap[-1] = False
    
    fvg_type = np.where(bull_gap, 1, np.where(bear_gap, -1, np.nan))
    
    # Top/Bottom Bounds
    top = np.where(bull_gap, np.roll(low, -1), np.where(bear_gap, np.roll(low, 1), np.nan))
    bottom = np.where(bull_gap, np.roll(high, 1), np.where(bear_gap, np.roll(high, -1), np.nan))
    
    # Join Consecutive (Merge gaps in a row)
    if join_consecutive:
        for i in range(len(fvg_type) - 1):
            if not np.isnan(fvg_type[i]) and fvg_type[i] == fvg_type[i + 1]:
                top[i + 1] = max(top[i], top[i + 1])
                bottom[i + 1] = min(bottom[i], bottom[i + 1])
                fvg_type[i] = top[i] = bottom[i] = np.nan

    return pd.DataFrame({
        "fvg": fvg_type,
        "top": top,
        "bottom": bottom
    }, index=ohlc.index)

@validate_ohlc(input_type="ohlc")
def check_fvg_mitigation(ohlc: pd.DataFrame, fvg_df: pd.DataFrame) -> pd.Series:
    """
    Tracks when FVGs are mitigated by price movement.
    Bullish FVG is mitigated if price closes below the gap.
    Bearish FVG is mitigated if price closes above the gap.
    """
    mitigation_indices = np.full(len(ohlc), np.nan)
    fvg_indices = np.where(~fvg_df["fvg"].isna())[0]
    
    lows = ohlc["low"].values
    highs = ohlc["high"].values
    
    for i in fvg_indices:
        fvg_type = fvg_df["fvg"].iloc[i]
        limit = fvg_df["top"].iloc[i] if fvg_type == 1 else fvg_df["bottom"].iloc[i]
        
        mask = (lows[i + 2:] <= limit) if fvg_type == 1 else (highs[i + 2:] >= limit)
        if np.any(mask):
            mitigation_indices[i] = np.argmax(mask) + i + 2
            
    return pd.Series(mitigation_indices, index=ohlc.index, name="mitigated_index")
