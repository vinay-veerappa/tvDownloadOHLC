"""Canonical Market Session Calendar for US Equity Index Futures.

Handles:
- Eastern Time (America/New_York) with Daylight Saving Time (DST) awareness.
- Session pre-market cutoff calculations (default 08:45:00 ET -> UTC).
- Session open (09:30:00 ET) and close (16:00:00 ET / 16:15:00 ET).
- Canonical ISO-8601 UTC string serialization (YYYY-MM-DDTHH:MM:SSZ).
"""

from datetime import date, datetime, time, timezone
from typing import Union
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
