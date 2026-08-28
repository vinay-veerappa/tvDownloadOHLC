"""Daily settlement construction and volatility-index resolution.

"Settlement" here mirrors Pine's ``close_day``: with default inputs
(``toggle=false``) the indicator uses ``close[1]`` of the 1D chart - i.e. the
previous regular-session close. With ``toggle=true`` it uses the current
first-bar open instead.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .core import DEFAULT_SESSION, DEFAULT_TZ, is_session_start

# Correlated market -> volatility-index symbol, mirroring the Pine branch table.
MARKET_VOL_PAIRS: dict[str, str] = {
    "ES": "CBOE:VIX",     # also SPY / SPX
    "NQ": "CBOE:VXN",     # also QQQ
    "CL": "CBOE:OVX",
    "RTY": "CBOE:RVX",    # also M2K / IWM
    "VIX": "CBOE:VVIX",
    "GC": "CBOE:GVZ",
    "SI": "CBOE:VXSLV",
    "YM": "CBOE:VXD",     # also DIA
}


def map_ticker_family(ticker: str) -> str:
    """Chart symbol -> market family, replicating the Pine ``str.contains`` order.

    Order matters: e.g. 'RTY' must be checked before 'YM'-style suffixes that
    do not collide, but SI/GC etc. are distinguished by their stem.
    """
    t = ticker.upper()
    if "ES" in t or "SPY" in t or "SPX" in t:
        return "ES"
    if "NQ" in t or "QQQ" in t:
        return "NQ"
    if "CL" in t:
        return "CL"
    if "RTY" in t or "M2K" in t or "IWM" in t:
        return "RTY"
    if t.endswith(":VIX") or t == "VIX":
        return "VIX"
    if "GC" in t:
        return "GC"
    if "SI" in t:
        return "SI"
    if "YM" in t or "DIA" in t:
        return "YM"
    raise ValueError(f"Unrecognized ticker family for {ticker!r}")


def vol_index_for_ticker(ticker: str) -> str:
    return MARKET_VOL_PAIRS[map_ticker_family(ticker)]


def build_daily_settlements(
    intraday: pd.DataFrame,
    daily: pd.DataFrame | pd.Series | None = None,
    toggle: bool = False,
) -> pd.Series:
    """Per-day "settlement" value the indicator anchors boxes at.

    Parameters
    ----------
    intraday : underlying 1m/5m OHLCV frame (tz-aware datetime index).
    daily    : optional 1D frame (or close Series). When supplied, replicates
               Pine's ``request.security(..., '1D', close_day)`` exactly:
               day D uses the prior daily bar's close (``close[1]``) or,
               with ``toggle=True``, the current daily bar's open. When
               omitted, falls back to the intraday frame's own daily close
               (last bar of each day), which equals the 1D close on days the
               session completed.
    toggle   : mirror of the Pine boolean input.

    Returns
    -------
    Series indexed by normalized day, containing the settlement price for
    that day (i.e. what the boxes drawn on that day are anchored at).
    """
    if daily is not None and len(daily) > 0:
        if isinstance(daily, pd.Series):
            base = daily.to_frame("value")
            value_col = "value"
        else:
            base = daily
            if "close" in base.columns:
                value_col = "close"
            else:
                value_col = base.columns[0]
        s = base[value_col].copy()
        idx = pd.to_datetime(s.index)
        if idx.tz is not None:
            idx = idx.tz_convert(DEFAULT_TZ).normalize()
        else:
            idx = idx.tz_localize(DEFAULT_TZ).normalize()
        s.index = idx
        s = s.sort_index()
        s = s[~s.index.duplicated(keep="last")]

        if toggle:
            # Pine: close_day = open (first regular-session bar of the day).
            if isinstance(daily, pd.Series):
                raise TypeError("toggle=True requires an OHLC daily DataFrame")
            open_col = "open" if "open" in base.columns else None
            if open_col is None:
                raise KeyError("toggle=True requires an 'open' column in daily data")
            o = base[open_col].copy()
            oi = pd.to_datetime(o.index)
            if oi.tz is not None:
                oi = oi.tz_convert(DEFAULT_TZ).normalize()
            else:
                oi = oi.tz_localize(DEFAULT_TZ).normalize()
            o.index = oi
            o = o.sort_index()
            o = o[~o.index.duplicated(keep="last")]
            return o.rename("settlement")

        return s.shift(1).rename("settlement")  # close_day = close[1]

    # Intraday-only fallback: last intra-day bar close == daily close.
    et = (intraday.index.tz_convert(DEFAULT_TZ)
          if intraday.index.tz is not None
          else intraday.index.tz_localize(DEFAULT_TZ))
    day = et.normalize()
    if toggle:
        per_day = intraday["open"].groupby(day).first()
    else:
        per_day = intraday["close"].groupby(day).last()
    per_day = per_day.sort_index()
    if not toggle:
        per_day = per_day.shift(1)  # previous day's close
    return per_day.rename("settlement")


def session_settlements(
    intraday: pd.DataFrame,
    daily: pd.DataFrame | pd.Series | None = None,
    session: str = DEFAULT_SESSION,
    tz: str = DEFAULT_TZ,
    toggle: bool = False,
) -> pd.DataFrame:
    """Frame with one row per session start, carrying anchor + session bounds.

    Columns
    -------
    close_day : settlement anchored at this session's first bar (== Pine
                ``close_day`` as seen from the chart timeframe).
    day       : normalized calendar day (in ``tz``) of the session start.
    """
    et_index = intraday.index.tz_convert(DEFAULT_TZ)
    starts = is_session_start(intraday.index, session, tz)
    # ET-normalized day of each session start (tz-aware timestamps).
    session_days = et_index.normalize()[starts]

    out = pd.DataFrame({"day": session_days}, index=intraday.index[starts])
    daily_indexed = build_daily_settlements(intraday, daily, toggle=toggle)
    # daily_indexed is already "what day D should use" (prior close or own
    # open), aligned on day D -> reindex directly at the session's day.
    val = daily_indexed.reindex(session_days).to_numpy()
    out["close_day"] = val
    return out