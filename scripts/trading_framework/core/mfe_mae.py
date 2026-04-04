"""
Vectorized MFE/MAE analysis logic.

Performance Principles:
- Use pandas rolling().max()/.min() shifts for forward-looking windows.
- No Python loops in calculation.
- Memory: use float32 for large datasets.
"""
import logging
import numpy as np
import pandas as pd
from typing import List, Optional
from scripts.trading_framework.config.config_loader import AppConfig

logger = logging.getLogger(__name__)


def compute_mfe_mae(
    df: pd.DataFrame, 
    signal_col: str, 
    horizons: List[int], 
    atr_col: str = "atr_14"
) -> pd.DataFrame:
    """
    Calculate MFE and MAE for all signals in the DataFrame.

    MFE = Maximum Favorable Excursion
    MAE = Maximum Adverse Excursion

    Args:
        df: Enriched DataFrame containing price (high, low, close), signal, and ATR.
            Signal column should have 1 for Long, -1 for Short, 0 otherwise.
        signal_col: Name of the column containing signals.
        horizons: List of forward horizons in bars (e.g. [5, 15, 30, 60, 120]).
        atr_col: Name of the ATR column for normalization.

    Returns:
        DataFrame containing only the signal bars, with additional MFE/MAE 
        columns for each horizon (e.g., 'mfe_15', 'mae_15').
    """
    # 1. Isolate signals
    signals = df[df[signal_col] != 0].copy()
    if signals.empty:
        return signals

    # 2. Extract price components to float32 for speed/memory
    high = df["high"].astype(np.float32)
    low = df["low"].astype(np.float32)
    close = df["close"].astype(np.float32)

    # 3. For each horizon, compute the max/min looking AHEAD
    for h in horizons:
        # High-water mark for the next H bars (including current bar's close as potential start)
        # rolling(h).max().shift(-h) gives the max of the NEXT h bars.
        # e.g., for h=5 at time T, we get max(T, T+1, T+2, T+3, T+4)
        # Use 'min_periods=1' to handle end-of-data tapering.
        fwd_high = high.rolling(window=h, min_periods=1).max().shift(-h+1)
        fwd_low  = low.rolling(window=h, min_periods=1).min().shift(-h+1)
        
        # Pull these back to the signal bars
        sig_fwd_high = fwd_high.reindex(signals.index)
        sig_fwd_low  = fwd_low.reindex(signals.index)
        sig_entry    = signals["close"].astype(np.float32) # Assume entry on signal bar close
        sig_atr      = signals[atr_col].astype(np.float32)

        # 4. Long vs Short Logic
        long_mask = signals[signal_col] == 1
        short_mask = signals[signal_col] == -1

        mfe = pd.Series(np.nan, index=signals.index, dtype=np.float32)
        mae = pd.Series(np.nan, index=signals.index, dtype=np.float32)

        # Longs: MFE is (MaxHigh - Entry) / ATR, MAE is (MinLow - Entry) / ATR
        mfe.loc[long_mask] = ((sig_fwd_high.loc[long_mask] - sig_entry.loc[long_mask]) / sig_atr.loc[long_mask]).astype(np.float32)
        mae.loc[long_mask] = ((sig_fwd_low.loc[long_mask] - sig_entry.loc[long_mask]) / sig_atr.loc[long_mask]).astype(np.float32)

        # Shorts: MFE is (Entry - MinLow) / ATR, MAE is (Entry - MaxHigh) / ATR
        mfe.loc[short_mask] = ((sig_entry.loc[short_mask] - sig_fwd_low.loc[short_mask]) / sig_atr.loc[short_mask]).astype(np.float32)
        mae.loc[short_mask] = ((sig_entry.loc[short_mask] - sig_fwd_high.loc[short_mask]) / sig_atr.loc[short_mask]).astype(np.float32)

        signals[f"mfe_{h}"] = mfe
        signals[f"mae_{h}"] = mae

    # Clean up any potential divide-by-zero or NaNs
    signals = signals.replace([np.inf, -np.inf], np.nan)
    
    logger.debug("Computed MFE/MAE for %d signals across %d horizons", len(signals), len(horizons))
    return signals
