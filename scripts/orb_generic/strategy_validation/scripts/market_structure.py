"""
market_structure.py — Vectorized market structure detection
============================================================
Swing highs/lows, BOS, CHOCH, Order Blocks, FVGs, VWAP.
All functions operate on numpy arrays for performance.
"""

import numpy as np
import pandas as pd
from typing import Tuple, Optional


# ---------------------------------------------------------------------------
# VWAP
# ---------------------------------------------------------------------------

def compute_vwap(high: np.ndarray, low: np.ndarray, close: np.ndarray,
                 volume: np.ndarray, reset_mask: Optional[np.ndarray] = None) -> np.ndarray:
    """Compute VWAP with optional session resets.

    Args:
        high, low, close, volume: OHLCV arrays
        reset_mask: boolean array, True at bars where VWAP resets (e.g., session open)

    Returns:
        vwap: array of VWAP values
    """
    typical = (high + low + close) / 3.0
    tp_vol = typical * volume

    if reset_mask is None:
        cum_tp_vol = np.cumsum(tp_vol)
        cum_vol = np.cumsum(volume)
    else:
        # Reset cumulative sums at each True in reset_mask
        # Use group-based cumsum
        groups = np.cumsum(reset_mask)
        cum_tp_vol = _grouped_cumsum(tp_vol, groups)
        cum_vol = _grouped_cumsum(volume, groups)

    vwap = np.where(cum_vol > 0, cum_tp_vol / cum_vol, typical)
    return vwap


def compute_vwap_bands(vwap: np.ndarray, high: np.ndarray, low: np.ndarray,
                       close: np.ndarray, volume: np.ndarray,
                       reset_mask: Optional[np.ndarray] = None,
                       n_std: float = 1.0) -> Tuple[np.ndarray, np.ndarray]:
    """Compute VWAP standard deviation bands."""
    typical = (high + low + close) / 3.0
    sq_diff = (typical - vwap) ** 2 * volume

    if reset_mask is None:
        cum_sq = np.cumsum(sq_diff)
        cum_vol = np.cumsum(volume)
    else:
        groups = np.cumsum(reset_mask)
        cum_sq = _grouped_cumsum(sq_diff, groups)
        cum_vol = _grouped_cumsum(volume, groups)

    variance = np.where(cum_vol > 0, cum_sq / cum_vol, 0)
    std = np.sqrt(variance)

    upper = vwap + n_std * std
    lower = vwap - n_std * std
    return upper, lower


def _grouped_cumsum(values: np.ndarray, groups: np.ndarray) -> np.ndarray:
    """Cumulative sum that resets at each new group."""
    result = np.zeros_like(values)
    prev_group = -1
    running = 0.0
    for i in range(len(values)):
        if groups[i] != prev_group:
            running = 0.0
            prev_group = groups[i]
        running += values[i]
        result[i] = running
    return result


# ---------------------------------------------------------------------------
# Swing Highs / Lows
# ---------------------------------------------------------------------------

def detect_swings(high: np.ndarray, low: np.ndarray,
                  lookback: int = 3, lookforward: int = 3) -> Tuple[np.ndarray, np.ndarray]:
    """Detect swing highs and swing lows.

    A swing high at bar i means high[i] is the highest high in the window
    [i-lookback, i+lookforward].

    Returns:
        swing_highs: boolean array, True at swing high bars
        swing_lows: boolean array, True at swing low bars
    """
    n = len(high)
    swing_highs = np.zeros(n, dtype=bool)
    swing_lows = np.zeros(n, dtype=bool)

    for i in range(lookback, n - lookforward):
        window_h = high[i - lookback:i + lookforward + 1]
        window_l = low[i - lookback:i + lookforward + 1]

        if high[i] == np.max(window_h) and np.sum(window_h == high[i]) == 1:
            swing_highs[i] = True
        if low[i] == np.min(window_l) and np.sum(window_l == low[i]) == 1:
            swing_lows[i] = True

    return swing_highs, swing_lows


def get_swing_levels(high: np.ndarray, low: np.ndarray,
                     swing_highs: np.ndarray, swing_lows: np.ndarray
                     ) -> Tuple[np.ndarray, np.ndarray]:
    """Forward-fill the most recent swing high/low values.

    Returns:
        last_swing_high: array of the most recent swing high price at each bar
        last_swing_low: array of the most recent swing low price at each bar
    """
    n = len(high)
    last_sh = np.full(n, np.nan)
    last_sl = np.full(n, np.nan)

    current_sh = np.nan
    current_sl = np.nan

    for i in range(n):
        if swing_highs[i]:
            current_sh = high[i]
        if swing_lows[i]:
            current_sl = low[i]
        last_sh[i] = current_sh
        last_sl[i] = current_sl

    return last_sh, last_sl


# ---------------------------------------------------------------------------
# BOS / CHOCH Detection
# ---------------------------------------------------------------------------

def detect_structure_shifts(high: np.ndarray, low: np.ndarray, close: np.ndarray,
                            swing_highs: np.ndarray, swing_lows: np.ndarray
                            ) -> pd.DataFrame:
    """Detect Break of Structure (BOS) and Change of Character (CHOCH).

    BOS: price breaks a swing level in the SAME direction as the prevailing trend
    CHOCH: price breaks a swing level in the OPPOSITE direction (trend reversal)

    Returns DataFrame with columns:
        bar_idx, type ('bos'/'choch'), direction ('bullish'/'bearish'),
        level_broken, entry_zone_high, entry_zone_low
    """
    n = len(high)
    events = []

    # Track trend: based on whether last significant move was HH/HL or LH/LL
    last_sh = np.nan
    last_sl = np.nan
    prev_sh = np.nan
    prev_sl = np.nan
    trend = 0  # 1=bullish, -1=bearish, 0=undefined

    for i in range(n):
        if swing_highs[i]:
            prev_sh = last_sh
            last_sh = high[i]
            if not np.isnan(prev_sh):
                if last_sh > prev_sh:
                    trend = 1  # higher high → bullish
                elif last_sh < prev_sh:
                    trend = -1  # lower high → bearish

        if swing_lows[i]:
            prev_sl = last_sl
            last_sl = low[i]
            if not np.isnan(prev_sl):
                if last_sl > prev_sl:
                    trend = 1  # higher low → bullish
                elif last_sl < prev_sl:
                    trend = -1  # lower low → bearish

        # Check for breaks
        if not np.isnan(last_sh) and close[i] > last_sh:
            if trend == -1:
                events.append({
                    "bar_idx": i, "type": "choch", "direction": "bullish",
                    "level_broken": last_sh, "price": close[i],
                })
            elif trend == 1:
                events.append({
                    "bar_idx": i, "type": "bos", "direction": "bullish",
                    "level_broken": last_sh, "price": close[i],
                })
            # Update: need new swing high above this level
            last_sh = np.nan

        if not np.isnan(last_sl) and close[i] < last_sl:
            if trend == 1:
                events.append({
                    "bar_idx": i, "type": "choch", "direction": "bearish",
                    "level_broken": last_sl, "price": close[i],
                })
            elif trend == -1:
                events.append({
                    "bar_idx": i, "type": "bos", "direction": "bearish",
                    "level_broken": last_sl, "price": close[i],
                })
            last_sl = np.nan

    return pd.DataFrame(events) if events else pd.DataFrame(
        columns=["bar_idx", "type", "direction", "level_broken", "price"])


# ---------------------------------------------------------------------------
# Order Blocks
# ---------------------------------------------------------------------------

def detect_order_blocks(open_: np.ndarray, high: np.ndarray, low: np.ndarray,
                        close: np.ndarray, displacement_mult: float = 1.5
                        ) -> pd.DataFrame:
    """Detect order blocks: last opposing candle before a displacement move.

    Bullish OB: last bearish candle before a bullish displacement
    Bearish OB: last bullish candle before a bearish displacement

    displacement_mult: the displacement candle body must be >= mult * avg body size

    Returns DataFrame with columns:
        bar_idx, ob_type ('bullish'/'bearish'), ob_high, ob_low, ob_mid,
        displacement_bar, mitigated (initially False)
    """
    n = len(open_)
    body = np.abs(close - open_)

    # Rolling average body size (20 bars)
    avg_body = pd.Series(body).rolling(20, min_periods=5).mean().values

    obs = []

    for i in range(1, n):
        if np.isnan(avg_body[i]):
            continue

        is_displacement = body[i] >= displacement_mult * avg_body[i]
        if not is_displacement:
            continue

        bullish_disp = close[i] > open_[i]
        bearish_disp = close[i] < open_[i]

        if bullish_disp:
            # Look back for last bearish candle
            for j in range(i - 1, max(i - 10, -1), -1):
                if close[j] < open_[j]:  # bearish candle
                    obs.append({
                        "bar_idx": j,
                        "ob_type": "bullish",
                        "ob_high": high[j],
                        "ob_low": low[j],
                        "ob_mid": (high[j] + low[j]) / 2,
                        "displacement_bar": i,
                        "mitigated": False,
                    })
                    break

        elif bearish_disp:
            for j in range(i - 1, max(i - 10, -1), -1):
                if close[j] > open_[j]:  # bullish candle
                    obs.append({
                        "bar_idx": j,
                        "ob_type": "bearish",
                        "ob_high": high[j],
                        "ob_low": low[j],
                        "ob_mid": (high[j] + low[j]) / 2,
                        "displacement_bar": i,
                        "mitigated": False,
                    })
                    break

    return pd.DataFrame(obs) if obs else pd.DataFrame(
        columns=["bar_idx", "ob_type", "ob_high", "ob_low", "ob_mid",
                 "displacement_bar", "mitigated"])


def check_ob_mitigation(obs: pd.DataFrame, high: np.ndarray, low: np.ndarray) -> pd.DataFrame:
    """Mark order blocks as mitigated when price returns through them."""
    obs = obs.copy()
    for idx in obs.index:
        ob = obs.loc[idx]
        start = int(ob["displacement_bar"]) + 1
        if start >= len(high):
            continue

        if ob["ob_type"] == "bullish":
            # Mitigated if price trades through OB low
            if np.any(low[start:] <= ob["ob_low"]):
                mit_bar = start + np.where(low[start:] <= ob["ob_low"])[0][0]
                obs.at[idx, "mitigated"] = True
                obs.at[idx, "mitigation_bar"] = mit_bar
        else:
            if np.any(high[start:] >= ob["ob_high"]):
                mit_bar = start + np.where(high[start:] >= ob["ob_high"])[0][0]
                obs.at[idx, "mitigated"] = True
                obs.at[idx, "mitigation_bar"] = mit_bar

    return obs


# ---------------------------------------------------------------------------
# Fair Value Gaps
# ---------------------------------------------------------------------------

def detect_fvgs(high: np.ndarray, low: np.ndarray,
                min_gap_pct: float = 0.0) -> pd.DataFrame:
    """Detect Fair Value Gaps.

    Bullish FVG: bar[i-2].high < bar[i].low
    Bearish FVG: bar[i-2].low > bar[i].high

    Args:
        min_gap_pct: minimum gap size as % of price to qualify

    Returns DataFrame with: bar_idx, fvg_type, fvg_top, fvg_bottom, fvg_mid, fvg_width, fvg_pct
    """
    n = len(high)
    fvgs = []

    for i in range(2, n):
        price_ref = (high[i] + low[i]) / 2

        # Bullish FVG
        if high[i - 2] < low[i]:
            gap = low[i] - high[i - 2]
            gap_pct = gap / price_ref * 100
            if gap_pct >= min_gap_pct:
                fvgs.append({
                    "bar_idx": i,
                    "fvg_type": "bullish",
                    "fvg_top": low[i],
                    "fvg_bottom": high[i - 2],
                    "fvg_mid": (low[i] + high[i - 2]) / 2,
                    "fvg_width": gap,
                    "fvg_pct": gap_pct,
                })

        # Bearish FVG
        if low[i - 2] > high[i]:
            gap = low[i - 2] - high[i]
            gap_pct = gap / price_ref * 100
            if gap_pct >= min_gap_pct:
                fvgs.append({
                    "bar_idx": i,
                    "fvg_type": "bearish",
                    "fvg_top": low[i - 2],
                    "fvg_bottom": high[i],
                    "fvg_mid": (low[i - 2] + high[i]) / 2,
                    "fvg_width": gap,
                    "fvg_pct": gap_pct,
                })

    return pd.DataFrame(fvgs) if fvgs else pd.DataFrame(
        columns=["bar_idx", "fvg_type", "fvg_top", "fvg_bottom", "fvg_mid",
                 "fvg_width", "fvg_pct"])


def check_fvg_fill(fvgs: pd.DataFrame, high: np.ndarray, low: np.ndarray,
                    lookforward: int = 60) -> pd.DataFrame:
    """Check if FVGs get filled (price returns to 50% of FVG)."""
    fvgs = fvgs.copy()
    fvgs["filled"] = False
    fvgs["fill_bar"] = np.nan
    fvgs["respected"] = False

    for idx in fvgs.index:
        fvg = fvgs.loc[idx]
        start = int(fvg["bar_idx"]) + 1
        end = min(start + lookforward, len(high))
        if start >= len(high):
            continue

        if fvg["fvg_type"] == "bullish":
            # Filled if price comes down to FVG mid
            fill_bars = np.where(low[start:end] <= fvg["fvg_mid"])[0]
            if len(fill_bars) > 0:
                fvgs.at[idx, "filled"] = True
                fvgs.at[idx, "fill_bar"] = start + fill_bars[0]
                # Respected if price bounces after touching
                touch_bar = start + fill_bars[0]
                if touch_bar + 5 < len(high):
                    post = high[touch_bar:touch_bar + 5]
                    fvgs.at[idx, "respected"] = np.max(post) > fvg["fvg_top"]
        else:
            fill_bars = np.where(high[start:end] >= fvg["fvg_mid"])[0]
            if len(fill_bars) > 0:
                fvgs.at[idx, "filled"] = True
                fvgs.at[idx, "fill_bar"] = start + fill_bars[0]
                touch_bar = start + fill_bars[0]
                if touch_bar + 5 < len(high):
                    post = low[touch_bar:touch_bar + 5]
                    fvgs.at[idx, "respected"] = np.min(post) < fvg["fvg_bottom"]

    return fvgs


# ---------------------------------------------------------------------------
# Fibonacci Levels
# ---------------------------------------------------------------------------

def fib_levels(high_val: float, low_val: float,
               levels: tuple = (0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0)
               ) -> dict:
    """Compute Fibonacci retracement levels between high and low.

    Returns dict of {level: price} where 0.0 = low (discount) and 1.0 = high (premium).
    """
    rng = high_val - low_val
    return {lvl: low_val + lvl * rng for lvl in levels}


def fib_zone(high_val: float, low_val: float, zone: str = "discount") -> Tuple[float, float]:
    """Return price bounds for a Fibonacci zone.

    discount: 0.618 - 0.786 of range (measured from low)
    premium: 0.618 - 0.786 of range (measured from high, i.e., 0.214 - 0.382 from low)
    equilibrium: 0.382 - 0.618

    For a LONG bias, you want price in the DISCOUNT zone (low area).
    For a SHORT bias, you want price in the PREMIUM zone (high area).
    """
    rng = high_val - low_val
    if zone == "discount":
        return low_val, low_val + 0.382 * rng  # bottom 38.2%
    elif zone == "premium":
        return low_val + 0.618 * rng, high_val  # top 38.2%
    elif zone == "equilibrium":
        return low_val + 0.382 * rng, low_val + 0.618 * rng
    else:
        raise ValueError(f"Unknown zone: {zone}")


# ---------------------------------------------------------------------------
# Percentage Normalization Helpers
# ---------------------------------------------------------------------------

def pct_of_price(points: float, price: float) -> float:
    """Convert absolute points to percentage of price."""
    return (points / price) * 100 if price > 0 else 0.0


def points_from_pct(pct: float, price: float) -> float:
    """Convert percentage of price to absolute points."""
    return (pct / 100) * price


def compute_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray,
                period: int = 14) -> np.ndarray:
    """Compute Average True Range."""
    prev_close = np.roll(close, 1)
    prev_close[0] = close[0]

    tr = np.maximum(high - low,
                    np.maximum(np.abs(high - prev_close),
                               np.abs(low - prev_close)))

    atr = pd.Series(tr).rolling(period, min_periods=1).mean().values
    return atr


def normalize_to_atr(values: np.ndarray, atr: np.ndarray) -> np.ndarray:
    """Normalize values by ATR (how many ATRs is this move)."""
    return np.where(atr > 0, values / atr, 0)
