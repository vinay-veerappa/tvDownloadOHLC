"""
filter_engine.py — Generic pivot-table filter engine.

Replicates the WebUI backend's filter logic using pandas pivot tables.
Each feature can subclass or compose this for its own filter needs.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


class FilterEngine:
    """
    Generic pivot-table-based filter engine.

    Builds status and broken pivot tables with shifted previous-session
    columns, then applies filters via boolean masks.

    This replicates the WebUI backend's ProfilerService.apply_filters() logic.
    """

    def __init__(self, sessions: List[dict]):
        """
        Args:
            sessions: Flat list of session dicts with at minimum:
                      date, session, status, broken fields.
        """
        self.status_pivot, self.broken_pivot = self._build_pivots(sessions)

    @staticmethod
    def _build_pivots(sessions: List[dict]) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Build status and broken pivot tables with shifted prev-session columns."""
        rows = []
        for s in sessions:
            d = s.get("date")
            sn = s.get("session")
            if not d or not sn:
                continue
            rows.append({
                "date": d,
                "session": sn,
                "status": s.get("status", ""),
                "broken": bool(s.get("broken", False)),
            })

        if not rows:
            return pd.DataFrame(), pd.DataFrame()

        df = pd.DataFrame(rows).sort_values(["date", "session"])
        status_pivot = df.pivot_table(
            index="date", columns="session", values="status", aggfunc="last"
        )
        broken_pivot = df.pivot_table(
            index="date", columns="session", values="broken", aggfunc="last"
        )

        # Add previous-session context columns (shifted by 1 row)
        for base_session in ["NY1", "NY2", "Asia"]:
            if base_session in status_pivot.columns:
                status_pivot[f"Prev {base_session}"] = status_pivot[base_session].shift(1)
            if base_session in broken_pivot.columns:
                broken_pivot[f"Prev {base_session}"] = broken_pivot[base_session].shift(1)

        status_pivot = status_pivot.sort_index()
        broken_pivot = broken_pivot.reindex(status_pivot.index).fillna(False).astype(bool)
        return status_pivot, broken_pivot

    def apply(
        self,
        target_session: str,
        filters: Dict[str, str],
        broken_filters: Dict[str, str],
        intra_state: str = "Any",
    ) -> List[str]:
        """
        Apply filters and return matching date strings.

        Args:
            target_session: Target session name.
            filters: Dict of session_name -> required_status.
            broken_filters: Dict of session_name -> "Yes"/"No"/"Any".
            intra_state: "Any", "Long", "Short", or exact status.

        Returns:
            List of matching date strings (YYYY-MM-DD).
        """
        mask = pd.Series(True, index=self.status_pivot.index)

        # Status filters
        for session_name, required_status in filters.items():
            if not required_status or required_status == "Any":
                continue
            if session_name not in self.status_pivot.columns:
                return []

            status_series = self.status_pivot[session_name].fillna("")
            if required_status in ["Long", "Short"]:
                mask &= status_series.str.startswith(required_status)
            elif required_status in ["True", "False"]:
                mask &= status_series.str.endswith(required_status)
            else:
                mask &= status_series.eq(required_status)

        # Broken filters
        for session_name, required_broken in broken_filters.items():
            if not required_broken or required_broken == "Any":
                continue
            if session_name not in self.broken_pivot.columns:
                return []

            is_broken = self.broken_pivot[session_name]
            if required_broken in ["Broken", "Yes"]:
                mask &= is_broken
            elif required_broken in ["Not Broken", "No"]:
                mask &= ~is_broken

        # Intra-state filter
        if intra_state and intra_state != "Any":
            if target_session not in self.status_pivot.columns:
                return []
            target_status = self.status_pivot[target_session].fillna("")
            if intra_state in ["Long", "Short"]:
                mask &= target_status.str.startswith(intra_state)
            else:
                mask &= target_status.str.contains(intra_state, regex=False)

        # Exclude dates where the target session is entirely missing (no session record).
        # The lookup table generator skips these dates, and the WebUI's distribution
        # count should not include dates with no target session data.
        if target_session in self.status_pivot.columns:
            mask &= self.status_pivot[target_session].notna()

        return self.status_pivot.index[mask].tolist()
