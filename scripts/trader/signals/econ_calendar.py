import logging
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import List, Dict, Any
from prisma import Prisma

logger = logging.getLogger(__name__)
ET = ZoneInfo("America/New_York")

# Target Macro Windows (time of day in ET)
MACRO_WINDOWS = {
    "RTH Open": datetime.strptime("09:30", "%H:%M").time(),
    "NY_AM_2 (Silver Bullet)": datetime.strptime("10:50", "%H:%M").time(),
}

def check_time_conflict(event_time_et: datetime.time) -> tuple[bool, str]:
    """Check if the event time falls within +/- 15 minutes of any macro window."""
    # Convert event_time_et to a datetime on a dummy day to do timedelta math
    dummy_date = date(2026, 1, 1)
    event_dt = datetime.combine(dummy_date, event_time_et)

    for window_name, window_time in MACRO_WINDOWS.items():
        window_dt = datetime.combine(dummy_date, window_time)
        diff = abs((event_dt - window_dt).total_seconds()) / 60.0
        if diff <= 15.0:
            return True, window_name
            
    return False, ""

async def get_econ_releases(target_date: date, db: Prisma) -> List[Dict[str, Any]]:
    """Retrieve economic releases from Prisma and flag macro-window conflicts."""
    start_dt = datetime.combine(target_date, datetime.min.time(), tzinfo=ET)
    end_dt = datetime.combine(target_date, datetime.max.time(), tzinfo=ET)

    try:
        events = await db.economicevent.find_many(
            where={
                "datetime": {
                    "gte": start_dt,
                    "lte": end_dt
                },
                "country": "USD"
            },
            order={"datetime": "asc"}
        )
    except Exception as e:
        logger.error(f"Failed to fetch economic events from DB: {e}")
        return []

    releases = []
    for e in events:
        impact = (e.impact or "").upper()
        
        # ── US-relevance filter ──
        # Exclude international events that don't directly move US futures.
        # Import the filter functions from briefing_core to avoid duplication.
        try:
            from scripts.trader.briefing_core import _is_non_us_event, _is_us_event
            if _is_non_us_event(e.name) and not _is_us_event(e.name):
                continue
        except ImportError:
            pass  # If import fails, don't filter (graceful degradation)
        
        # Convert DB datetime to ET
        if e.datetime.tzinfo:
            evt_dt = e.datetime.astimezone(ET)
        else:
            evt_dt = e.datetime.replace(tzinfo=timezone.utc).astimezone(ET)

        evt_time_et = evt_dt.time()
        conflict, window_name = check_time_conflict(evt_time_et)

        releases.append({
            "name": e.name,
            "impact": impact or "UNKNOWN",
            "time_et": evt_dt.strftime("%H:%M ET"),
            "datetime": int(evt_dt.timestamp() * 1000),
            "macro_window_conflict": conflict,
            "conflict_window": window_name,
            "forecast": e.forecast,
            "previous": e.previous,
            "actual": e.actual
        })

    return releases
