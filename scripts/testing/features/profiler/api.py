"""
api.py — Profiler-specific WebUI API calls.

Extends the base WebUIClient with profiler-specific endpoints.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from ...core.api_client import WebUIClient


class ProfilerAPIClient(WebUIClient):
    """WebUI API client with profiler-specific endpoints."""

    def get_filtered_stats(
        self,
        ticker: str,
        target_session: str,
        filters: Dict[str, str],
        broken_filters: Dict[str, str],
        intra_state: str = "Any",
    ) -> Dict[str, Any]:
        """Call POST /stats/filtered-stats."""
        return self.post("/stats/filtered-stats", {
            "ticker": ticker,
            "target_session": target_session,
            "filters": filters,
            "broken_filters": broken_filters,
            "intra_state": intra_state,
        })

    def get_daily_hod_lod(
        self,
        ticker: str,
        unadjusted: bool = False,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Call GET /stats/daily-hod-lod/{ticker}."""
        return self.get(f"/stats/daily-hod-lod/{ticker}", {
            "unadjusted": str(unadjusted).lower(),
            "start_date": start_date,
            "end_date": end_date,
        })

    def get_profiler_stats(self, ticker: str, days: int = 50) -> Dict[str, Any]:
        """Call GET /stats/profiler/{ticker}."""
        return self.get(f"/stats/profiler/{ticker}", {"days": str(days)})

    def get_level_touches(
        self,
        ticker: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Call GET /stats/level-touches/{ticker}.

        Returns columnar level touch data with per-session hit times.
        This is what the WebUI frontend uses to compute level hit rates client-side.
        """
        return self.get(f"/stats/level-touches/{ticker}", {
            "start_date": start_date,
            "end_date": end_date,
        })
