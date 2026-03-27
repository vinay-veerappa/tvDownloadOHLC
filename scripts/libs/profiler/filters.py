"""
ProfilerFilter - Filters session records by cross-session context.

This mirrors the TradingView indicator logic:
  - For Asia:   filter by yesterday's NY1/NY2 status (and optionally broken state)
  - For London: filter by today's Asia status
  - For NY1:    filter by today's Asia + London statuses
  - For NY2:    filter by today's Asia + London + NY1 statuses

Additionally, intra_state narrows results to those historical days where the
TARGET session already had a specific outcome (used when session is in-progress).
"""

from typing import List, Optional, Dict, Tuple
from .loader import ProfilerData, SESSION_ORDER


# Which context keys drive each session's cross-session filter
_SESSION_FILTER_KEYS = {
    "Asia":   [("prev_ny1_status", "NY1"), ("prev_ny2_status", "NY2")],
    "London": [("prev_ny2_status", "NY2"), ("asia_status", "Asia")],
    "NY1":    [("asia_status", "Asia"), ("lon_status", "London")],
    "NY2":    [("asia_status", "Asia"), ("lon_status", "London"), ("ny1_status", "NY1")],
}


class ProfilerFilter:
    """
    Provides static filtering methods for profiler session data.
    All methods return lists of session dicts that match the criteria.
    """

    @staticmethod
    def filter(
        data: ProfilerData,
        session: str,
        context: Dict,
        intra_state: Optional[str] = None,
        broken_filter: Optional[bool] = None,
    ) -> List[dict]:
        """
        Return all historical target-session records that match the provided context.

        Args:
            data:          ProfilerData instance
            session:       Target session: "Asia", "London", "NY1", "NY2"
            context:       Dict from ProfilerData.get_trading_day_context()
                           (or a manually constructed dict with the same keys)
            intra_state:   Optional str to narrow by current session's own status
                           e.g. "Long False" — only show dates where Asia was Long False
            broken_filter: Optional bool to filter by broken status of target session
                           True = only broken, False = only not broken, None = no filter
        
        Returns:
            List of matching session dicts (each is a full session record from the JSON).
        """
        filter_keys = _SESSION_FILTER_KEYS.get(session, [])

        # Build required (cross-session_key -> required_status) map
        # Skip keys where context value is None (session didn't happen or unknown)
        required = {}
        for ctx_key, ref_session in filter_keys:
            val = context.get(ctx_key)
            if val and val != "None":
                required[ref_session] = val

        matched = []

        for trading_date in data.trading_dates:
            # Skip if target session doesn't exist for this date
            target = data.get_session(trading_date, session)
            if not target:
                continue

            # --- Cross-session filter ---
            passed = True
            for ref_session, required_status in required.items():
                # For Asia: ref_session is from PREVIOUS trading day
                if session == "Asia":
                    prev_date = data.get_prev_trading_date(trading_date)
                    ref = data.get_session(prev_date, ref_session) if prev_date else None
                else:
                    ref = data.get_session(trading_date, ref_session)

                if ref is None or ref.get("status") != required_status:
                    passed = False
                    break

            if not passed:
                continue

            # --- Intra-state filter (target session's own outcome) ---
            if intra_state and intra_state != "Any":
                if target.get("status") != intra_state:
                    continue

            # --- Broken filter ---
            if broken_filter is not None:
                if target.get("broken") != broken_filter:
                    continue

            matched.append(target)

        return matched

    @staticmethod
    def filter_for_today(
        data: ProfilerData,
        session: str,
        reference_date: Optional[str] = None,
        intra_state: Optional[str] = None,
    ) -> Tuple[List[dict], Dict]:
        """
        Convenience: Automatically determines the context from the latest available
        trading day (or a specific reference_date) and filters.

        Args:
            data:           ProfilerData instance
            session:        Target session name
            reference_date: Trading date string "YYYY-MM-DD". Defaults to latest.
            intra_state:    Optional outcome to filter by if session already resolved.

        Returns:
            (matched_sessions, context_used)
        """
        ref_date = reference_date or data.trading_dates[-1]
        context = data.get_trading_day_context(ref_date)
        matched = ProfilerFilter.filter(data, session, context, intra_state=intra_state)
        return matched, context
