import pandas as pd
import numpy as np
from .validation import validate_ohlc
from .structure import detect_structure_breaks

@validate_ohlc(input_type="ohlc")
def detect_bias_mmxm_simple(ohlc_1h: pd.DataFrame) -> pd.DataFrame:
    """
    MMXM 'Simple' Bias Filter.
    Rule: 1H 200 EMA.
    - Price > 200 EMA: Bullish Bias
    - Price < 200 EMA: Bearish Bias
    """
    ema_200 = ohlc_1h["close"].ewm(span=200, adjust=False).mean()
    
    bias = np.where(ohlc_1h["close"] > ema_200, 1, -1)
    
    return pd.DataFrame({
        "mmxm_ema_200": ema_200,
        "bias_mmxm": bias
    }, index=ohlc_1h.index)

@validate_ohlc(input_type="ohlc")
def detect_bias_ttrades_mechanical(ohlc_daily: pd.DataFrame, ohlc_intraday: pd.DataFrame) -> pd.DataFrame:
    """
    TTrades Mechanical Bias Rules.
    - Close above PDH: Bullish
    - Close below PDL: Bearish
    - Wick below PDL + Reclaim: Potential Bullish (Requires MSS)
    - Wick above PDH + Reclaim: Potential Bearish (Requires MSS)
    """
    # 1. Map Daily Levels to Intraday
    # We use the previous day's data
    pdh = ohlc_daily["high"].shift(1)
    pdl = ohlc_daily["low"].shift(1)
    
    # Reindex daily levels to intraday timeframe
    intraday_levels = pd.DataFrame(index=ohlc_intraday.index)
    intraday_levels["pdh"] = pdh.reindex(ohlc_intraday.index, method="ffill")
    intraday_levels["pdl"] = pdl.reindex(ohlc_intraday.index, method="ffill")
    
    close = ohlc_intraday["close"].values
    high = ohlc_intraday["high"].values
    low = ohlc_intraday["low"].values
    
    # Mechanical Clauses
    close_above_pdh = close > intraday_levels["pdh"].values
    close_below_pdl = close < intraday_levels["pdl"].values
    
    # Sweep logic (Wick through, but body inside)
    sweep_low = (low < intraday_levels["pdl"].values) & (close > intraday_levels["pdl"].values)
    sweep_high = (high > intraday_levels["pdh"].values) & (close < intraday_levels["pdh"].values)
    
    # We mark 'Potential' on sweeps
    potential_bias = np.zeros(len(ohlc_intraday))
    potential_bias[sweep_low] = 1
    potential_bias[sweep_high] = -1
    
    # Main Bias
    bias = np.zeros(len(ohlc_intraday))
    bias[close_above_pdh] = 1
    bias[close_below_pdl] = -1
    
    return pd.DataFrame({
        "bias_ttrades": bias,
        "potential_reversal": potential_bias,
        "pdh": intraday_levels["pdh"],
        "pdl": intraday_levels["pdl"]
    }, index=ohlc_intraday.index)

def apply_midnight_open_filter(ohlc: pd.DataFrame, bias: pd.Series) -> pd.Series:
    """
    MMXM Midnight Open (MOP) Execution Zone.
    - If Bullish: Buy only below Midnight Open (Discount of the day).
    - If Bearish: Sell only above Midnight Open (Premium of the day).
    """
    # Ensure US/Eastern normalization (Midnight Open is 00:00 ET)
    if ohlc.index.tz is not None:
        et_df = ohlc.tz_convert("US/Eastern")
    else:
        et_df = ohlc.tz_localize("UTC").tz_convert("US/Eastern")

    # Identify Midnight Open (00:00)
    is_midnight = et_df.index.time == pd.Timestamp("00:00").time()
    midnight_opens = et_df["open"].where(is_midnight).ffill()
    
    in_execution_zone = np.zeros(len(et_df), dtype=bool)
    
    # Bullish Rule: Buy below Midnight Open
    bull_mask = (bias.values == 1) & (et_df["close"] < midnight_opens)
    # Bearish Rule: Sell above Midnight Open
    bear_mask = (bias.values == -1) & (et_df["close"] > midnight_opens)
    
    in_execution_zone[bull_mask | bear_mask] = True
    
    return pd.Series(in_execution_zone, index=ohlc.index)
