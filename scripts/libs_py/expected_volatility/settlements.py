"""Daily settlement construction and volatility-index resolution.

"Settlement" here mirrors Pine's ``close_day``: with default inputs
(``toggle=false``) the indicator uses ``close[1]`` of the 1D chart - i.e. the
previous regular-session close.

Timebase (matches Pine ``request.security(.., '1D', close[1])`` on CME-style
23h symbols): the TradingView daily bar for calendar day D spans
[D-1 17:00 ET, D ~16:00 ET), so its close is the last 1m trade before 16:00
on day D. Evening bars at/after 17:00 ET belong to the NEXT daily bar.
Therefore the value used at the 09:30 session start on day X is the last
intraday close strictly before 16:00 ET on calendar day X-1 (equities and
futures both satisfy this; holidays fall back further).
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

# Pine input toggles (useVOLI / useVIX1D) swap the vol source for the ES family:
#   request.security(useVOLI ? 'NASDAQ:VOLI' : useVIX1D ? 'CBOE:VIX1D' : 'CBOE:VIX', ...)
# Other families have no alternate source in the Pine code.
VOL_SOURCE_ALTERNATES: dict[str, dict[str, str]] = {
    "ES": {
        "VIX": "CBOE:VIX",
        "VOLI": "NASDAQ:VOLI",
        "VIX1D": "CBOE:VIX1D",
    },
}

SESSION_END_HOUR = 16  # bars at/after this ET hour belong to the next daily bar


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


def vol_index_for_ticker(
    ticker: str, source: str = "VIX"
) -> str:
    """Vol index symbol for a chart ticker, honouring Pine's source toggles.

    ``source`` mirrors the Pine inputs ``useVOLI``/``useVIX1D``: "VIX"
    (default), "VOLI" or "VIX1D". Only the ES family has alternates in the
    Pine code; other families ignore it and return their base pairing.
    """
    family = map_ticker_family(ticker)
    alternates = VOL_SOURCE_ALTERNATES.get(family, {})
    if source in alternates:
        return alternates[source]
    if source != "VIX":
        raise ValueError(
            f"vol source {source!r} has no alternate for family {family!r}; "
            f"valid sources: {sorted(alternates) or ['VIX']}"
        )
    return MARKET_VOL_PAIRS[family]


def _et_index(df: pd.DataFrame) -> pd.DatetimeIndex:
    """ET-converted index of a frame with tz-aware or UTC-naive timestamps."""
    idx = df.index
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    return idx.tz_convert(DEFAULT_TZ)


def _per_day_by_cutoff(
    values: pd.Series,
    et_index: pd.DatetimeIndex,
    cutoff_hour: int,
    agg: str,
) -> pd.Series:
    """Aggregate values per ET calendar day, using only bars strictly before
    ``cutoff_hour`` ET. Evening bars (>= cutoff) are dropped entirely - they
    belong to the next TradingView daily bar and must not pollute day D's
    close.
    """
    days = et_index.normalize()
    keep = et_index.hour < cutoff_hour
    if agg == "last":
        grouped = values[keep].groupby(days[keep]).last()
    elif agg == "first":
        grouped = values[keep].groupby(days[keep]).first()
    else:
        raise ValueError(f"unsupported agg: {agg}")
    return grouped.sort_index()


def build_daily_settlements(
    intraday: pd.DataFrame,
    daily: pd.DataFrame | pd.Series | None = None,
    toggle: bool = False,
) -> pd.Series:
    """Per-day value the indicator's boxes are anchored at, indexed by ET day.

    Default (toggle=False): last close strictly before 16:00 ET on the
    PREVIOUS calendar day with qualifying bars (Pine ``close[1]`` on 1D).
    toggle=True: first regular open at/after 09:30 ET of the same day
    (Pine ``session.isfirstbar_regular`` open), matching the ``useTF`` bar
    assigned to the session date.
    """
    et = _et_index(intraday)

    # Daily-frequency frames (VOLI_1d / VIX1D_1d) carry close-stamps at the
    # cutoff hour itself (16:00 ET), so the intraday cutoff would drop every
    # bar. Route them through the daily path.
    et_hours = pd.Index(et.hour)
    if len(et) <= 1 or (et_hours.nunique() <= 2 and et.hour.min() >= SESSION_END_HOUR):
        return _settlements_from_daily(intraday, toggle)

    if daily is not None and len(daily) > 0:
        return _settlements_from_daily(daily, toggle)

    # Intraday fallback: per-day aggregation with the 16:00 ET cutoff.
    values_col = "open" if toggle else "close"
    per_day = _per_day_by_cutoff(
        intraday[values_col].astype(float), et, SESSION_END_HOUR,
        agg=("first" if toggle else "last"),
    )
    if not toggle:
        per_day = per_day.shift(1)  # previous day's close
    return per_day.rename("settlement")


def _settlements_from_daily(
    daily: pd.DataFrame | pd.Series, toggle: bool
) -> pd.Series:
    """Settlements from an explicit daily frame/Series (Pine 1D security).

    Bars are attached to the ET day they represent: daily close-stamps at
    16:00 ET (VOLI_1d, VIX1D_1d) and 17:00 ET (futures 1d captures like
    ES1_1d at 22:00 UTC) both normalize onto their own ET calendar date.
    Default: prior day's close (``close[1]``); toggle: same day's open.
    """
    if isinstance(daily, pd.Series):
        s = daily.copy()
    else:
        col = "open" if toggle and "open" in daily.columns else (
            "close" if "close" in daily.columns else daily.columns[0]
        )
        s = daily[col].copy()
    idx = pd.to_datetime(s.index)
    if idx.tz is not None:
        idx = idx.tz_convert(DEFAULT_TZ).normalize()
    else:
        idx = idx.tz_localize(DEFAULT_TZ).normalize()
    s.index = idx
    s = s.sort_index()
    s = s[~s.index.duplicated(keep="last")]
    if not toggle:
        s = s.shift(1)  # close_day = close[1]
    return s.rename("settlement")


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