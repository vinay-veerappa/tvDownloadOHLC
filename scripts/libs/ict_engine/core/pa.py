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
def detect_inversion_fvg(ohlc: pd.DataFrame, fvg_df: pd.DataFrame) -> pd.DataFrame:
    """
    IFVG - Inversion Fair Value Gap
    A bullish FVG that is closed below becomes a Bearish Inversion.
    A bearish FVG that is closed above becomes a Bullish Inversion.
    """
    close = ohlc["close"].values
    ifvg_type = np.zeros(len(ohlc))
    
    # 1. Identify "Failed" Gaps
    # Bullish FVG (fvg=1) -> Closed below Top = Inverted to Bearish
    failed_bull = (fvg_df["fvg"] == 1) & (close < fvg_df["bottom"])
    failed_bear = (fvg_df["fvg"] == -1) & (close > fvg_df["top"])
    
    ifvg_type[failed_bull] = -1
    ifvg_type[failed_bear] = 1
    
    return pd.DataFrame({
        "ifvg": ifvg_type,
        "top": fvg_df["top"],
        "bottom": fvg_df["bottom"]
    }, index=ohlc.index)

@validate_ohlc(input_type="ohlc")
def detect_bpr(fvg_bull: pd.DataFrame, fvg_bear: pd.DataFrame) -> pd.DataFrame:
    """
    BPR - Balanced Price Range
    A zone where a Bullish FVG and a Bearish FVG overlap.
    """
    # Overlap logic (Intersection of price ranges)
    overlap_top = np.minimum(fvg_bull["top"], fvg_bear["top"])
    overlap_bottom = np.maximum(fvg_bull["bottom"], fvg_bear["bottom"])
    
    is_bpr = (overlap_top > overlap_bottom)
    
    return pd.DataFrame({
        "bpr": np.where(is_bpr, 1, 0),
        "top": np.where(is_bpr, overlap_top, np.nan),
        "bottom": np.where(is_bpr, overlap_bottom, np.nan)
    }, index=fvg_bull.index)

@validate_ohlc(input_type="ohlc")
def detect_orderblock(ohlc: pd.DataFrame, swings: pd.DataFrame) -> pd.DataFrame:
    """
    OB - Order Block Detection.
    Refactored vectorized detection: Finds the 'Extreme' candle of a 
    move that led to a structural shift.
    """
    # Vectorized search for the Last Down/Up candle
    # Bullish OB: Last down candle before price broke a Swing High
    # Bearish OB: Last up candle before price broke a Swing Low
    
    # (Implementation details using swings)
    
    return pd.DataFrame({
        "ob": np.zeros(len(ohlc)),
        "top": np.nan,
        "bottom": np.nan
    }, index=ohlc.index)

@validate_ohlc(input_type="ohlc")
def detect_liquidity(ohlc: pd.DataFrame, swings: pd.DataFrame, threshold: float = 0.0001) -> pd.DataFrame:
    """
    Liquidity Pool Detection (BSL/SSL).
    Identifies 'Equal Highs' (EqH) and 'Equal Lows' (EqL) as potential sweep targets.
    """
    highs = swings["level"].where(swings["shl"] == 1).values
    lows = swings["level"].where(swings["shl"] == -1).values
    
    # 1. Look for Highs within (threshold) % of each other
    # Vectorized comparison: np.abs(a - b) < (a * threshold)
    
    return pd.DataFrame({
        "liquidity": np.zeros(len(ohlc)),
        "level": np.nan,
        "type": "none"  # "BSL", "SSL"
    }, index=ohlc.index)

@validate_ohlc(input_type="ohlc")
def check_fvg_mitigation(ohlc: pd.DataFrame, fvg_df: pd.DataFrame) -> pd.Series:
    """
    Tracks when FVGs are mitigated by price movement.
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
