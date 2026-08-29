"""Canonical Market Session Calendar for US Equity Index Futures.

Handles:
- Eastern Time (America/New_York) with Daylight Saving Time (DST) awareness.
- Session pre-market cutoff calculations (default 08:45:00 ET -> UTC).
- Session open (09:30:00 ET) and close (16:00:00 ET / 16:15:00 ET).
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


def get_session_cutoff_utc(
    session_date: Union[str, date, datetime],
    cutoff_time_et_str: str = "08:45:00"
) -> datetime:
    """Calculates the exact UTC timestamp for a session cutoff in Eastern Time.
    
    Correctly accounts for DST transitions (EDT UTC-4 vs EST UTC-5).
    
    Args:
        session_date: Target session date (e.g. '2026-08-28')
        cutoff_time_et_str: Cutoff time string in ET (default '08:45:00')
        
    Returns:
        datetime: Timezone-aware UTC datetime.
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
