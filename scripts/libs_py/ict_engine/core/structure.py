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

import numba
from typing import Tuple


@numba.njit(fastmath=True)
def _compute_cisd_neo_jit(
    open_arr: np.ndarray,
    high_arr: np.ndarray,
    low_arr: np.ndarray,
    close_arr: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Fast JIT kernel for Neo/Canonical CISD detection.
    Evaluates multi-bar pullbacks, structure expansion breaks, and body-close level breaches.
    """
    n = len(open_arr)
    cisd_event = np.zeros(n, dtype=np.int8)
    cisd_state = np.zeros(n, dtype=np.int8)
    active_bull_lvl = np.full(n, np.nan, dtype=np.float64)
    active_bear_lvl = np.full(n, np.nan, dtype=np.float64)
    struct_top = np.zeros(n, dtype=np.float64)
    struct_bot = np.zeros(n, dtype=np.float64)

    if n < 2:
        return cisd_event, cisd_state, active_bull_lvl, active_bear_lvl, struct_top, struct_bot

    curr_struct_top = high_arr[0]
    curr_struct_bot = low_arr[0]

    is_bullish_pb = False
    is_bearish_pb = False

    potential_top_price = np.nan
    potential_bot_price = np.nan
    bullish_break_idx = -1
    bearish_break_idx = -1

    armed_bull_level = np.nan
    armed_bear_level = np.nan
    armed_bull_completed = True
    armed_bear_completed = True

    current_regime = 0

    for t in range(1, n):
        o = open_arr[t]
        h = high_arr[t]
        l = low_arr[t]
        c = close_arr[t]

        o_prev = open_arr[t - 1]
        c_prev = close_arr[t - 1]

        # 1. Pullback detection on previous bar
        bearish_pb_detected = c_prev > o_prev  # Prior candle was green
        bullish_pb_detected = c_prev < o_prev  # Prior candle was red

        # 2. Initiate pullback state
        if bearish_pb_detected and not is_bearish_pb:
            is_bearish_pb = True
            potential_top_price = o_prev
            bullish_break_idx = t - 1

        if bullish_pb_detected and not is_bullish_pb:
            is_bullish_pb = True
            potential_bot_price = o_prev
            bearish_break_idx = t - 1

        # 3. Dynamically update potential anchor open during multi-bar pullbacks
        if is_bullish_pb:
            if o < potential_bot_price or np.isnan(potential_bot_price):
                potential_bot_price = o
                bearish_break_idx = t
            elif (c < o) and (o > potential_bot_price):
                potential_bot_price = o
                bearish_break_idx = t

        if is_bearish_pb:
            if o > potential_top_price or np.isnan(potential_top_price):
                potential_top_price = o
                bullish_break_idx = t
            elif (c > o) and (o < potential_top_price):
                potential_top_price = o
                bullish_break_idx = t

        # 4. Structure Expansion & Level Arming
        # Bearish Structure Break (New Low) -> Arms +CISD Resistance Level
        if l < curr_struct_bot:
            curr_struct_bot = l
            if is_bearish_pb and (t != bullish_break_idx):
                h1 = high_arr[bullish_break_idx]
                h2 = high_arr[bullish_break_idx + 1] if (bullish_break_idx + 1 < t) else h1
                curr_struct_top = max(h1, h2)
                is_bearish_pb = False
                armed_bull_level = potential_top_price
                armed_bull_completed = False
            elif (c_prev > o_prev) and (c < o):
                curr_struct_top = high_arr[t - 1]
                is_bearish_pb = False
                armed_bull_level = potential_top_price
                armed_bull_completed = False

        # Bullish Structure Break (New High) -> Arms -CISD Support Level
        if h > curr_struct_top:
            curr_struct_top = h
            if is_bullish_pb and (t != bearish_break_idx):
                l1 = low_arr[bearish_break_idx]
                l2 = low_arr[bearish_break_idx + 1] if (bearish_break_idx + 1 < t) else l1
                curr_struct_bot = min(l1, l2)
                is_bullish_pb = False
                armed_bear_level = potential_bot_price
                armed_bear_completed = False
            elif (c_prev < o_prev) and (c > o):
                curr_struct_bot = low_arr[t - 1]
                is_bullish_pb = False
                armed_bear_level = potential_bot_price
                armed_bear_completed = False

        # 5. Check Breach of Armed Anchor Levels (The CISD State Flip)
        # Bearish CISD: Body-close below armed support floor (-CISD)
        if not armed_bear_completed and not np.isnan(armed_bear_level):
            if c < armed_bear_level:
                armed_bear_completed = True
                cisd_event[t] = -1
                current_regime = -1

        # Bullish CISD: Body-close above armed resistance ceiling (+CISD)
        if not armed_bull_completed and not np.isnan(armed_bull_level):
            if c > armed_bull_level:
                armed_bull_completed = True
                cisd_event[t] = 1
                current_regime = 1

        cisd_state[t] = current_regime
        active_bull_lvl[t] = armed_bull_level if not armed_bull_completed else np.nan
        active_bear_lvl[t] = armed_bear_level if not armed_bear_completed else np.nan
        struct_top[t] = curr_struct_top
        struct_bot[t] = curr_struct_bot

    return cisd_event, cisd_state, active_bull_lvl, active_bear_lvl, struct_top, struct_bot


@validate_ohlc(input_type="ohlc")
def detect_cisd_neo(ohlc: pd.DataFrame) -> pd.DataFrame:
    """
    Authoritative CISD (Change in State of Delivery) Engine - Neo/Institutional Standard.

    Detects true Changes in State of Delivery (CISD) by:
    1. Tracking multi-bar pullback delivery runs (recording the deepest open price).
    2. Arming anchor levels ONLY upon structural impulse expansions (new swing highs/lows).
    3. Confirming the state flip when price body-closes through the armed anchor level.

    Parameters
    ----------
    ohlc : pd.DataFrame
        DataFrame with columns ['open', 'high', 'low', 'close'] and DatetimeIndex.

    Returns
    -------
    pd.DataFrame with columns:
        - 'cisd_event'        : int8 (1 = Bullish CISD trigger on this bar, -1 = Bearish CISD trigger, 0 = None)
        - 'cisd_state'        : int8 (1 = Bullish delivery regime, -1 = Bearish delivery regime, 0 = Neutral)
        - 'active_bull_level' : float (Active +CISD resistance ceiling level)
        - 'active_bear_level' : float (Active -CISD support floor level)
        - 'structure_top'     : float (Running structural swing high)
        - 'structure_bottom'  : float (Running structural swing low)
    """
    open_arr = np.ascontiguousarray(ohlc["open"].values, dtype=np.float64)
    high_arr = np.ascontiguousarray(ohlc["high"].values, dtype=np.float64)
    low_arr = np.ascontiguousarray(ohlc["low"].values, dtype=np.float64)
    close_arr = np.ascontiguousarray(ohlc["close"].values, dtype=np.float64)

    events, states, bull_lvls, bear_lvls, s_tops, s_bots = _compute_cisd_neo_jit(
        open_arr, high_arr, low_arr, close_arr
    )

    return pd.DataFrame(
        {
            "cisd_event": events,
            "cisd_state": states,
            "active_bull_level": bull_lvls,
            "active_bear_level": bear_lvls,
            "structure_top": s_tops,
            "structure_bottom": s_bots,
        },
        index=ohlc.index,
    )


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
