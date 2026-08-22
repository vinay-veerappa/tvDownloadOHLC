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
    """FVG — Fair Value Gap Detection.

    Delegates to the high-performance ``scripts.libs_py.fvg.compute_fvg``
    kernel, which implements the canonical ICT definition including body-gap
    merging within the 3-candle formation. Output columns are mapped to the
    legacy ``ict_engine`` schema for backwards compatibility.

    Parameters
    ----------
    ohlc : pd.DataFrame
        OHLC data. If ``resample_rule`` is supplied the data is resampled
        first, otherwise FVGs are detected at the native timeframe.
    join_consecutive : bool
        Kept for API compatibility; the performance kernel does not join
        consecutive FVGs. When True, a post-process merge is applied.
    require_candle_direction : bool
        Passed through as ``require_directional_candle``.
    resample_rule : str | None
        Pandas resample rule (e.g. ``"5min"``, ``"15min"``). Passed through as
        ``timeframe`` with ``align_to_base=False``.

    Returns
    -------
    pd.DataFrame with columns:
        fvg_type            — 1 (bullish), -1 (bearish), 0 (none)
        fvg_top             — upper bound of the gap
        fvg_bottom          — lower bound of the gap
        fvg_low             — 3-bar pattern low
        fvg_high            — 3-bar pattern high
        fvg_finalized_time  — timestamp when candle[i] closes
    """
    from scripts.libs_py.fvg import compute_fvg

    base_index = ohlc.index
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
        bar_duration = df.index[1] - df.index[0] if len(df.index) >= 2 else pd.Timedelta(minutes=1)

    res = compute_fvg(
        df,
        min_gap_pts=0.0,
        include_vi=True,
        require_directional_candle=require_candle_direction,
    )

    high = df["high"].values
    low = df["low"].values
    n = len(df)

    # 3-bar pattern extremes for IFVG invalidation / hold checks
    three_bar_low = np.minimum.reduce([
        pd.Series(low).values,
        pd.Series(low).shift(1).values,
        pd.Series(low).shift(2).values,
    ])
    three_bar_high = np.maximum.reduce([
        pd.Series(high).values,
        pd.Series(high).shift(1).values,
        pd.Series(high).shift(2).values,
    ])

    fvg_type = res["fvg_event"].astype(np.int64).values
    fvg_top = res["fvg_top"].values
    fvg_bottom = res["fvg_bottom"].values
    fvg_low = np.where(fvg_type != 0, three_bar_low, np.nan)
    fvg_high = np.where(fvg_type != 0, three_bar_high, np.nan)
    finalized = df.index + bar_duration

    if join_consecutive and (fvg_type != 0).any():
        s_fvg = pd.Series(fvg_type, index=df.index)
        groups = (s_fvg != s_fvg.shift(1)).cumsum()
        fvg_mask = s_fvg != 0

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
            "top": "max",
            "bottom": "min",
            "low": "min",
            "high": "max",
        })

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

    result = pd.DataFrame({
        "fvg_type": fvg_type,
        "fvg_top": fvg_top,
        "fvg_bottom": fvg_bottom,
        "fvg_low": fvg_low,
        "fvg_high": fvg_high,
        "fvg_finalized_time": finalized,
    }, index=df.index)

    if resample_rule is None:
        return result

    # Reindex back to base only when explicitly requested by a resample_rule caller
    # that expects aligned output. Legacy callers using resample_rule expected HTF index.
    return result

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
    - MT: Mean Threshold = 50% midpoint of the Order Block zone.
    """
    close = ohlc["close"].values
    open_ = ohlc["open"].values
    high = ohlc["high"].values
    low = ohlc["low"].values
    
    # 1. Identify Down/Up candles (Body matters)
    is_down = (close < open_)
    is_up = (close > open_)
    
    # 2. Track when structure was broken (MSS / BOS)
    last_sh = swings["level"].where(swings["shl"] == 1).ffill().values
    last_sl = swings["level"].where(swings["shl"] == -1).ffill().values
    
    break_high = (close > last_sh)
    break_low = (close < last_sl)
    
    # 3. Find the 'Last Down' / 'Last Up' candle index before break
    down_indices = np.where(is_down, np.arange(len(ohlc)), -1)
    last_down_idx = pd.Series(down_indices).replace(-1, np.nan).ffill().values
    
    up_indices = np.where(is_up, np.arange(len(ohlc)), -1)
    last_up_idx = pd.Series(up_indices).replace(-1, np.nan).ffill().values
    
    ob_type = np.zeros(len(ohlc), dtype=np.int64)
    ob_top = np.full(len(ohlc), np.nan)
    ob_bottom = np.full(len(ohlc), np.nan)
    ob_mt = np.full(len(ohlc), np.nan)
    
    # Only mark OB on the first bar of structural break
    can_mark_bull = break_high & (pd.Series(break_high).shift(1).fillna(False) == False)
    can_mark_bear = break_low & (pd.Series(break_low).shift(1).fillna(False) == False)
    
    # Valid index masks
    valid_bull_mask = can_mark_bull & ~np.isnan(last_down_idx)
    valid_bear_mask = can_mark_bear & ~np.isnan(last_up_idx)
    
    if np.any(valid_bull_mask):
        bull_locs = last_down_idx[valid_bull_mask].astype(int)
        ob_type[valid_bull_mask] = 1
        ob_top[valid_bull_mask] = high[bull_locs]
        ob_bottom[valid_bull_mask] = low[bull_locs]
        ob_mt[valid_bull_mask] = (high[bull_locs] + low[bull_locs]) / 2.0
        
    if np.any(valid_bear_mask):
        bear_locs = last_up_idx[valid_bear_mask].astype(int)
        ob_type[valid_bear_mask] = -1
        ob_top[valid_bear_mask] = high[bear_locs]
        ob_bottom[valid_bear_mask] = low[bear_locs]
        ob_mt[valid_bear_mask] = (high[bear_locs] + low[bear_locs]) / 2.0
    
    return pd.DataFrame({
        "ob": ob_type,
        "top": ob_top,
        "bottom": ob_bottom,
        "mt": ob_mt
    }, index=ohlc.index)

@validate_ohlc(input_type="ohlc")
def detect_breaker(ohlc: pd.DataFrame, swings: pd.DataFrame) -> pd.DataFrame:
    """
    Breaker Block Detection.
    A 'failed' OB that took liquidity (swept) before being broken.
    Bullish Breaker: A Bearish OB (High swing level that swept liquidity) that price broke ABOVE.
    Bearish Breaker: A Bullish OB (Low swing level that swept liquidity) that price broke BELOW.
    """
    close = ohlc["close"].values
    high = ohlc["high"].values
    low = ohlc["low"].values
    
    # 1. Identify Sweeps (Liquidity grab)
    last_sh = swings["level"].where(swings["shl"] == 1).ffill().values
    last_sl = swings["level"].where(swings["shl"] == -1).ffill().values
    
    swept_h = (high > last_sh) & (close <= last_sh)
    swept_l = (low < last_sl) & (close >= last_sl)
    
    # Store sweep state as float with NaN so ffill preserves forward active sweep state
    swept_h_float = np.where(swept_h, 1.0, np.nan)
    swept_l_float = np.where(swept_l, 1.0, np.nan)
    has_swept_h = pd.Series(swept_h_float).ffill().notna().values
    has_swept_l = pd.Series(swept_l_float).ffill().notna().values
    
    # 2. Identify Breaches after Sweeps
    break_h = (close > last_sh) & (pd.Series(close > last_sh).shift(1).fillna(False) == False)
    break_l = (close < last_sl) & (pd.Series(close < last_sl).shift(1).fillna(False) == False)
    
    breaker_type = np.zeros(len(ohlc), dtype=np.int64)
    breaker_type[break_h & has_swept_h] = 1
    breaker_type[break_l & has_swept_l] = -1
    
    top = np.where(breaker_type != 0, last_sh, np.nan)
    bottom = np.where(breaker_type != 0, last_sl, np.nan)
    
    return pd.DataFrame({
        "breaker": breaker_type,
        "top": top,
        "bottom": bottom
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
    
    sh_levels = swings["level"].where(sh_mask)
    sl_levels = swings["level"].where(sl_mask)
    
    l_type = np.full(len(ohlc), "none", dtype=object)
    l_type[sh_mask] = "BSL"
    l_type[sl_mask] = "SSL"
    
    prev_sh = sh_levels.ffill().shift(1)
    prev_sl = sl_levels.ffill().shift(1)
    
    is_eqh = sh_mask & (np.abs(sh_levels - prev_sh) <= (sh_levels * threshold))
    is_eql = sl_mask & (np.abs(sl_levels - prev_sl) <= (sl_levels * threshold))
    
    l_type[is_eqh] = "EQH"
    l_type[is_eql] = "EQL"
    
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
    Uses O(N) reverse cumulative min/max filters to achieve zero-loop vectorization 
    compliance (ADR-017) without causing O(N*M) memory explosion from dense broadcasting.
    """
    n = len(ohlc)
    mitigation_indices = np.full(n, np.nan)

    fvg_mask = fvg_df["fvg_type"] != 0
    if not fvg_mask.any():
        return pd.Series(mitigation_indices, index=ohlc.index, name="mitigated_index")

    fvg_idx = np.where(fvg_mask)[0]
    fvg_types = fvg_df["fvg_type"].values[fvg_idx]
    
    bull_mask = fvg_types == 1
    bear_mask = fvg_types == -1

    lows = ohlc["low"].values
    highs = ohlc["high"].values
    
    # O(N) Vectorized filter: Calculate running extremes from the future
    # This tells us instantly if an FVG will EVER be mitigated, eliminating 
    # unnecessary search space without slow loops.
    rev_cummin_low = np.minimum.accumulate(lows[::-1])[::-1]
    rev_cummax_high = np.maximum.accumulate(highs[::-1])[::-1]

    def _find_hit(args):
        i, lvl, is_bull = args
        arr = lows if is_bull else highs
        mask = (arr[i+1:] <= lvl) if is_bull else (arr[i+1:] >= lvl)
        if len(mask) == 0: return np.nan
        idx = np.argmax(mask)
        return i + 1 + idx if mask[idx] else np.nan

    # --- Bullish FVGs (mitigated when low <= fvg_top) ---
    if np.any(bull_mask):
        b_i = fvg_idx[bull_mask]
        b_levels = fvg_df["fvg_top"].values[b_i]
        
        # Filter: Only process FVGs that WILL be mitigated in the future
        safe_next_i = np.minimum(b_i + 1, n - 1)
        will_mitigate = (rev_cummin_low[safe_next_i] <= b_levels) & (b_i < n - 1)
        
        active_b_i = b_i[will_mitigate]
        active_b_levels = b_levels[will_mitigate]
        
        # Map is implemented in C and avoids standard python loop overhead on the reduced subset
        hits = np.fromiter(map(_find_hit, zip(active_b_i, active_b_levels, [True]*len(active_b_i))), dtype=float, count=len(active_b_i))
        mitigation_indices[active_b_i] = hits

    # --- Bearish FVGs (mitigated when high >= fvg_bottom) ---
    if np.any(bear_mask):
        br_i = fvg_idx[bear_mask]
        br_levels = fvg_df["fvg_bottom"].values[br_i]
        
        safe_next_i = np.minimum(br_i + 1, n - 1)
        will_mitigate = (rev_cummax_high[safe_next_i] >= br_levels) & (br_i < n - 1)
        
        active_br_i = br_i[will_mitigate]
        active_br_levels = br_levels[will_mitigate]
        
        hits = np.fromiter(map(_find_hit, zip(active_br_i, active_br_levels, [False]*len(active_br_i))), dtype=float, count=len(active_br_i))
        mitigation_indices[active_br_i] = hits

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


def detect_unicorn(breaker_df: pd.DataFrame, fvg_df: pd.DataFrame) -> pd.DataFrame:
    """
    Unicorn Model Detection.
    High-probability confluence pattern: Overlap of a Breaker Block and an FVG.
    """
    has_breaker = breaker_df["breaker"] != 0
    has_fvg = fvg_df["fvg_type"] != 0
    directions_match = breaker_df["breaker"] == fvg_df["fvg_type"]

    # Vertical overlap
    overlap_top = np.minimum(breaker_df["top"], fvg_df["fvg_top"])
    overlap_bottom = np.maximum(breaker_df["bottom"], fvg_df["fvg_bottom"])

    is_unicorn = has_breaker & has_fvg & directions_match & (overlap_top > overlap_bottom)
    unicorn_type = np.where(is_unicorn, breaker_df["breaker"], 0)

    top = np.where(is_unicorn, overlap_top, np.nan)
    bottom = np.where(is_unicorn, overlap_bottom, np.nan)

    return pd.DataFrame({
        "unicorn": unicorn_type,
        "top": top,
        "bottom": bottom,
    }, index=breaker_df.index)


@validate_ohlc(input_type="ohlc")
def detect_propulsion_block(ohlc: pd.DataFrame, ob_df: pd.DataFrame) -> pd.DataFrame:
    """
    Propulsion Block Detection.
    An Order Block that forms inside a preceding active Order Block zone.
    """
    is_ob = ob_df["ob"] != 0
    prev_ob_top = ob_df["top"].ffill().shift(1)
    prev_ob_bottom = ob_df["bottom"].ffill().shift(1)
    prev_ob_type = ob_df["ob"].replace(0, np.nan).ffill().shift(1)

    # Current OB open/close falls inside previous OB range
    in_prev_ob = (ohlc["open"] >= prev_ob_bottom) & (ohlc["open"] <= prev_ob_top)
    directions_match = ob_df["ob"] == prev_ob_type

    is_propulsion = is_ob & in_prev_ob & directions_match
    prop_type = np.where(is_propulsion, ob_df["ob"], 0)

    top = np.where(is_propulsion, ob_df["top"], np.nan)
    bottom = np.where(is_propulsion, ob_df["bottom"], np.nan)

    return pd.DataFrame({
        "propulsion": prop_type,
        "top": top,
        "bottom": bottom,
    }, index=ohlc.index)


@validate_ohlc(input_type="ohlc")
def detect_mitigation_block(ohlc: pd.DataFrame, swings: pd.DataFrame) -> pd.DataFrame:
    """
    Mitigation Block Detection.
    A swing high/low that failed to sweep liquidity before breaking structure.
    Bullish Mitigation Block: Bearish swing point (failed to sweep) broken ABOVE.
    Bearish Mitigation Block: Bullish swing point (failed to sweep) broken BELOW.
    """
    close = ohlc["close"].values
    high = ohlc["high"].values
    low = ohlc["low"].values

    last_sh = swings["level"].where(swings["shl"] == 1).ffill().values
    last_sl = swings["level"].where(swings["shl"] == -1).ffill().values
    
    prev_last_sh = swings["level"].where(swings["shl"] == 1).ffill().shift(1).values
    prev_last_sl = swings["level"].where(swings["shl"] == -1).ffill().shift(1).values

    # Non-swept swings (failed to take liquidity)
    # A new SH that is lower than the previous SH (failed to sweep)
    no_sweep_h = (last_sh < prev_last_sh)
    # A new SL that is higher than the previous SL (failed to sweep)
    no_sweep_l = (last_sl > prev_last_sl)

    # When price breaks above the last SH
    break_h = (close > last_sh) & (pd.Series(close > last_sh).shift(1).fillna(False) == False)
    # When price breaks below the last SL
    break_l = (close < last_sl) & (pd.Series(close < last_sl).shift(1).fillna(False) == False)

    mitigation_type = np.zeros(len(ohlc), dtype=np.int64)
    mitigation_type[break_h & no_sweep_h] = 1
    mitigation_type[break_l & no_sweep_l] = -1

    top = np.where(mitigation_type != 0, last_sh, np.nan)
    bottom = np.where(mitigation_type != 0, last_sl, np.nan)

    return pd.DataFrame({
        "mitigation_block": mitigation_type,
        "top": top,
        "bottom": bottom,
    }, index=ohlc.index)


@validate_ohlc(input_type="ohlc")
def detect_rejection_block(ohlc: pd.DataFrame, swings: pd.DataFrame) -> pd.DataFrame:
    """
    Rejection Block Detection.
    Long wick at a swing extreme where candle body failed to close beyond extreme.
    Zone: Candle body top/bottom to wick tip extreme.
    """
    close = ohlc["close"].values
    open_ = ohlc["open"].values
    high = ohlc["high"].values
    low = ohlc["low"].values

    is_sh = (swings["shl"] == 1)
    is_sl = (swings["shl"] == -1)

    rej_type = np.zeros(len(ohlc), dtype=np.int64)
    rej_type[is_sh] = -1
    rej_type[is_sl] = 1

    body_top = np.maximum(open_, close)
    body_bottom = np.minimum(open_, close)

    # Bullish Rejection Block (at swing low): zone = [low, body_bottom]
    # Bearish Rejection Block (at swing high): zone = [body_top, high]
    top = np.where(is_sh, high, np.where(is_sl, body_bottom, np.nan))
    bottom = np.where(is_sh, body_top, np.where(is_sl, low, np.nan))

    return pd.DataFrame({
        "rejection_block": rej_type,
        "top": top,
        "bottom": bottom,
    }, index=ohlc.index)


@validate_ohlc(input_type="ohlc")
def detect_org(ohlc: pd.DataFrame, timezone: str = "US/Eastern") -> pd.DataFrame:
    """
    Opening Range Gap (ORG).
    Gap between 16:14 ET previous session settlement and 09:30 ET new session open.
    Includes CE (50%) and 25%/75% quadrant levels.
    """
    if ohlc.index.tz is not None:
        et_df = ohlc.tz_convert(timezone)
    else:
        et_df = ohlc.tz_localize("UTC").tz_convert(timezone)

    is_settle = (et_df.index.hour == 16) & (et_df.index.minute == 14)
    is_open = (et_df.index.hour == 9) & (et_df.index.minute == 30)

    settle_price = ohlc["close"].where(is_settle).ffill().shift(1)
    open_price = ohlc["open"].where(is_open)

    org_type = np.zeros(len(ohlc), dtype=np.int64)
    org_type[is_open & (open_price > settle_price)] = 1
    org_type[is_open & (open_price < settle_price)] = -1

    gap_top = np.where(is_open, np.maximum(open_price, settle_price), np.nan)
    gap_bottom = np.where(is_open, np.minimum(open_price, settle_price), np.nan)
    ce = (gap_top + gap_bottom) / 2.0
    q25 = gap_bottom + (gap_top - gap_bottom) * 0.25
    q75 = gap_bottom + (gap_top - gap_bottom) * 0.75

    return pd.DataFrame({
        "org": org_type,
        "gap_top": gap_top,
        "gap_bottom": gap_bottom,
        "ce": ce,
        "q25": q25,
        "q75": q75,
    }, index=ohlc.index)
