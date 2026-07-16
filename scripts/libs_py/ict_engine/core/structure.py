import pandas as pd
import numpy as np
from .validation import validate_ohlc

@validate_ohlc(input_type="ohlc")
def detect_swings(ohlc: pd.DataFrame, swing_length: int = 5) -> pd.DataFrame:
    """
    Swing Highs and Lows Detection (Fractals)
    """
    high = ohlc["high"].values
    low = ohlc["low"].values
    
    rolling_max = ohlc["high"].rolling(window=2 * swing_length + 1, center=True).max()
    rolling_min = ohlc["low"].rolling(window=2 * swing_length + 1, center=True).min()
    
    swing_high = (high == rolling_max)
    swing_low = (low == rolling_min)
    
    shl_type = np.zeros(len(ohlc))
    shl_type[swing_high] = 1
    shl_type[swing_low] = -1
    
    level = np.where(swing_high, high, np.where(swing_low, low, np.nan))
    
    return pd.DataFrame({
        "shl": shl_type,
        "level": level
    }, index=ohlc.index)

@validate_ohlc(input_type="ohlc")
def detect_structure_breaks(ohlc: pd.DataFrame, swings: pd.DataFrame) -> pd.DataFrame:
    """
    BOS and MSS Detection.
    BOS: Continuation break of structure.
    MSS: Market structure shift (Trend reversal).
    """
    close = ohlc["close"].values
    
    # 1. Track the last confirmed swing levels
    last_sh = swings["level"].where(swings["shl"] == 1).ffill().values
    last_sl = swings["level"].where(swings["shl"] == -1).ffill().values
    
    # 2. Basic Breaches
    break_high = (close > last_sh)
    break_low = (close < last_sl)
    
    # Classification logic (BOS vs MSS)
    # This requires tracking the sequence of Highs/Lows
    
    return pd.DataFrame({
        "break_high": break_high,
        "break_low": break_low,
        "level_h": last_sh,
        "level_l": last_sl
    }, index=ohlc.index)

@validate_ohlc(input_type="ohlc")
def detect_cisd(ohlc: pd.DataFrame, swings: pd.DataFrame) -> pd.DataFrame:
    """
    CISD - Change in State of Delivery
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
    
    # Bullish Shift (State change)
    bullish_shift = (close > curr_extreme_open) & (pd.Series(sweep_low).ffill().values)
    bearish_shift = (close < curr_extreme_open) & (pd.Series(sweep_high).ffill().values)
    
    cisd_type = np.zeros(len(ohlc))
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

    After a liquidity sweep, identify the **consecutive same-close-direction
    delivery series** that made the extreme.  The series starts at the
    **first candle** after the last opposite-close candle.  Mark the
    **opening price of the FIRST candle** in that series.  CISD fires when
    a subsequent candle **body-closes** beyond that opening.

    This is more precise than ``detect_cisd`` (sweep-open proxy) because the
    reference level is the start of the delivery run, not the sweep bar —
    giving price more room before the signal triggers and reducing false
    positives from ~31% to ~14% (per ictkillzone.com tracking).

    Parameters
    ----------
    ohlc : pd.DataFrame
        OHLC data with columns open / high / low / close.
    swings : pd.DataFrame
        Swing points from ``detect_swings`` (columns: shl, level).
    displacement_ratio : float
        Minimum body-to-range ratio on the confirming candle
        (e.g. 0.65 for 65% filter).  0 = no filter.

    Returns
    -------
    pd.DataFrame with columns:
        cisd_type      — 1 (bullish shift), -1 (bearish shift), 0 (none)
        cisd_level     — the delivery-series opening price (reference)
        sweep_time     — timestamp of the triggering sweep
    """
    close = ohlc["close"].values
    open_ = ohlc["open"].values
    high = ohlc["high"].values
    low = ohlc["low"].values
    n = len(ohlc)
    idx = ohlc.index

    last_sh = swings["level"].where(swings["shl"] == 1).ffill().values
    last_sl = swings["level"].where(swings["shl"] == -1).ffill().values

    # ── 1. Sweep detection (same as proxy) ──────────────────────────
    sweep_high = (high > last_sh) & (close <= last_sh)   # wick above SH, close back below
    sweep_low = (low < last_sl) & (close >= last_sl)      # wick below SL, close back above

    # ── 2. Walk backward to find delivery-series opening ───────────
    # For a sweep_low (bullish setup): the delivery series is the
    #   consecutive down-close (close < open) candles leading into the low.
    #   Walk backward from the sweep bar; skip consecutive down-close
    #   candles; the series OPEN = open of the FIRST candle in the run
    #   (i.e. the one with the highest open among the down-close run).
    # For a sweep_high (bearish setup): mirror — consecutive up-close
    #   candles leading into the high; series OPEN = open of the FIRST
    #   candle in the run (lowest open among the up-close run).

    cisd_type = np.zeros(n, dtype=np.float64)
    cisd_level = np.full(n, np.nan)
    sweep_time_arr = np.array([np.datetime64("NaT")] * n, dtype="datetime64[ns]")

    down_close = close < open_   # bearish candles
    up_close = close > open_     # bullish candles

    # Track active sweep state for forward CISD detection
    active_sweep_low = np.zeros(n, dtype=bool)
    active_sweep_high = np.zeros(n, dtype=bool)
    active_level = np.full(n, np.nan)

    sweep_low_idx = np.where(sweep_low)[0]
    sweep_high_idx = np.where(sweep_high)[0]

    for si in sweep_low_idx:
        # Walk backward from sweep bar to find consecutive down-close run
        j = si - 1
        while j >= 0 and down_close[j]:
            j -= 1
        # j now points to the last up-close candle (or -1); series starts at j+1
        series_start = j + 1
        if series_start < si:
            cisd_ref = open_[series_start]   # open of FIRST candle in down-close run
            active_sweep_low[si] = True
            active_level[si] = cisd_ref
            sweep_time_arr[si] = idx[si]

    for si in sweep_high_idx:
        # Walk backward from sweep bar to find consecutive up-close run
        j = si - 1
        while j >= 0 and up_close[j]:
            j -= 1
        series_start = j + 1
        if series_start < si:
            cisd_ref = open_[series_start]
            active_sweep_high[si] = True
            active_level[si] = cisd_ref
            sweep_time_arr[si] = idx[si]

    # ── 3. Forward-fill active sweep state ──────────────────────────
    active_low_ff = pd.Series(active_sweep_low).cummax().astype(bool).values
    active_high_ff = pd.Series(active_sweep_high).cummax().astype(bool).values
    level_ff = pd.Series(active_level).ffill().values

    # ── 4. CISD trigger: body close beyond delivery-series opening ─
    body_range = np.where(high > low, high - low, 1e-9)
    body_size = np.abs(close - open_)
    body_ratio = body_size / body_range

    # Bullish CISD: close > cisd_level AND we had a sweep_low
    bull_cisd = (
        active_low_ff
        & (close > level_ff)
        & (close > open_)                      # body close up
        & (pd.Series(sweep_low).cummax().astype(bool).values)
    )
    if displacement_ratio > 0:
        bull_cisd &= (body_ratio >= displacement_ratio)

    # Bearish CISD: close < cisd_level AND we had a sweep_high
    bear_cisd = (
        active_high_ff
        & (close < level_ff)
        & (close < open_)                      # body close down
        & (pd.Series(sweep_high).cummax().astype(bool).values)
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
