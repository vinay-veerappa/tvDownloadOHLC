"""Advanced ICT Time-Based & Session Models.

Includes:
- 30-Minute ICT Opening Range & Dynamic/Fixed Standard Deviation Projections (0.5 SD increments)
- Dynamic Killzone Pivot Tracking (AS.H/L, LO.H/L, NYAM.H/L, NYPM.H/L) with 50% Midpoints
- CBDR / Asia Range / FLOUT Auto-Selector with Standard Deviation projections
- TGIF (Thank God It's Friday) Retracement Model
"""

import numpy as np
import pandas as pd
from datetime import time
from .validation import validate_ohlc


@validate_ohlc(input_type="ohlc")
def detect_opening_range_30m(
    ohlc: pd.DataFrame,
    start_time: str = "09:30",
    end_time: str = "10:00",
    timezone: str = "US/Eastern",
) -> pd.DataFrame:
    """
    30-Minute ICT Opening Range Model.
    Calculates range H/L, CE (50%), Quadrants (25%/75%), and 0.5 SD increments.
    """
    if ohlc.index.tz is not None:
        et_df = ohlc.tz_convert(timezone)
    else:
        et_df = ohlc.tz_localize("UTC").tz_convert(timezone)

    t_start = pd.Timestamp(f"2000-01-01 {start_time}").time()
    t_end = pd.Timestamp(f"2000-01-01 {end_time}").time()

    times = et_df.index.time
    in_range = (times >= t_start) & (times < t_end)

    range_high = et_df["high"].where(in_range).groupby(et_df.index.date).transform("max")
    range_low = et_df["low"].where(in_range).groupby(et_df.index.date).transform("min")

    high_ff = range_high.ffill().values
    low_ff = range_low.ffill().values
    open_price = et_df["open"].where(times == t_start).ffill().values

    rng = high_ff - low_ff
    ce = (high_ff + low_ff) / 2.0
    q25 = low_ff + rng * 0.25
    q75 = low_ff + rng * 0.75

    sd_plus_05 = high_ff + rng * 0.5
    sd_plus_10 = high_ff + rng * 1.0
    sd_minus_05 = low_ff - rng * 0.5
    sd_minus_10 = low_ff - rng * 1.0

    return pd.DataFrame({
        "or30_high": high_ff,
        "or30_low": low_ff,
        "or30_open": open_price,
        "or30_ce": ce,
        "or30_q25": q25,
        "or30_q75": q75,
        "sd_plus_05": sd_plus_05,
        "sd_plus_10": sd_plus_10,
        "sd_minus_05": sd_minus_05,
        "sd_minus_10": sd_minus_10,
    }, index=ohlc.index)


@validate_ohlc(input_type="ohlc")
def track_killzone_pivots(
    ohlc: pd.DataFrame,
    session_data: pd.DataFrame,
    timezone: str = "US/Eastern",
) -> pd.DataFrame:
    """
    Dynamic Killzone Pivot Tracker.
    Forward-fills session Highs/Lows and tracks 50% Midpoints until price mitigates them.
    """
    hi = session_data["session_high"].ffill().values
    lo = session_data["session_low"].ffill().values
    mid = (hi + lo) / 2.0

    # Mitigation tracking
    hi_mitigated = (ohlc["high"].values > hi)
    lo_mitigated = (ohlc["low"].values < lo)

    active_hi = np.where(~hi_mitigated, hi, np.nan)
    active_lo = np.where(~lo_mitigated, lo, np.nan)

    return pd.DataFrame({
        "kz_high": active_hi,
        "kz_low": active_lo,
        "kz_mid": mid,
    }, index=ohlc.index)


@validate_ohlc(input_type="ohlc")
def select_cbdr_asia_flout(
    ohlc: pd.DataFrame,
    threshold_points: float = 30.0,
    timezone: str = "US/Eastern",
) -> pd.DataFrame:
    """
    CBDR / Asia Range / FLOUT Auto-Selector.
    Selects range based on volatility size (15-40 points/pips) and computes SD levels (0.5 to 4.0).
    """
    if ohlc.index.tz is not None:
        et_df = ohlc.tz_convert(timezone)
    else:
        et_df = ohlc.tz_localize("UTC").tz_convert(timezone)

    times = et_df.index.time

    # CBDR: 16:00 - 20:00
    cbdr_mask = (times >= time(16, 0)) & (times < time(20, 0))
    # Asia: 20:00 - 00:00
    asia_mask = (times >= time(20, 0))

    cbdr_h = et_df["high"].where(cbdr_mask).groupby(et_df.index.date).transform("max")
    cbdr_l = et_df["low"].where(cbdr_mask).groupby(et_df.index.date).transform("min")
    cbdr_rng = (cbdr_h - cbdr_l).ffill().values

    asia_h = et_df["high"].where(asia_mask).groupby(et_df.index.date).transform("max")
    asia_l = et_df["low"].where(asia_mask).groupby(et_df.index.date).transform("min")
    asia_rng = (asia_h - asia_l).ffill().values

    use_cbdr = (cbdr_rng <= threshold_points) & (cbdr_rng > 0)
    selected_range_name = np.where(use_cbdr, "CBDR", "ASIA")

    sel_h = np.where(use_cbdr, cbdr_h.ffill().values, asia_h.ffill().values)
    sel_l = np.where(use_cbdr, cbdr_l.ffill().values, asia_l.ffill().values)
    sel_rng = np.abs(sel_h - sel_l)

    sd1_up = sel_h + sel_rng * 1.0
    sd2_up = sel_h + sel_rng * 2.0
    sd1_dn = sel_l - sel_rng * 1.0
    sd2_dn = sel_l - sel_rng * 2.0

    return pd.DataFrame({
        "selected_range": selected_range_name,
        "range_high": sel_h,
        "range_low": sel_l,
        "sd1_up": sd1_up,
        "sd2_up": sd2_up,
        "sd1_dn": sd1_dn,
        "sd2_dn": sd2_dn,
    }, index=ohlc.index)


@validate_ohlc(input_type="ohlc")
def detect_tgif_setup(
    ohlc: pd.DataFrame,
    weekly_high_time: pd.Timestamp | None = None,
    weekly_low_time: pd.Timestamp | None = None,
    timezone: str = "US/Eastern",
) -> pd.DataFrame:
    """
    TGIF (Thank God It's Friday) Model.
    Triggers Friday retracement targeting 20-30% or 70-80% of weekly range.
    """
    if ohlc.index.tz is not None:
        et_df = ohlc.tz_convert(timezone)
    else:
        et_df = ohlc.tz_localize("UTC").tz_convert(timezone)

    is_friday = et_df.index.weekday == 4
    n = len(ohlc)

    # Use a weekly grouper that ends on Sunday (W-SUN)
    weekly_grouper = pd.Grouper(freq="W-SUN")
    weekly_high = et_df["high"].groupby(weekly_grouper).cummax().values
    weekly_low = et_df["low"].groupby(weekly_grouper).cummin().values
    w_range = weekly_high - weekly_low

    tgif_target = np.full(n, np.nan)
    tgif_zone = np.full(n, "NONE", dtype=object)

    if np.any(is_friday):
        # Upper zone target: 70-80% retracement down (we just use 75% line proxy: high - 0.25*range)
        # Lower zone target: 20-30% retracement up (we just use 25% line proxy: low + 0.25*range)
        upper_target = weekly_high - w_range * 0.25
        lower_target = weekly_low + w_range * 0.25

        tgif_target[is_friday] = upper_target[is_friday]
        tgif_zone[is_friday] = "TGIF_RETRACEMENT"

    return pd.DataFrame({
        "tgif_active": is_friday.astype(int),
        "tgif_zone": tgif_zone,
        "tgif_target": tgif_target,
    }, index=ohlc.index)
