from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Optional, List
import pytz

# Setup logger
logger = logging.getLogger(__name__)


@dataclass
class BlackoutWindow:
    """An economic event blackout."""
    event_name: str
    impact: str                     # "High" | "Medium" | "Low"
    event_time: datetime
    pre_minutes: int                # minutes before event the blackout starts
    post_minutes: int               # minutes after event the blackout ends


class CalendarService:
    """Read-only wrapper over EconomicEvent. Adds blackout-window semantics."""

    # Default pre/post buffers per impact level (configurable in config.yaml)
    DEFAULT_BUFFERS = {
        "High": (120, 60),     # 2h before, 1h after (FOMC, NFP, CPI)
        "Medium": (30, 30),    # 30 min on each side
        "Low": (0, 0),         # no buffer
    }

    # Impact hierarchy to filter events
    IMPACT_HIERARCHY = {
        "Low": ["Low", "Medium", "High"],
        "Medium": ["Medium", "High"],
        "High": ["High"]
    }

    def __init__(self, prisma_client, buffers: Optional[dict] = None):
        """
        Args:
            prisma_client: Prisma client instance
            buffers: Optional custom pre/post buffers mapping impact -> (pre_mins, post_mins)
        """
        self.db = prisma_client
        self.buffers = buffers or self.DEFAULT_BUFFERS

    def _normalize_dt(self, dt: Optional[datetime]) -> datetime:
        """Normalize datetime to timezone-aware UTC datetime."""
        if dt is None:
            return datetime.now(pytz.utc)
        if dt.tzinfo is None:
            return pytz.utc.localize(dt)
        return dt.astimezone(pytz.utc)

    async def is_blackout_window(
        self,
        at: Optional[datetime] = None,
        min_impact: str = "High",
    ) -> bool:
        """True if `at` (default: now) falls within a High-or-above impact blackout."""
        utc_at = self._normalize_dt(at)
        eligible_impacts = self.IMPACT_HIERARCHY.get(min_impact, ["High"])

        # Fetch events that could possibly overlap with utc_at
        # Max buffer is 2 hours (120 minutes) pre and 1 hour (60 minutes) post
        # Let's search events within 3 hours on either side to be safe
        search_start = utc_at - timedelta(hours=3)
        search_end = utc_at + timedelta(hours=3)

        try:
            events = await self.db.economicevent.find_many(
                where={
                    "datetime": {
                        "gte": search_start,
                        "lte": search_end,
                    },
                    "impact": {
                        "in": eligible_impacts
                    }
                }
            )
        except Exception as e:
            logger.error(f"Failed to query EconomicEvent from DB: {e}")
            return False

        for event in events:
            # Ensure event datetime is UTC aware
            event_dt = self._normalize_dt(event.datetime)
            pre_mins, post_mins = self.buffers.get(event.impact, (0, 0))
            
            start_time = event_dt - timedelta(minutes=pre_mins)
            end_time = event_dt + timedelta(minutes=post_mins)

            if start_time <= utc_at <= end_time:
                logger.info(f"Blackout active for event '{event.name}' ({event.impact}) at {utc_at}")
                return True

        return False

    async def get_active_blackouts(
        self,
        at: Optional[datetime] = None,
        within_hours: int = 24,
    ) -> List[BlackoutWindow]:
        """All blackouts that are active or upcoming within `within_hours` of `at`."""
        utc_at = self._normalize_dt(at)
        search_start = utc_at - timedelta(hours=3)  # Catch currently active windows
        search_end = utc_at + timedelta(hours=within_hours + 3)

        try:
            events = await self.db.economicevent.find_many(
                where={
                    "datetime": {
                        "gte": search_start,
                        "lte": search_end,
                    }
                },
                order={
                    "datetime": "asc"
                }
            )
        except Exception as e:
            logger.error(f"Failed to query EconomicEvent for active blackouts: {e}")
            return []

        active_blackouts = []
        for event in events:
            event_dt = self._normalize_dt(event.datetime)
            pre_mins, post_mins = self.buffers.get(event.impact, (0, 0))
            
            start_time = event_dt - timedelta(minutes=pre_mins)
            end_time = event_dt + timedelta(minutes=post_mins)

            # Blackout overlaps [utc_at, utc_at + within_hours]
            limit_end = utc_at + timedelta(hours=within_hours)
            if start_time <= limit_end and end_time >= utc_at:
                active_blackouts.append(
                    BlackoutWindow(
                        event_name=event.name,
                        impact=event.impact,
                        event_time=event_dt,
                        pre_minutes=pre_mins,
                        post_minutes=post_mins
                    )
                )

        return active_blackouts

    async def next_blackout_start(
        self,
        after: Optional[datetime] = None,
        min_impact: str = "High",
    ) -> Optional[datetime]:
        """When does the next High+ blackout begin? Used to plan exits before events."""
        utc_after = self._normalize_dt(after)
        eligible_impacts = self.IMPACT_HIERARCHY.get(min_impact, ["High"])

        # Fetch future events
        try:
            events = await self.db.economicevent.find_many(
                where={
                    "datetime": {
                        "gte": utc_after - timedelta(hours=3)  # Search starting slightly early
                    },
                    "impact": {
                        "in": eligible_impacts
                    }
                },
                order={
                    "datetime": "asc"
                }
            )
        except Exception as e:
            logger.error(f"Failed to query next blackout: {e}")
            return None

        for event in events:
            event_dt = self._normalize_dt(event.datetime)
            pre_mins, _ = self.buffers.get(event.impact, (0, 0))
            start_time = event_dt - timedelta(minutes=pre_mins)

            if start_time > utc_after:
                return start_time

        return None
