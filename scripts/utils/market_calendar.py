"""Canonical Market Session Calendar for US Equity Index Futures.

Handles:
- Eastern Time (America/New_York) with Daylight Saving Time (DST) awareness.
- Session pre-market cutoff calculations (default 08:45:00 ET -> UTC).
- Session open (09:30:00 ET) and close (16:00:00 ET / 16:15:00 ET).
- Canonical ISO-8601 UTC string serialization (YYYY-MM-DDTHH:MM:SSZ).
- Logical CME Futures Trading Session date derivation (18:00 ET roll).
"""

from datetime import date, datetime, time, timedelta, timezone
from typing import Tuple, Union
from zoneinfo import ZoneInfo

EASTERN_TZ = ZoneInfo("America/New_York")


def parse_date(date_val: Union[str, date, datetime]) -> date:
    """Parses date from string (YYYY-MM-DD), date, or datetime."""
    if isinstance(date_val, str):
        return date.fromisoformat(date_val.split("T")[0])
    if isinstance(date_val, datetime):
        return date_val.date()
    return date_val


def parse_iso_utc(dt_val: Union[str, datetime]) -> datetime:
    """Normalizes string or datetime into UTC datetime object."""
    if isinstance(dt_val, str):
        cleaned = dt_val.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
    else:
        dt = dt_val
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def to_iso_utc(dt_val: Union[str, datetime]) -> str:
    """Serializes date/datetime into canonical ISO-8601 UTC string (YYYY-MM-DDTHH:MM:SSZ)."""
    dt = parse_iso_utc(dt_val)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def now_iso_utc() -> str:
    """Returns the current UTC timestamp formatted as canonical ISO-8601 string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_session_cutoff_utc(
    session_date: Union[str, date, datetime],
    cutoff_time_et_str: str = "08:45:00"
) -> datetime:
    """Calculates the exact UTC timestamp for a session cutoff in Eastern Time.
    
    Correctly accounts for DST transitions (EDT UTC-4 vs EST UTC-5).
    """
    d = parse_date(session_date)
    parts = [int(p) for p in cutoff_time_et_str.split(":")]
    h = parts[0]
    m = parts[1] if len(parts) > 1 else 0
    s = parts[2] if len(parts) > 2 else 0
    
    t = time(hour=h, minute=m, second=s)
    dt_et = datetime.combine(d, t, tzinfo=EASTERN_TZ)
    return dt_et.astimezone(timezone.utc)


def is_market_weekday(session_date: Union[str, date, datetime]) -> bool:
    """Returns True if the date is a standard trading weekday (Monday-Friday)."""
    d = parse_date(session_date)
    return d.weekday() < 5


def derive_futures_session_date(dt_val: Union[str, datetime]) -> str:
    """Derives the logical CME futures trading session date (YYYY-MM-DD) from timestamp.
    
    CME Globex futures trading sessions roll at 18:00 ET:
    - Fills from 18:00 ET to 23:59 ET belong to the NEXT business day's session.
    - Fills from 00:00 ET to 17:00 ET belong to TODAY's trading session.
    """
    dt_utc = parse_iso_utc(dt_val)
    dt_et = dt_utc.astimezone(EASTERN_TZ)
    if dt_et.hour >= 18:
        next_day = dt_et.date() + timedelta(days=1)
        while next_day.weekday() >= 5:
            next_day += timedelta(days=1)
        return next_day.strftime("%Y-%m-%d")
    else:
        cur_day = dt_et.date()
        while cur_day.weekday() >= 5:
            cur_day += timedelta(days=1)
        return cur_day.strftime("%Y-%m-%d")


def _prev_business_day(d: date) -> date:
    prev = d - timedelta(days=1)
    while prev.weekday() >= 5:
        prev -= timedelta(days=1)
    return prev


def get_futures_session_bounds(session_date: Union[str, date, datetime]) -> Tuple[datetime, datetime]:
    """Returns (start_utc, end_utc) for a LOGICAL CME futures trading session.

    CME Globex sessions roll at 18:00 ET: the logical session for business day D opens
    18:00 ET on the previous business day and closes 17:00 ET on D. Filtering bars by
    ET calendar date (as load_session_bars does) drops the prior-evening leg, which is
    exactly where the overnight profile (P12/Globex) is computed - a sealed manifest
    built from a calendar-date filter silently omits inputs the wargame actually uses.

    DST note: the bounds are computed from ET wall-clocks per day, so a session
    spanning a DST transition yields boundaries converted independently and correctly.
    """
    d = parse_date(session_date)
    open_et = datetime.combine(_prev_business_day(d), time(hour=18, minute=0), tzinfo=EASTERN_TZ)
    close_et = datetime.combine(d, time(hour=17, minute=0), tzinfo=EASTERN_TZ)
    return open_et.astimezone(timezone.utc), close_et.astimezone(timezone.utc)
