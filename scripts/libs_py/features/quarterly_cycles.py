"""
Pack Quarterly Theory & Fractal Cycles Feature Module.
======================================================
Implements Pack Quarterly Theory across two core dimensions:
1. Macro 90-Minute Cycles (RTH Session Quarters: Q1, Q2, Q3, Q4)
2. Micro Hourly 15-Minute Quarters (Q1 Anticipation / '05 Box, Q2 Confirmation, Q3 Extension, Q4 Completion)

Adds columns:
    quarter_90m                     — 'Q1' | 'Q2' | 'Q3' | 'Q4' | 'OFF_HOURS'
    is_quarterly_expansion_window   — bool (True during Q1 & Q3 institutional drive)
    is_quarterly_consolidation_window — bool (True during Q2 midday chop)
    hour_quarter                    — int (1, 2, 3, 4)
    is_05_box                       — bool (True during :00–:04 of each hour)
    hour_box05_high                 — High of the first 5 minutes of current hour
    hour_box05_low                  — Low of the first 5 minutes of current hour
    q1_sweep_retreat                — bool (Signals potential hourly Doji / reversal)
"""
from __future__ import annotations

import datetime as dt
import logging
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def compute_quarterly_cycles(df: pd.DataFrame, config=None) -> pd.DataFrame:
    """
    Computes 90-minute session quarters and 15-minute hourly fractal cycle metrics.

    Args:
        df: 1-minute DataFrame with DatetimeIndex, high, low, close.
        config: Optional AppConfig.

    Returns:
        DataFrame with attached Quarterly Theory feature columns.
    """
    out = df.copy()

    # Determine date and time keys
    if hasattr(out.index, "time"):
        times = out.index.time
        minutes = out.index.minute
        hour_keys = out.index.floor("1h")
    else:
        dt_idx = pd.to_datetime(out.index)
        times = dt_idx.dt.time
        minutes = dt_idx.dt.minute
        hour_keys = dt_idx.dt.floor("1h")

    # ── 1. Macro 90-Minute Session Quarters ──
    # Q1: 09:30 - 11:00 (Opening Accumulation / IB Formation)
    # Q2: 11:00 - 12:30 (Midday Consolidation / Lunch Chop)
    # Q3: 12:30 - 14:00 (Afternoon Re-accumulation / Trend Expansion)
    # Q4: 14:00 - 15:30 (Final Distribution / EOD Close)
    q1_mask = (times >= dt.time(9, 30)) & (times < dt.time(11, 0))
    q2_mask = (times >= dt.time(11, 0)) & (times < dt.time(12, 30))
    q3_mask = (times >= dt.time(12, 30)) & (times < dt.time(14, 0))
    q4_mask = (times >= dt.time(14, 0)) & (times <= dt.time(15, 30))

    q_90m = np.select(
        [q1_mask, q2_mask, q3_mask, q4_mask],
        ["Q1", "Q2", "Q3", "Q4"],
        default="OFF_HOURS",
    )
    out["quarter_90m"] = q_90m

    # Expansion vs Consolidation Windows
    # Q1 Expansion starts at 09:45 (post-opening 15m whipsaw) through 11:00
    q1_exp = (times >= dt.time(9, 45)) & (times < dt.time(11, 0))
    q3_exp = (times >= dt.time(12, 30)) & (times < dt.time(14, 0))
    out["is_quarterly_expansion_window"] = q1_exp | q3_exp
    out["is_quarterly_consolidation_window"] = q2_mask

    # ── 2. Micro Hourly 15-Minute Quarters ──
    # Q1: :00 - :14 (Anticipation / initial high/low set)
    # Q2: :15 - :29 (Confirmation)
    # Q3: :30 - :44 (Extension / Expansion)
    # Q4: :45 - :59 (Completion)
    m_arr = np.array(minutes)
    hq = np.select(
        [m_arr < 15, m_arr < 30, m_arr < 45],
        [1, 2, 3],
        default=4,
    )
    out["hour_quarter"] = hq

    # The '05 initial box (:00 - :04)
    out["is_05_box"] = m_arr < 5

    # Compute high/low of the first 5 minutes of each hour
    box05_high = out["high"].where(out["is_05_box"]).groupby(hour_keys).transform("max")
    box05_low = out["low"].where(out["is_05_box"]).groupby(hour_keys).transform("min")
    out["hour_box05_high"] = box05_high.groupby(hour_keys).ffill()
    out["hour_box05_low"] = box05_low.groupby(hour_keys).ffill()

    # ── 3. Hourly Doji Sweep & Retreat Detection (Trigger 1) ──
    # Price breaks outside '05 box during Q1 (:05-:14) but closes back inside
    in_q1_post_box = (m_arr >= 5) & (m_arr < 15)
    broke_up_then_retreat = (
        in_q1_post_box
        & (out["high"] > out["hour_box05_high"])
        & (out["close"] < out["hour_box05_high"])
    )
    broke_dn_then_retreat = (
        in_q1_post_box
        & (out["low"] < out["hour_box05_low"])
        & (out["close"] > out["hour_box05_low"])
    )
    out["q1_sweep_retreat"] = (broke_up_then_retreat | broke_dn_then_retreat).astype(bool)

    logger.debug("Computed Quarterly Theory & Cycles features across %d bars", len(out))
    return out
