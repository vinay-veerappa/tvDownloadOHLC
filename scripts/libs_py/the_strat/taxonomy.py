"""The Strat Candle Taxonomy and Classification Engine.

Implements Rob Smith's "The Strat" candle numbering:
  - Type 1 (Inside Bar): High <= Prev High and Low >= Prev Low
  - Type 2U (Directional Up): High > Prev High and Low >= Prev Low
  - Type 2D (Directional Down): Low < Prev Low and High <= Prev High
  - Type 3 (Outside Bar): High > Prev High and Low < Prev Low

Also provides actionable wick classification (Hammer and Shooter definitions).

WICK RANGE GUARD (decided 2026-09-05, STRATEGY_WORKFLOW.md section 11 item 2):
a bar whose entire range is <= one tick carries no actionable wick. On such a
bar every price position is quantized to the tick grid, so the wick ratio is a
rounding artifact that reads as 0 or 1, and classifying it invents a setup from
noise. C# StratCore.cs has always suppressed them; Python now agrees. This
changes existing the_strat results and lands through a recorded run.
"""

from __future__ import annotations

from enum import IntEnum
from typing import NamedTuple
import numpy as np
import pandas as pd


class StratType(IntEnum):
    """Strat candle classification numeric codes."""
    UNKNOWN = 0
    INSIDE = 1       # 1: Inside bar (equilibrium)
    TWO_UP = 21      # 2U: Directional Up
    TWO_DOWN = 22    # 2D: Directional Down
    OUTSIDE = 3      # 3: Outside bar (broadening)

    @property
    def display_name(self) -> str:
        if self == StratType.INSIDE:
            return "1"
        elif self == StratType.TWO_UP:
            return "2U"
        elif self == StratType.TWO_DOWN:
            return "2D"
        elif self == StratType.OUTSIDE:
            return "3"
        return "?"


class ActionableWickType(IntEnum):
    """Actionable candle wick classifications."""
    NONE = 0
    HAMMER = 1     # Bullish hammer (lower wick >= threshold of full range)
    SHOOTER = -1   # Bearish shooting star (upper wick >= threshold of full range)


class StratBarInfo(NamedTuple):
    """Complete Strat metadata for a single candle."""
    strat_type: StratType
    is_inside: bool
    is_directional_up: bool
    is_directional_down: bool
    is_outside: bool
    wick_type: ActionableWickType
    body_ratio: float
    upper_wick_ratio: float
    lower_wick_ratio: float


def classify_bar(
    high: float,
    low: float,
    prev_high: float,
    prev_low: float,
    open_price: float | None = None,
    close_price: float | None = None,
    wick_threshold: float = 0.65,
    tick_size: float | None = None,
) -> StratBarInfo:
    """Classify a single candle according to The Strat taxonomy.

    Parameters
    ----------
    high, low : float
        Current candle high and low.
    prev_high, prev_low : float
        Previous candle high and low.
    open_price, close_price : float, optional
        Current candle open and close (needed for wick/body calculations).
    wick_threshold : float
        Proportion of total range required to qualify as hammer/shooter (default 0.65).
    tick_size : float, optional
        The instrument's tick size. A bar whose total range is <= this carries
        no actionable wick (section 11 item 2); None keeps the old behavior,
        which is why the parity harness passes it explicitly.

    Returns
    -------
    StratBarInfo
    """
    higher = high > prev_high
    lower = low < prev_low

    if not higher and not lower:
        st = StratType.INSIDE
    elif higher and not lower:
        st = StratType.TWO_UP
    elif lower and not higher:
        st = StratType.TWO_DOWN
    else:
        st = StratType.OUTSIDE

    wick_type = ActionableWickType.NONE
    body_ratio = 0.0
    upper_wick_ratio = 0.0
    lower_wick_ratio = 0.0

    if open_price is not None and close_price is not None:
        total_range = high - low
        # Section 11 item 2: suppress sub-tick bars, mirroring StratCore.cs.
        # The caller supplies the instrument's tick size; when it is not known,
        # callers pass the frame through classify_bars_df, which takes one too.
        if tick_size is not None and total_range <= tick_size:
            return StratBarInfo(
                strat_type=st,
                is_inside=(st == StratType.INSIDE),
                is_directional_up=(st == StratType.TWO_UP),
                is_directional_down=(st == StratType.TWO_DOWN),
                is_outside=(st == StratType.OUTSIDE),
                wick_type=ActionableWickType.NONE,
                body_ratio=0.0,
                upper_wick_ratio=0.0,
                lower_wick_ratio=0.0,
            )
        if total_range > 1e-8:
            body_top = max(open_price, close_price)
            body_bottom = min(open_price, close_price)
            upper_wick = high - body_top
            lower_wick = body_bottom - low
            body_size = body_top - body_bottom

            body_ratio = body_size / total_range
            upper_wick_ratio = upper_wick / total_range
            lower_wick_ratio = lower_wick / total_range

            if lower_wick_ratio >= wick_threshold and close_price >= (low + 0.5 * total_range):
                wick_type = ActionableWickType.HAMMER
            elif upper_wick_ratio >= wick_threshold and close_price <= (low + 0.5 * total_range):
                wick_type = ActionableWickType.SHOOTER

    return StratBarInfo(
        strat_type=st,
        is_inside=(st == StratType.INSIDE),
        is_directional_up=(st == StratType.TWO_UP),
        is_directional_down=(st == StratType.TWO_DOWN),
        is_outside=(st == StratType.OUTSIDE),
        wick_type=wick_type,
        body_ratio=body_ratio,
        upper_wick_ratio=upper_wick_ratio,
        lower_wick_ratio=lower_wick_ratio,
    )


def classify_bars_df(
    df: pd.DataFrame,
    wick_threshold: float = 0.65,
    tick_size: float | None = None,
) -> pd.DataFrame:
    """Vectorized Strat classification for an OHLC DataFrame.

    Expects columns: ['open', 'high', 'low', 'close'] (case-insensitive).
    Adds columns:
      - 'strat_type': int (1, 21, 22, 3)
      - 'strat_label': str ('1', '2U', '2D', '3')
      - 'wick_type': int (1=Hammer, -1=Shooter, 0=None)
      - 'upper_wick_ratio': float
      - 'lower_wick_ratio': float

    `tick_size` suppresses the wick classification on bars whose range is <=
    one tick (section 11 item 2, mirroring C# StratCore.cs). None keeps the
    old behavior.

    Returns
    -------
    pd.DataFrame with new Strat feature columns.
    """
    df_out = df.copy()
    cols = {c.lower(): c for c in df_out.columns}
    h_col = cols["high"]
    l_col = cols["low"]
    o_col = cols.get("open", None)
    c_col = cols.get("close", None)

    high = df_out[h_col].values
    low = df_out[l_col].values

    prev_high = np.roll(high, 1)
    prev_low = np.roll(low, 1)

    higher = high > prev_high
    lower = low < prev_low

    strat_arr = np.full(len(df_out), StratType.UNKNOWN, dtype=int)
    if len(df_out) > 0:
        strat_arr[0] = StratType.UNKNOWN

    inside_mask = (~higher) & (~lower)
    twoup_mask = higher & (~lower)
    twodown_mask = lower & (~higher)
    outside_mask = higher & lower

    strat_arr[inside_mask] = StratType.INSIDE
    strat_arr[twoup_mask] = StratType.TWO_UP
    strat_arr[twodown_mask] = StratType.TWO_DOWN
    strat_arr[outside_mask] = StratType.OUTSIDE

    if len(df_out) > 0:
        strat_arr[0] = StratType.UNKNOWN

    df_out["strat_type"] = strat_arr
    label_map = {
        StratType.UNKNOWN: "",
        StratType.INSIDE: "1",
        StratType.TWO_UP: "2U",
        StratType.TWO_DOWN: "2D",
        StratType.OUTSIDE: "3",
    }
    df_out["strat_label"] = [label_map.get(StratType(v), "") for v in strat_arr]

    if o_col and c_col:
        o = df_out[o_col].values
        c = df_out[c_col].values
        raw_range = high - low
        tot_range = np.maximum(raw_range, 1e-8)
        body_top = np.maximum(o, c)
        body_bottom = np.minimum(o, c)
        upper_wick = high - body_top
        lower_wick = body_bottom - low

        u_ratio = upper_wick / tot_range
        l_ratio = lower_wick / tot_range

        df_out["upper_wick_ratio"] = u_ratio
        df_out["lower_wick_ratio"] = l_ratio

        wick_arr = np.zeros(len(df_out), dtype=int)
        hammer_mask = (l_ratio >= wick_threshold) & (c >= (low + 0.5 * tot_range))
        shooter_mask = (u_ratio >= wick_threshold) & (c <= (low + 0.5 * tot_range))

        wick_arr[hammer_mask] = ActionableWickType.HAMMER
        wick_arr[shooter_mask] = ActionableWickType.SHOOTER

        # Section 11 item 2: a sub-tick bar carries no actionable wick. The
        # ratio on such a bar is a quantization artifact (0 or 1), exactly the
        # case StratCore.cs suppresses with `range <= tickSize`.
        if tick_size is not None:
            wick_arr[raw_range <= tick_size] = ActionableWickType.NONE

        df_out["wick_type"] = wick_arr

    return df_out
