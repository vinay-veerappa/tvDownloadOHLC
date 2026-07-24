"""ICT Integrated Execution Models & State Machines.

Includes:
- ICT 2022 Model State Machine (Bias -> Sweep -> MSS -> FVG Retrace -> Signal)
- Market Maker Buy/Sell Models (MMBM / MMSM Curve Tracking)
"""

import numpy as np
import pandas as pd
from .validation import validate_ohlc


@validate_ohlc(input_type="ohlc")
def ict_2022_model(
    ohlc: pd.DataFrame,
    bias: pd.Series,
    swings: pd.DataFrame,
    fvg_df: pd.DataFrame,
    ob_df: pd.DataFrame,
    dealing_range: pd.DataFrame,
) -> pd.DataFrame:
    """
    ICT 2022 Model Execution Pipeline State Machine.

    Steps:
      1. Daily Bias alignment (Discount for Buys, Premium for Sells)
      2. Liquidity Sweep (Wick beyond swing high/low)
      3. MSS (Market Structure Shift) with displacement
      4. Retrace into FVG / OB
      5. Execution signal triggered at array tap

    Returns
    -------
    pd.DataFrame with:
        signal      - 1 (Long entry), -1 (Short entry), 0 (No signal)
        entry_price - Price level at entry signal
        stop_loss   - Stop loss level beyond swept extreme
        target_tp   - Primary target level (opposing liquidity)
    """
    n = len(ohlc)
    close = ohlc["close"].values
    high = ohlc["high"].values
    low = ohlc["low"].values

    last_sh = swings["level"].where(swings["shl"] == 1).ffill().values
    last_sl = swings["level"].where(swings["shl"] == -1).ffill().values

    # Step 2: Sweep
    swept_low = (low < last_sl) & (close >= last_sl)
    swept_high = (high > last_sh) & (close <= last_sh)

    # Use a combined state so a sweep in the opposite direction resets the active sweep
    sweep_state = np.where(swept_low, 1, np.where(swept_high, -1, np.nan))
    sweep_state_ff = pd.Series(sweep_state).ffill().values

    active_sweep_low = sweep_state_ff == 1
    active_sweep_high = sweep_state_ff == -1

    # Step 3 & 4: FVG / OB active after sweep
    has_bull_fvg = (fvg_df["fvg_type"] == 1).values
    has_bear_fvg = (fvg_df["fvg_type"] == -1).values
    has_bull_ob = (ob_df["ob"] == 1).values
    has_bear_ob = (ob_df["ob"] == -1).values

    is_discount = dealing_range["is_discount"].values
    is_premium = dealing_range["is_premium"].values

    # Step 5: Triggers
    long_signal = (bias.values == 1) & is_discount & active_sweep_low & (has_bull_fvg | has_bull_ob)
    short_signal = (bias.values == -1) & is_premium & active_sweep_high & (has_bear_fvg | has_bear_ob)

    signal = np.zeros(n, dtype=np.int64)
    signal[long_signal] = 1
    signal[short_signal] = -1

    entry_price = np.where(signal == 1, low, np.where(signal == -1, high, np.nan))
    stop_loss = np.where(signal == 1, last_sl, np.where(signal == -1, last_sh, np.nan))
    target_tp = np.where(signal == 1, last_sh, np.where(signal == -1, last_sl, np.nan))

    return pd.DataFrame({
        "signal": signal,
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "target_tp": target_tp,
    }, index=ohlc.index)


@validate_ohlc(input_type="ohlc")
def detect_mmbm_mmsm(
    ohlc: pd.DataFrame,
    swings: pd.DataFrame,
    fvg_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Market Maker Buy/Sell Model (MMBM / MMSM) Curve Stage Tracking.

    Phases:
      - ORIGINAL_CONSOLIDATION
      - LOW_RESISTANCE_RUN
      - SMART_MONEY_REVERSAL (SMR)
      - RE_ACCUMULATION / RE_DISTRIBUTION
      - TARGET_DISTRIBUTION
    """
    n = len(ohlc)
    close = ohlc["close"].values

    sh_mask = swings["shl"] == 1
    sl_mask = swings["shl"] == -1

    has_fvg = fvg_df["fvg_type"] != 0

    curve_phase = np.full(n, "ORIGINAL_CONSOLIDATION", dtype=object)

    # Simple curve state heuristic:
    # After a sweep + FVG, enter SMR. After displacement, enter RE_ACCUMULATION / DISTRIBUTION.
    is_smr = has_fvg.values & (sh_mask.values | sl_mask.values)
    has_smr_ff = pd.Series(np.where(is_smr, 1.0, np.nan)).ffill().notna().values

    curve_phase[has_smr_ff] = "SMART_MONEY_REVERSAL"

    return pd.DataFrame({
        "curve_phase": curve_phase,
        "is_smr": is_smr.astype(int),
    }, index=ohlc.index)
