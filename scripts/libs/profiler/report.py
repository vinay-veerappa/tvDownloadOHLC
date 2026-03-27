"""
ProfilerReport - Renders profiler statistics as the standard institutional table.

Produces the format:
  | Session Outcomes | Stats | LOD Time | HOD Time | LOD Dist | HOD Dist | ...levels... |

When intra_state is set (session already resolved), it shows the single outcome row.
When intra_state is None, it shows all 4 outcome rows (LT/LF/ST/SF).
"""

from typing import Optional, Dict, List, Any
from .stats import ALL_STATUSES, STATUS_SHORT
from .filters import _SESSION_FILTER_KEYS

# Display-friendly keys for context
_CONTEXT_LABELS = {
    "prev_ny1_status":  "Prev NY1",
    "prev_ny2_status":  "Prev NY2",
    "prev_asia_status": "Prev Asia",
    "prev_lon_status":  "Prev London",
    "asia_status":      "Asia",
    "lon_status":       "London",
    "ny1_status":       "NY1",
    "ny2_status":       "NY2",
}


def _fmt(val, fallback="-") -> str:
    """Safely format a value for table display."""
    if val is None:
        return fallback
    if isinstance(val, float):
        return f"{val:.2f}%"
    return str(val)


class ProfilerReport:
    """
    Renders profiler statistics as a human-readable markdown table.
    """

    @staticmethod
    def render(
        result: Dict[str, Any],
        ticker: str,
        session: str,
        context: Optional[Dict] = None,
        intra_state: Optional[str] = None,
        reference_date: Optional[str] = None,
    ) -> str:
        """
        Render the institutional profiler report as a markdown string.

        Args:
            result:         From ProfilerStats.compute()
            ticker:         e.g. "NQ1"
            session:        e.g. "Asia"
            context:        The context dict used for filtering (for display)
            intra_state:    Current session resolved outcome (if known)
            reference_date: Trading date being analyzed

        Returns:
            Markdown-formatted string ready for print() or saving.
        """
        lines = []

        # --- Header ---
        date_label = f" — {reference_date}" if reference_date else ""
        lines.append(f"## {ticker} {session} Session Profiler{date_label}")
        lines.append(f"**Sample Size**: {result['count']} historical matches")
        lines.append("")

        # --- Context used ---
        # Only show context keys that were actually used as filters for this session
        if context:
            active_filter_keys = {ctx_key for ctx_key, _ in _SESSION_FILTER_KEYS.get(session, [])}
            ctx_parts = []
            for key, label in _CONTEXT_LABELS.items():
                if key not in active_filter_keys:
                    continue  # Skip keys not relevant to this session
                val = context.get(key)
                if val and val != "None":
                    ctx_parts.append(f"{label}: **{val}**")
            if ctx_parts:
                lines.append("**Filters Applied**: " + " | ".join(ctx_parts))
            else:
                lines.append("**Filters Applied**: _None (unfiltered — no prior session data)_")
            lines.append("")

        if intra_state:
            lines.append(f"**Current Status**: {intra_state}")
            lines.append("")

        if result["count"] == 0:
            lines.append("_No historical matches found for this combination._")
            return "\n".join(lines)

        # --- Main Outcomes Table ---
        dist = result["distribution"]
        dist_pct = result["distribution_pct"]
        timing = result["timing"]
        rng = result["range"]
        by_outcome = result["by_outcome"]
        total = result["count"]

        headers = [
            f"{session} Outcome", "Prob", "Count",
            "LOD Time", "HOD Time",
            "LOD Dist%", "HOD Dist%",
            "Broken%"
        ]
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("| " + " | ".join(["---"] * len(headers)) + " |")

        for status in ALL_STATUSES:
            count = dist.get(status, 0)
            if count == 0:
                continue
            pct = dist_pct.get(status, 0.0)
            short = STATUS_SHORT[status]
            od = by_outcome.get(status, {})
            lod_t = od.get("timing", {}).get("lod", {}).get("median") or timing.get("lod_median") or "—"
            hod_t = od.get("timing", {}).get("hod", {}).get("median") or timing.get("hod_median") or "—"
            lod_dist = od.get("range", {}).get("low_pct", {}).get("median")
            hod_dist = od.get("range", {}).get("high_pct", {}).get("median")
            broken_n = od.get("broken_count", 0)
            broken_pct = f"{broken_n / count * 100:.0f}%" if count else "—"

            row = [
                f"**{short}** {status}",
                f"{pct:.1f}%",
                str(count),
                lod_t,
                hod_t,
                _fmt(lod_dist),
                _fmt(hod_dist),
                broken_pct,
            ]
            lines.append("| " + " | ".join(row) + " |")

        lines.append("")

        # --- Timing Breakdown (HOD / LOD by bucket) ---
        if timing["hod"] or timing["lod"]:
            lines.append("### HOD / LOD Timing (15-min buckets, all outcomes)")
            lines.append("")
            
            all_times = sorted(set(list(timing["hod"].keys()) + list(timing["lod"].keys())))
            lines.append("| Time  | HOD | LOD |")
            lines.append("| ----- | --- | --- |")
            for t in all_times:
                hod_n = timing["hod"].get(t, 0)
                lod_n = timing["lod"].get(t, 0)
                if hod_n or lod_n:
                    lines.append(f"| {t} | {hod_n} | {lod_n} |")
            lines.append("")

        # --- Per-Outcome Timing Deep Dive ---
        lines.append("### Per-Outcome Timing")
        lines.append("")
        t_headers = ["Outcome", "HOD Mode", "HOD Median", "LOD Mode", "LOD Median"]
        lines.append("| " + " | ".join(t_headers) + " |")
        lines.append("| " + " | ".join(["---"] * len(t_headers)) + " |")
        for status in ALL_STATUSES:
            od = by_outcome.get(status)
            if not od:
                continue
            hod_mode = od["timing"]["hod"].get("mode") or "—"
            hod_med  = od["timing"]["hod"].get("median") or "—"
            lod_mode = od["timing"]["lod"].get("mode") or "—"
            lod_med  = od["timing"]["lod"].get("median") or "—"
            lines.append(f"| {STATUS_SHORT[status]} | {hod_mode} | {hod_med} | {lod_mode} | {lod_med} |")
        lines.append("")

        return "\n".join(lines)

    @staticmethod
    def print(result, ticker, session, context=None, intra_state=None, reference_date=None):
        """Convenience wrapper: renders and prints directly."""
        print(ProfilerReport.render(result, ticker, session, context, intra_state, reference_date))
