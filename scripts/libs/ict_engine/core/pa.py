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
    Identifies the 'Extreme' candle of a move that led to a structural shift.
    - Bullish OB: Last down candle before price broke a Swing High.
    - Bearish OB: Last up candle before price broke a Swing Low.
    """
    close = ohlc["close"].values
    open_ = ohlc["open"].values
    high = ohlc["high"].values
    low = ohlc["low"].values
    
    # 1. Identify Down/Up candles (Body matters)
    is_down = (close < open_)
    is_up = (close > open_)
    
    # 2. Track when structure was broken (MSS / BOS)
    # We use a simplified check: current close breaks the last swing high/low
    last_sh = swings["level"].where(swings["shl"] == 1).ffill().values
    last_sl = swings["level"].where(swings["shl"] == -1).ffill().values
    
    break_high = (close > last_sh)
    break_low = (close < last_sl)
    
    # 3. Find the 'Last Down' candle before break_high
    # This is slightly complex in pure vector form. 
    # We find the index of the most recent down candle.
    down_indices = np.where(is_down, np.arange(len(ohlc)), 0)
    last_down_idx = pd.Series(down_indices).replace(0, np.nan).ffill().values
    
    up_indices = np.where(is_up, np.arange(len(ohlc)), 0)
    last_up_idx = pd.Series(up_indices).replace(0, np.nan).ffill().values
    
    # Potential OB Locations
    ob_type = np.zeros(len(ohlc))
    ob_top = np.full(len(ohlc), np.nan)
    ob_bottom = np.full(len(ohlc), np.nan)
    
    # Only mark OB on the bar that broke structure
    can_mark_bull = break_high & (pd.Series(break_high).shift(1) == False)
    can_mark_bear = break_low & (pd.Series(break_low).shift(1) == False)
    
    # Retrieve levels of those 'Last candles'
    # Bullish OB levels from the last down candle
    ob_indices_bull = last_down_idx[can_mark_bull].astype(int)
    ob_indices_bear = last_up_idx[can_mark_bear].astype(int)
    
    ob_type[can_mark_bull] = 1
    ob_type[can_mark_bear] = -1
    
    # (Simplified: using High/Low of that candle)
    ob_top[can_mark_bull] = high[ob_indices_bull]
    ob_bottom[can_mark_bull] = low[ob_indices_bull]
    
    ob_top[can_mark_bear] = high[ob_indices_bear]
    ob_bottom[can_mark_bear] = low[ob_indices_bear]
    
    return pd.DataFrame({
        "ob": ob_type,
        "top": ob_top,
        "bottom": ob_bottom
    }, index=ohlc.index)

@validate_ohlc(input_type="ohlc")
def detect_breaker(ohlc: pd.DataFrame, swings: pd.DataFrame) -> pd.DataFrame:
    """
    Breaker Block Detection.
    A 'failed' OB that took liquidity (swept) before being broken.
    Bullish Breaker: A Bearish OB (Last Up Candle) that price broke ABOVE.
    """
    close = ohlc["close"].values
    high = ohlc["high"].values
    low = ohlc["low"].values
    
    # 1. Identify Sweeps (Liquidity grab)
    last_sh = swings["level"].where(swings["shl"] == 1).ffill().values
    last_sl = swings["level"].where(swings["shl"] == -1).ffill().values
    
    swept_h = (high > last_sh) & (close <= last_sh)
    swept_l = (low < last_sl) & (close >= last_sl)
    
    # 2. Identify Breaches after Sweeps
    # (High level logic: A failed OB that was created during a sweep)
    # For now, we'll mark the levels where a previous 'Resistance' is broken
    break_h = (close > last_sh)
    break_l = (close < last_sl)
    
    breaker_type = np.zeros(len(ohlc))
    breaker_type[break_h & pd.Series(swept_h).ffill().values] = 1
    breaker_type[break_l & pd.Series(swept_l).ffill().values] = -1
    
    return pd.DataFrame({
        "breaker": breaker_type,
        "top": last_sh,
        "bottom": last_sl
    }, index=ohlc.index)

@validate_ohlc(input_type="ohlc")
def detect_liquidity(ohlc: pd.DataFrame, swings: pd.DataFrame, threshold: float = 0.0001) -> pd.DataFrame:
    """
    Liquidity Pool Detection (BSL/SSL).
    - BSL (Buyside Liquidity): Swing Highs.
    - SSL (Sellside Liquidity): Swing Lows.
    - EQH (Equal Highs): A cluster of 2+ swing highs within tolerance.
    - EQL (Equal Lows): A cluster of 2+ swing lows within tolerance.
    """
    low = ohlc["low"].values
    high = ohlc["high"].values
    
    # 1. Swings are our primary liquidity points
    sh_mask = (swings["shl"] == 1)
    sl_mask = (swings["shl"] == -1)
    
    # Extract levels for processing
    sh_levels = swings["level"].where(sh_mask)
    sl_levels = swings["level"].where(sl_mask)
    
    # 2. Equal Highs/Lows (EQH/EQL)
    # Vectorized check: Find if current swing is close to a previous swing
    # To keep it vectorized and simple, we check 'N' recent swings.
    # But for now, let's identify just the point itself.
    
    # Identify type
    l_type = np.full(len(ohlc), "none", dtype=object)
    # Default to BSL for highs and SSL for lows
    l_type[sh_mask] = "BSL"
    l_type[sl_mask] = "SSL"
    
    # Vectorized check for "Equal"
    # We compare the current swing high with the previous 3 swing highs
    last_3_sh = sh_levels.dropna().tail(25) # Sample to find EQH
    # For a truly vectorized engine approach, we'll implement EQH based on clusters
    
    # Simple logic: If current swing high is close to previous swing high
    prev_sh = sh_levels.ffill().shift(1)
    prev_sl = sl_levels.ffill().shift(1)
    
    is_eqh = sh_mask & (np.abs(sh_levels - prev_sh) <= (sh_levels * threshold))
    is_eql = sl_mask & (np.abs(sl_levels - prev_sl) <= (sl_levels * threshold))
    
    l_type[is_eqh] = "EQH"
    l_type[is_eql] = "EQL"
    
    # Active Liquidity Flag
    liquidity_active = np.where(sh_mask | sl_mask, 1, np.nan)
    
    return pd.DataFrame({
        "liquidity": liquidity_active,
        "level": swings["level"],
        "type": l_type
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

@validate_ohlc(input_type="ohlc")
def detect_volume_imbalance(ohlc: pd.DataFrame) -> pd.DataFrame:
    """
    VI - Volume Imbalance Detection
    Detects gaps between the bodies of consecutive candles (Close(i-1) and Open(i)).
    """
    close = ohlc["close"].values
    open_ = ohlc["open"].values
    
    # Vectorized check for Bullish/Bearish Gaps between bodies
    # Bullish VI: Close[i-1] < Open[i]
    bull_vi = (open_ > np.roll(close, 1))
    # Bearish VI: Close[i-1] > Open[i]
    bear_vi = (open_ < np.roll(close, 1))
    
    # Avoid first candle
    bull_vi[0] = False
    bear_vi[0] = False
    
    # Top/Bottom Bounds
    # Bullish VI: Top = Open[i], Bottom = Close[i-1]
    # Bearish VI: Top = Close[i-1], Bottom = Open[i]
    top = np.where(bull_vi, open_, np.where(bear_vi, np.roll(close, 1), np.nan))
    bottom = np.where(bull_vi, np.roll(close, 1), np.where(bear_vi, open_, np.nan))
    
    vi_type = np.where(bull_vi, 1, np.where(bear_vi, -1, np.nan))
    
    return pd.DataFrame({
        "vi": vi_type,
        "top": top,
        "bottom": bottom
    }, index=ohlc.index)

@validate_ohlc(input_type="ohlc")
def detect_liquidity_void(ohlc: pd.DataFrame) -> pd.DataFrame:
    """
    Liquidity Void Detection.
    Identifies zones with high displacement (large candle range relative to body)
    that remain unfilled.
    """
    high = ohlc["high"].values
    low = ohlc["low"].values
    
    # Simple displacement check: (High - Low) > 2x Mean of last 20 candles
    candle_size = (high - low)
    avg_size = pd.Series(candle_size).rolling(20).mean().values
    
    is_void = (candle_size > (2.5 * avg_size))
    
    return pd.DataFrame({
        "void": np.where(is_void, 1, 0),
        "top": high,
        "bottom": low
    }, index=ohlc.index)

@validate_ohlc(input_type="ohlc")
def detect_first_fvg_per_hour(ohlc: pd.DataFrame, fvg_df: pd.DataFrame) -> pd.DataFrame:
    """
    Identifies the 'First Presented FVG' for every hour (H:00 window).
    No special offsets - strictly the first FVG after each hourly open.
    """
    fvg_exists = ~fvg_df["fvg"].isna()
    
    # Group by Date + Hour to find the first occurrence within the hour
    fvg_rank = fvg_exists.groupby([ohlc.index.date, ohlc.index.hour]).cumsum()
    is_first = fvg_exists & (fvg_rank == 1)
    
    return pd.DataFrame({
        "first_fvg": np.where(is_first, fvg_df["fvg"], np.nan),
        "top": np.where(is_first, fvg_df["top"], np.nan),
        "bottom": np.where(is_first, fvg_df["bottom"], np.nan)
    }, index=ohlc.index)

@validate_ohlc(input_type="ohlc")
def detect_first_fvg_after_time(ohlc: pd.DataFrame, fvg_df: pd.DataFrame, time_str: str = "09:30") -> pd.DataFrame:
    """
    Identifies the single 'First Presented FVG' after a specific time (e.g., 09:30).
    Useful for NY Open specific entry models.
    """
    fvg_exists = ~fvg_df["fvg"].isna()
    times = ohlc.index.strftime("%H:%M")
    
    is_eligible = (times >= time_str)
    eligible_fvgs = fvg_exists & is_eligible
    
    # Group by Date and find the absolute first FVG of the day after that time
    fvg_rank = eligible_fvgs.groupby(ohlc.index.date).cumsum()
    first_fvg_mask = eligible_fvgs & (fvg_rank == 1)
    
    return pd.DataFrame({
        "first_fvg": np.where(first_fvg_mask, fvg_df["fvg"], np.nan),
        "top": np.where(first_fvg_mask, fvg_df["top"], np.nan),
        "bottom": np.where(first_fvg_mask, fvg_df["bottom"], np.nan)
    }, index=ohlc.index)
