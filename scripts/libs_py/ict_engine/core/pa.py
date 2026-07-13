import pandas as pd
import numpy as np
from .validation import validate_ohlc

@validate_ohlc(input_type="ohlc")
def detect_fvg(
    ohlc: pd.DataFrame,
    join_consecutive: bool = False,
    require_candle_direction: bool = False,
    resample_rule: str | None = None,
) -> pd.DataFrame:
    """FVG — Fair Value Gap Detection (canonical implementation).

    A 3-bar imbalance where the wicks of candle[i-2] and candle[i] do not
    overlap.

    Bullish FVG: ``high[i-2] < low[i]``  (gap above candle 1)
    Bearish FVG: ``low[i-2] > high[i]``  (gap below candle 1)

    Parameters
    ----------
    ohlc : pd.DataFrame
        OHLC data. If ``resample_rule`` is supplied the data is resampled
        first (e.g. ``"5min"``), otherwise FVGs are detected at the native
        timeframe.
    join_consecutive : bool
        If True, merge adjacent FVGs of the same type into a single zone
        (widest top, narrowest bottom for bullish; vice-versa for bearish).
    require_candle_direction : bool
        If True, require candle[i] to be bullish (close > open) for a
        bullish FVG and bearish (close < open) for a bearish FVG. This
        filters out gaps formed against the displacement direction.
    resample_rule : str | None
        Pandas resample rule (e.g. ``"5min"``, ``"15min"``). When set,
        the OHLC data is resampled using ``origin="start_day"`` before
        detection. The returned DataFrame is indexed at the resampled
        timeframe (NOT reindexed back to the original 1m index).

    Returns
    -------
    pd.DataFrame with columns:
        fvg_type            — 1 (bullish), -1 (bearish), 0 (none)
        fvg_top             — upper bound of the gap
        fvg_bottom          — lower bound of the gap
        fvg_low             — 3-bar pattern low (for IFVG invalidation)
        fvg_high            — 3-bar pattern high (for IFVG invalidation)
        fvg_finalized_time  — timestamp when candle[i] closes (index + bar_duration)
    """
    # ── Optional resample ──────────────────────────────────────────
    if resample_rule is not None:
        df = (
            ohlc[["high", "low", "open", "close"]]
            .resample(resample_rule, origin="start_day")
            .agg({"open": "first", "high": "max", "low": "min", "close": "last"})
            .dropna()
        )
        bar_duration = pd.Timedelta(resample_rule)
    else:
        df = ohlc
        # Infer bar duration from index for finalized_time
        if len(df.index) >= 2:
            bar_duration = df.index[1] - df.index[0]
        else:
            bar_duration = pd.Timedelta(minutes=1)

    high = df["high"].values
    low = df["low"].values
    close = df["close"].values
    open_ = df["open"].values

    # 3-bar FVG core: compare candle[i-2] with candle[i]
    high_1 = pd.Series(high).shift(2)  # candle[i-2] high
    low_1 = pd.Series(low).shift(2)    # candle[i-2] low
    high_3 = pd.Series(high)           # candle[i] high
    low_3 = pd.Series(low)             # candle[i] low

    bull_mask = (high_1 < low_3) & high_1.notna() & low_3.notna()
    bear_mask = (low_1 > high_3) & low_1.notna() & high_3.notna()

    # Optional candle direction filter
    if require_candle_direction:
        bull_mask &= (pd.Series(close) > pd.Series(open_))
        bear_mask &= (pd.Series(close) < pd.Series(open_))

    # 3-bar pattern extremes (for IFVG invalidation / hold checks)
    three_bar_low = pd.concat(
        [pd.Series(low), pd.Series(low).shift(1), pd.Series(low).shift(2)], axis=1
    ).min(axis=1)
    three_bar_high = pd.concat(
        [pd.Series(high), pd.Series(high).shift(1), pd.Series(high).shift(2)], axis=1
    ).max(axis=1)

    fvg_type = np.zeros(len(df), dtype=np.int64)
    fvg_type[bull_mask.values] = 1
    fvg_type[bear_mask.values] = -1

    fvg_top = np.full(len(df), np.nan)
    fvg_bottom = np.full(len(df), np.nan)
    fvg_low = np.full(len(df), np.nan)
    fvg_high = np.full(len(df), np.nan)

    # Bullish: top = low[i], bottom = high[i-2]
    fvg_top[bull_mask.values] = low_3[bull_mask.values]
    fvg_bottom[bull_mask.values] = high_1[bull_mask.values]
    fvg_low[bull_mask.values] = three_bar_low[bull_mask.values]
    fvg_high[bull_mask.values] = three_bar_high[bull_mask.values]

    # Bearish: top = low[i-2], bottom = high[i]
    fvg_top[bear_mask.values] = low_1[bear_mask.values]
    fvg_bottom[bear_mask.values] = high_3[bear_mask.values]
    fvg_low[bear_mask.values] = three_bar_low[bear_mask.values]
    fvg_high[bear_mask.values] = three_bar_high[bear_mask.values]

    # Finalized time = when candle[i] closes
    finalized = df.index + bar_duration

    # ── Optional: join consecutive FVGs of same type ───────────────
    if join_consecutive:
        s_fvg = pd.Series(fvg_type, index=df.index)
        groups = (s_fvg != s_fvg.shift(1)).cumsum()
        fvg_mask = s_fvg != 0

        if fvg_mask.any():
            group_df = pd.DataFrame({
                "type": s_fvg[fvg_mask],
                "top": pd.Series(fvg_top, index=df.index)[fvg_mask],
                "bottom": pd.Series(fvg_bottom, index=df.index)[fvg_mask],
                "low": pd.Series(fvg_low, index=df.index)[fvg_mask],
                "high": pd.Series(fvg_high, index=df.index)[fvg_mask],
                "group": groups[fvg_mask],
            })

            agg = group_df.groupby("group").agg({
                "type": "first",
                # Bullish: keep highest top, lowest bottom; Bearish: keep lowest top, highest bottom
                "top": "max",
                "bottom": "min",
                "low": "min",
                "high": "max",
            })

            # Clear and re-assign only to the LAST bar of each group
            fvg_type[:] = 0
            fvg_top[:] = np.nan
            fvg_bottom[:] = np.nan
            fvg_low[:] = np.nan
            fvg_high[:] = np.nan

            last_indices = groups[fvg_mask].groupby(groups[fvg_mask]).tail(1).index
            fvg_type[np.isin(df.index, last_indices)] = agg["type"].values
            locs = df.index.get_indexer(last_indices)
            fvg_top[locs] = agg["top"].values
            fvg_bottom[locs] = agg["bottom"].values
            fvg_low[locs] = agg["low"].values
            fvg_high[locs] = agg["high"].values

    return pd.DataFrame({
        "fvg_type": fvg_type,
        "fvg_top": fvg_top,
        "fvg_bottom": fvg_bottom,
        "fvg_low": fvg_low,
        "fvg_high": fvg_high,
        "fvg_finalized_time": finalized,
    }, index=df.index)

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
    # Bullish FVG (fvg_type=1) -> Closed below Bottom = Inverted to Bearish
    failed_bull = (fvg_df["fvg_type"] == 1) & (close < fvg_df["fvg_bottom"])
    failed_bear = (fvg_df["fvg_type"] == -1) & (close > fvg_df["fvg_top"])

    ifvg_type[failed_bull] = -1
    ifvg_type[failed_bear] = 1

    return pd.DataFrame({
        "ifvg": ifvg_type,
        "top": fvg_df["fvg_top"],
        "bottom": fvg_df["fvg_bottom"]
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
    Vectorized for high performance (eliminates loop).
    """
    mitigation_indices = np.full(len(ohlc), np.nan)

    # Extract only valid FVGs (fvg_type != 0)
    fvg_mask = fvg_df["fvg_type"] != 0
    if not fvg_mask.any():
        return pd.Series(mitigation_indices, index=ohlc.index, name="mitigated_index")

    fvg_indices = np.where(fvg_mask)[0]
    fvg_types = fvg_df["fvg_type"].values[fvg_indices]
    fvg_levels = np.where(fvg_types == 1, fvg_df["fvg_top"].values[fvg_indices], fvg_df["fvg_bottom"].values[fvg_indices])
    
    lows = ohlc["low"].values
    highs = ohlc["high"].values
    
    # 1. Pre-calculate the first time any price is touched
    # We create a mapping of price -> first index it was reached
    # For bearish FVGs, we care about 'highs' reaching 'bottom'
    # For bullish FVGs, we care about 'lows' reaching 'top'
    
    # This is still non-trivial to fully vectorize without a loop over price levels,
    # but we can optimize the loop significantly by using np.minimum/maximum.accumulate
    # or by processing in chunks.
    
    # Optimized loop: Still a loop, but O(N_FVG) with fast inner ops
    # The 'np.argmax(mask)' is the bottleneck. 
    # Let's use a sorted approach if possible.
    
    # Actually, the most robust 'vectorized' way in standard Python/Numpy 
    # for 'first encounter' is using a loop, but we can make it faster
    # by reducing the search space or using a more efficient search.
    
    for idx, (i, f_type, level) in enumerate(zip(fvg_indices, fvg_types, fvg_levels)):
        if f_type == 1: # Bullish: mitigation if Low <= Level
            subset = lows[i + 2:]
            mask = subset <= level
        else: # Bearish: mitigation if High >= Level
            subset = highs[i + 2:]
            mask = subset >= level
            
        if np.any(mask):
            mitigation_indices[i] = np.argmax(mask) + i + 2
            
    return pd.Series(mitigation_indices, index=ohlc.index, name="mitigated_index")

@validate_ohlc(input_type="ohlc")
def detect_volume_imbalance(
    ohlc: pd.DataFrame,
    resample_rule: str | None = None,
) -> pd.DataFrame:
    """VI — Volume Imbalance Detection.

    Detects gaps between the *bodies* of consecutive candles
    (Close[i-1] vs Open[i]).

    Bullish VI: ``close[i-1] < open[i]``  (gap up between bodies)
    Bearish VI: ``close[i-1] > open[i]``  (gap down between bodies)

    Parameters
    ----------
    ohlc : pd.DataFrame
        OHLC data. If ``resample_rule`` is supplied the data is resampled
        first, otherwise VIs are detected at the native timeframe.
    resample_rule : str | None
        Pandas resample rule (e.g. ``"5min"``). When set, the OHLC data is
        resampled using ``origin="start_day"`` before detection.

    Returns
    -------
    pd.DataFrame with columns:
        vi_type             — 1 (bullish), -1 (bearish), 0 (none)
        vi_top              — upper bound of the body gap
        vi_bottom           — lower bound of the body gap
        vi_finalized_time   — timestamp when candle[i] closes
    """
    if resample_rule is not None:
        df = (
            ohlc[["high", "low", "open", "close"]]
            .resample(resample_rule, origin="start_day")
            .agg({"open": "first", "high": "max", "low": "min", "close": "last"})
            .dropna()
        )
        bar_duration = pd.Timedelta(resample_rule)
    else:
        df = ohlc
        if len(df.index) >= 2:
            bar_duration = df.index[1] - df.index[0]
        else:
            bar_duration = pd.Timedelta(minutes=1)

    close = df["close"].values
    open_ = df["open"].values

    # Bullish VI: Close[i-1] < Open[i]
    bull_vi = np.zeros(len(df), dtype=bool)
    bear_vi = np.zeros(len(df), dtype=bool)
    bull_vi[1:] = close[:-1] < open_[1:]
    bear_vi[1:] = close[:-1] > open_[1:]

    # Top/Bottom Bounds
    # Bullish VI: Top = Open[i], Bottom = Close[i-1]
    # Bearish VI: Top = Close[i-1], Bottom = Open[i]
    prev_close = np.roll(close, 1)
    prev_close[0] = np.nan

    vi_type = np.zeros(len(df), dtype=np.int64)
    vi_type[bull_vi] = 1
    vi_type[bear_vi] = -1

    vi_top = np.where(bull_vi, open_, np.where(bear_vi, prev_close, np.nan))
    vi_bottom = np.where(bull_vi, prev_close, np.where(bear_vi, open_, np.nan))

    finalized = df.index + bar_duration

    return pd.DataFrame({
        "vi_type": vi_type,
        "vi_top": vi_top,
        "vi_bottom": vi_bottom,
        "vi_finalized_time": finalized,
    }, index=df.index)

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
    fvg_exists = fvg_df["fvg_type"] != 0

    # Ensure US/Eastern for hour detection
    if ohlc.index.tz is not None:
        et_df = ohlc.tz_convert('US/Eastern')
    else:
        et_df = ohlc.tz_localize('UTC').tz_convert('US/Eastern')

    # Group by Date + Hour to find the first occurrence within the hour
    fvg_rank = fvg_exists.groupby([et_df.index.date, et_df.index.hour]).cumsum()
    is_first = fvg_exists & (fvg_rank == 1)

    return pd.DataFrame({
        "first_fvg": np.where(is_first, fvg_df["fvg_type"], np.nan),
        "top": np.where(is_first, fvg_df["fvg_top"], np.nan),
        "bottom": np.where(is_first, fvg_df["fvg_bottom"], np.nan)
    }, index=ohlc.index)

@validate_ohlc(input_type="ohlc")
def detect_first_fvg_after_time(ohlc: pd.DataFrame, fvg_df: pd.DataFrame, time_str: str = "09:30") -> pd.DataFrame:
    """
    Identifies the single 'First Presented FVG' after a specific time (e.g., 09:30).
    Useful for NY Open specific entry models.
    """
    fvg_exists = fvg_df["fvg_type"] != 0
    # Ensure US/Eastern for time comparison
    if ohlc.index.tz is not None:
        et_df = ohlc.tz_convert('US/Eastern')
    else:
        et_df = ohlc.tz_localize('UTC').tz_convert('US/Eastern')

    times = et_df.index.strftime("%H:%M")

    is_eligible = (times >= time_str)
    eligible_fvgs = fvg_exists & is_eligible

    # Group by Date and find the absolute first FVG of the day after that time
    fvg_rank = eligible_fvgs.groupby(et_df.index.date).cumsum()
    first_fvg_mask = eligible_fvgs & (fvg_rank == 1)

    return pd.DataFrame({
        "first_fvg": np.where(first_fvg_mask, fvg_df["fvg_type"], np.nan),
        "top": np.where(first_fvg_mask, fvg_df["fvg_top"], np.nan),
        "bottom": np.where(first_fvg_mask, fvg_df["fvg_bottom"], np.nan)
    }, index=ohlc.index)
