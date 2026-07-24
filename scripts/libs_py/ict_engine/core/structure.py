import pandas as pd
import numpy as np
from .validation import validate_ohlc

@validate_ohlc(input_type="ohlc")
def detect_swings(ohlc: pd.DataFrame, swing_length: int = 5, delay_confirmation: bool = False) -> pd.DataFrame:
    """
    Swing Highs and Lows Detection (Fractals).

    Parameters
    ----------
    ohlc : pd.DataFrame
        OHLC data.
    swing_length : int
        Number of bars on each side required to confirm a pivot.
    delay_confirmation : bool
        If True, shift the output signals forward by `swing_length` bars so
        they are marked at the exact bar where confirmation occurs in real-time,
        preventing lookahead bias in backtests.
    """
    high = ohlc["high"].values
    low = ohlc["low"].values
    
    rolling_max = ohlc["high"].rolling(window=2 * swing_length + 1, center=True).max()
    rolling_min = ohlc["low"].rolling(window=2 * swing_length + 1, center=True).min()
    
    swing_high = (high == rolling_max)
    swing_low = (low == rolling_min)
    
    shl_type = np.zeros(len(ohlc), dtype=np.int64)
    shl_type[swing_high] = 1
    shl_type[swing_low] = -1
    
    level = np.where(swing_high, high, np.where(swing_low, low, np.nan))

    if delay_confirmation:
        shl_type = pd.Series(shl_type, index=ohlc.index).shift(swing_length).fillna(0).astype(int).values
        level = pd.Series(level, index=ohlc.index).shift(swing_length).values

    return pd.DataFrame({
        "shl": shl_type,
        "level": level
    }, index=ohlc.index)

@validate_ohlc(input_type="ohlc")
def detect_structure_breaks(ohlc: pd.DataFrame, swings: pd.DataFrame) -> pd.DataFrame:
    """
    BOS and MSS Detection.
    BOS: Break of Structure (Continuation signal).
    MSS: Market Structure Shift (Reversal signal).
    """
    close = ohlc["close"].values
    
    # 1. Track the last confirmed swing levels
    last_sh = swings["level"].where(swings["shl"] == 1).ffill().values
    last_sl = swings["level"].where(swings["shl"] == -1).ffill().values
    
    # Track which swing type happened last (1 = SH was last, -1 = SL was last)
    last_swing_type = swings["shl"].replace(0, np.nan).ffill().values
    
    # 2. Basic Breaches
    break_high = (close > last_sh) & (pd.Series(close > last_sh).shift(1).fillna(False) == False)
    break_low = (close < last_sl) & (pd.Series(close < last_sl).shift(1).fillna(False) == False)
    
    structure_type = np.full(len(ohlc), "NONE", dtype=object)
    
    # If last swing was SH (bullish trend context):
    # - Breaking SH again is BOS (continuation)
    # - Breaking SL is MSS (reversal to bearish)
    # If last swing was SL (bearish trend context):
    # - Breaking SL again is BOS (continuation)
    # - Breaking SH is MSS (reversal to bullish)
    
    bos_mask = (break_high & (last_swing_type == 1)) | (break_low & (last_swing_type == -1))
    mss_mask = (break_high & (last_swing_type == -1)) | (break_low & (last_swing_type == 1))
    
    structure_type[bos_mask] = "BOS"
    structure_type[mss_mask] = "MSS"
    
    return pd.DataFrame({
        "break_high": break_high,
        "break_low": break_low,
        "level_h": last_sh,
        "level_l": last_sl,
        "structure_type": structure_type,
    }, index=ohlc.index)

@validate_ohlc(input_type="ohlc")
def detect_cisd(ohlc: pd.DataFrame, swings: pd.DataFrame) -> pd.DataFrame:
    """
    CISD - Change in State of Delivery (Sweep-Open Proxy)
    """
    close = ohlc["close"].values
    open_ = ohlc["open"].values
    high = ohlc["high"].values
    low = ohlc["low"].values
    
    last_sh = swings["level"].where(swings["shl"] == 1).ffill().values
    last_sl = swings["level"].where(swings["shl"] == -1).ffill().values
    
    sweep_high = (high > last_sh) & (close <= last_sh)
    sweep_low = (low < last_sl) & (close >= last_sl)
    
    extreme_open = np.full(len(ohlc), np.nan)
    extreme_open[sweep_high] = open_[sweep_high]
    extreme_open[sweep_low] = open_[sweep_low]
    
    curr_extreme_open = pd.Series(extreme_open).ffill().values
    
    # Store float with NaN so ffill preserves active sweep state
    sw_low_float = np.where(sweep_low, 1.0, np.nan)
    sw_high_float = np.where(sweep_high, 1.0, np.nan)
    has_sweep_low = pd.Series(sw_low_float).ffill().notna().values
    has_sweep_high = pd.Series(sw_high_float).ffill().notna().values
    
    # Bullish Shift (State change)
    bullish_shift = (close > curr_extreme_open) & has_sweep_low
    bearish_shift = (close < curr_extreme_open) & has_sweep_high
    
    cisd_type = np.zeros(len(ohlc), dtype=np.int64)
    cisd_type[bullish_shift] = 1
    cisd_type[bearish_shift] = -1
    
    return pd.DataFrame({
        "cisd": cisd_type,
        "extreme_ref": curr_extreme_open
    }, index=ohlc.index)


@validate_ohlc(input_type="ohlc")
def detect_cisd_authoritative(
    ohlc: pd.DataFrame,
    swings: pd.DataFrame,
    displacement_ratio: float = 0.0,
) -> pd.DataFrame:
    """CISD — Change in State of Delivery (authoritative ICT definition).
    """
    close = ohlc["close"].values
    open_ = ohlc["open"].values
    high = ohlc["high"].values
    low = ohlc["low"].values
    n = len(ohlc)
    idx = ohlc.index

    last_sh = swings["level"].where(swings["shl"] == 1).ffill().values
    last_sl = swings["level"].where(swings["shl"] == -1).ffill().values

    sweep_high = (high > last_sh) & (close <= last_sh)
    sweep_low = (low < last_sl) & (close >= last_sl)

    cisd_type = np.zeros(n, dtype=np.float64)
    cisd_level = np.full(n, np.nan)
    sweep_time_arr = np.full(n, np.datetime64("NaT", "ns"), dtype="datetime64[ns]")

    down_close = close < open_
    up_close = close > open_

    active_sweep_low = np.zeros(n, dtype=bool)
    active_sweep_high = np.zeros(n, dtype=bool)
    active_level = np.full(n, np.nan)

    sweep_low_idx = np.where(sweep_low)[0]
    sweep_high_idx = np.where(sweep_high)[0]

    for si in sweep_low_idx:
        j = si - 1
        while j >= 0 and down_close[j]:
            j -= 1
        series_start = j + 1
        cisd_ref = open_[series_start]
        active_sweep_low[si] = True
        active_level[si] = cisd_ref
        sweep_time_arr[si] = idx[si]

    for si in sweep_high_idx:
        j = si - 1
        while j >= 0 and up_close[j]:
            j -= 1
        series_start = j + 1
        cisd_ref = open_[series_start]
        active_sweep_high[si] = True
        active_level[si] = cisd_ref
        sweep_time_arr[si] = idx[si]

    active_low_ff = pd.Series(active_sweep_low).cummax().astype(bool).values
    active_high_ff = pd.Series(active_sweep_high).cummax().astype(bool).values
    level_ff = pd.Series(active_level).ffill().values

    body_range = np.where(high > low, high - low, 1e-9)
    body_size = np.abs(close - open_)
    body_ratio = body_size / body_range

    bull_cisd = (
        active_low_ff
        & (close > level_ff)
        & (close > open_)
    )
    if displacement_ratio > 0:
        bull_cisd &= (body_ratio >= displacement_ratio)

    bear_cisd = (
        active_high_ff
        & (close < level_ff)
        & (close < open_)
    )
    if displacement_ratio > 0:
        bear_cisd &= (body_ratio >= displacement_ratio)

    cisd_type[bull_cisd] = 1
    cisd_type[bear_cisd] = -1

    return pd.DataFrame({
        "cisd_type": cisd_type,
        "cisd_level": level_ff,
        "sweep_time": sweep_time_arr,
    }, index=ohlc.index)


@validate_ohlc(input_type="ohlc")
def detect_swing_hierarchy(ohlc: pd.DataFrame, swings: pd.DataFrame) -> pd.DataFrame:
    """
    Swing Hierarchy Classification (STH/STL, ITH/ITL, LTH/LTL).

    - STH / STL: Short-Term High / Low (basic 5-bar fractal).
    - ITH: Intermediate-Term High — STH flanked by a lower STH before and after.
    - ITL: Intermediate-Term Low — STL flanked by a higher STL before and after.
    - LTH: Long-Term High — ITH flanked by a lower ITH before and after.
    - LTL: Long-Term Low — ITL flanked by a higher ITL before and after.
    """
    shl = swings["shl"].values
    level = swings["level"].values
    n = len(ohlc)

    hierarchy = np.full(n, "NONE", dtype=object)

    # 1. Identify STH / STL indices
    sth_mask = (shl == 1)
    stl_mask = (shl == -1)
    hierarchy[sth_mask] = "STH"
    hierarchy[stl_mask] = "STL"

    # 2. Identify ITH / ITL
    sth_indices = np.where(sth_mask)[0]
    stl_indices = np.where(stl_mask)[0]

    ith_mask = np.zeros(n, dtype=bool)
    itl_mask = np.zeros(n, dtype=bool)

    if len(sth_indices) >= 3:
        for idx in range(1, len(sth_indices) - 1):
            curr_i = sth_indices[idx]
            prev_i = sth_indices[idx - 1]
            next_i = sth_indices[idx + 1]
            if level[curr_i] > level[prev_i] and level[curr_i] > level[next_i]:
                ith_mask[curr_i] = True
                hierarchy[curr_i] = "ITH"

    if len(stl_indices) >= 3:
        for idx in range(1, len(stl_indices) - 1):
            curr_i = stl_indices[idx]
            prev_i = stl_indices[idx - 1]
            next_i = stl_indices[idx + 1]
            if level[curr_i] < level[prev_i] and level[curr_i] < level[next_i]:
                itl_mask[curr_i] = True
                hierarchy[curr_i] = "ITL"

    # 3. Identify LTH / LTL
    ith_indices = np.where(ith_mask)[0]
    itl_indices = np.where(itl_mask)[0]

    if len(ith_indices) >= 3:
        for idx in range(1, len(ith_indices) - 1):
            curr_i = ith_indices[idx]
            prev_i = ith_indices[idx - 1]
            next_i = ith_indices[idx + 1]
            if level[curr_i] > level[prev_i] and level[curr_i] > level[next_i]:
                hierarchy[curr_i] = "LTH"

    if len(itl_indices) >= 3:
        for idx in range(1, len(itl_indices) - 1):
            curr_i = itl_indices[idx]
            prev_i = itl_indices[idx - 1]
            next_i = itl_indices[idx + 1]
            if level[curr_i] < level[prev_i] and level[curr_i] < level[next_i]:
                hierarchy[curr_i] = "LTL"

    return pd.DataFrame({
        "hierarchy": hierarchy,
        "level": level,
    }, index=ohlc.index)


@validate_ohlc(input_type="ohlc")
def detect_irl_erl(
    ohlc: pd.DataFrame,
    swings_hierarchy: pd.DataFrame,
    fvg_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Internal vs External Range Liquidity Cycle (IRL / ERL).

    - ERL: External Range Liquidity — Major swing points (ITH/ITL, LTH/LTL).
    - IRL: Internal Range Liquidity — Active unmitigated Fair Value Gaps / Order Blocks inside dealing range.
    """
    close = ohlc["close"].values
    n = len(ohlc)

    is_erl = swings_hierarchy["hierarchy"].isin(["ITH", "ITL", "LTH", "LTL"])
    is_irl = fvg_df["fvg_type"] != 0

    erl_level = np.where(is_erl, swings_hierarchy["level"], np.nan)
    last_erl_target = pd.Series(erl_level).ffill().values

    delivery_phase = np.full(n, "NEUTRAL", dtype=object)

    # If price swept ERL, market retraces to IRL. If price tapped IRL, market expands to ERL.
    erl_swept = (ohlc["high"].values > last_erl_target) | (ohlc["low"].values < last_erl_target)
    irl_tapped = is_irl

    has_erl_swept = pd.Series(np.where(erl_swept, 1.0, np.nan)).ffill().notna().values
    has_irl_tapped = pd.Series(np.where(irl_tapped, 1.0, np.nan)).ffill().notna().values

    delivery_phase[has_irl_tapped] = "EXPANSION_TO_ERL"
    delivery_phase[has_erl_swept] = "RETRACEMENT_TO_IRL"

    return pd.DataFrame({
        "delivery_phase": delivery_phase,
        "erl_target": last_erl_target,
        "is_erl": is_erl.astype(int),
        "is_irl": is_irl.astype(int),
    }, index=ohlc.index)


@validate_ohlc(input_type="ohlc")
def detect_hrlr_lrlr(ohlc: pd.DataFrame, swings: pd.DataFrame) -> pd.DataFrame:
    """
    High Resistance vs Low Resistance Liquidity Run (HRLR / LRLR).

    - LRLR: Price run that has cleared opposing swing points (unobstructed path to liquidity target).
    - HRLR: Price run facing multiple opposing unmitigated swing points / obstacles.
    """
    n = len(ohlc)
    close = ohlc["close"].values

    sh_count = (swings["shl"] == 1).cumsum().values
    sl_count = (swings["shl"] == -1).cumsum().values

    run_type = np.full(n, "LRLR", dtype=object)

    # If there are 3+ uncleared swing points in opposing direction, run is HRLR
    opposing_obstacles = np.abs(sh_count - sl_count)
    run_type[opposing_obstacles >= 3] = "HRLR"

    return pd.DataFrame({
        "run_type": run_type,
        "obstacle_count": opposing_obstacles,
    }, index=ohlc.index)
