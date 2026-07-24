import pandas as pd
import numpy as np
from .validation import validate_ohlc

def detect_smt(symbol_a: pd.DataFrame, symbol_b: pd.DataFrame, swings_a: pd.DataFrame, swings_b: pd.DataFrame) -> pd.DataFrame:
    """
    SMT Divergence Detection (Cross-Asset Correlation).
    Primary check: NQ vs ES vs YM.
    
    Bullish SMT: Symbol A makes Higher Low | Symbol B makes Lower Low.
    Bearish SMT: Symbol A makes Lower High | Symbol B makes Higher High.
    """
    # 1. Align timeframes
    # (Assuming both dataframes are already aligned by index)
    
    # 2. Track the last confirmed swing levels for both symbols
    # We look for the MOST RECENT confirmed swings
    sh_a = swings_a["level"].where(swings_a["shl"] == 1).ffill().values
    sl_a = swings_a["level"].where(swings_a["shl"] == -1).ffill().values
    
    sh_b = swings_b["level"].where(swings_b["shl"] == 1).ffill().values
    sl_b = swings_b["level"].where(swings_b["shl"] == -1).ffill().values
    
    # 3. Detection
    # Bullish SMT: One symbol failed to make a lower low
    smt_bull = (symbol_a["low"] > sl_a) & (symbol_b["low"] <= sl_b)
    
    # Bearish SMT: One symbol failed to make a higher high
    smt_bear = (symbol_a["high"] < sh_a) & (symbol_b["high"] >= sh_b)
    
    smt_type = np.zeros(len(symbol_a))
    smt_type[smt_bull] = 1
    smt_type[smt_bear] = -1
    
    return pd.DataFrame({
        "smt": smt_type
    }, index=symbol_a.index)


def detect_triad_smt(
    symbol_a: pd.DataFrame,
    symbol_b: pd.DataFrame,
    symbol_c: pd.DataFrame,
    swings_a: pd.DataFrame,
    swings_b: pd.DataFrame,
    swings_c: pd.DataFrame,
    is_inverse: bool = False,
) -> pd.DataFrame:
    """
    Triad SMT Divergence Matrix (e.g. NQ vs ES vs YM).
    Checks 3-way correlation non-confirmation.

    Bullish Triad SMT: At least one symbol makes Higher Low while others make Lower Low.
    Bearish Triad SMT: At least one symbol makes Lower High while others make Higher High.
    If is_inverse=True, flips the high/low comparison for Dollar Index (DX).
    """
    smt_ab = detect_smt(symbol_a, symbol_b, swings_a, swings_b)
    smt_ac = detect_smt(symbol_a, symbol_c, swings_a, swings_c)
    smt_bc = detect_smt(symbol_b, symbol_c, swings_b, swings_c)

    # Bullish SMT if any pair exhibits bullish non-confirmation
    bull_triad = (smt_ab["smt"] == 1) | (smt_ac["smt"] == 1) | (smt_bc["smt"] == 1)
    bear_triad = (smt_ab["smt"] == -1) | (smt_ac["smt"] == -1) | (smt_bc["smt"] == -1)

    if is_inverse:
        bull_triad, bear_triad = bear_triad, bull_triad

    triad_type = np.zeros(len(symbol_a), dtype=np.int64)
    triad_type[bull_triad] = 1
    triad_type[bear_triad] = -1

    return pd.DataFrame({
        "triad_smt": triad_type,
        "smt_ab": smt_ab["smt"],
        "smt_ac": smt_ac["smt"],
        "smt_bc": smt_bc["smt"],
    }, index=symbol_a.index)
