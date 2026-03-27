"""
ProfilerStats - Computes statistics from a filtered list of session records.

Given a list of matching sessions (from ProfilerFilter), this module computes:
  - Outcome distribution (Long True / Long False / Short True / Short False %)
  - HOD / LOD timing distributions (bucketed to 15-min intervals)
  - Range statistics (median/mean high_pct and low_pct)
  - Level hit rates (PDH, PDM, PDL, Midnight Open, 07:30 Open, session mids)

Level hits are computed on-the-fly from the session's range_high/range_low vs
the institutional levels stored in each session record.

NOTE: Since the precomputed JSON doesn't include PDH/PDL/Midnight values,
we read those from the levels JSON or compute an approximation from session data.
"""

import statistics
from typing import List, Dict, Optional, Any
from collections import defaultdict


ALL_STATUSES = ["Long True", "Long False", "Short True", "Short False"]
# Short-code aliases for display
STATUS_SHORT = {
    "Long True": "LT",
    "Long False": "LF",
    "Short True": "ST",
    "Short False": "SF",
}


HIT_KEYS = [
    "hit_pdh", "hit_pdm", "hit_pdl",
    "hit_midnight", "hit_0730",
    "hit_ny_p12h", "hit_ny_p12m", "hit_ny_p12l",
    "hit_p12h", "hit_p12m", "hit_p12l",
    "hit_p_asia_mid", "hit_p_lon_mid", "hit_p_ny1_mid", "hit_p_ny2_mid"
]


def _bucket_time(time_str: Optional[str], bucket_minutes: int = 15) -> Optional[str]:
    """Round a HH:MM string to the nearest N-minute bucket."""
    if not time_str:
        return None
    try:
        h, m = map(int, time_str.split(":"))
        m_bucket = (m // bucket_minutes) * bucket_minutes
        return f"{h:02d}:{m_bucket:02d}"
    except Exception:
        return None


def compute(sessions: List[dict]) -> Dict[str, Any]:
    """
    Compute full statistics for a set of filtered session records.

    Args:
        sessions: List of session dicts from ProfilerFilter.filter()

    Returns:
        {
          "count": int,
          "distribution": { "Long True": int, "Long False": int, ... },
          "distribution_pct": { "Long True": float, ... },
          "timing": { ... },
          "range": { ... },
          "hit_rates": { "hit_pdh": float, ... }, # HIT percentages
          "by_outcome": {    # All of the above broken down per outcome
              "Long True":  { "count", "timing", "range", "hit_rates" },
              ...
          }
        }
    """
    n = len(sessions)
    if n == 0:
        return {
            "count": 0,
            "distribution": {s: 0 for s in ALL_STATUSES},
            "distribution_pct": {s: 0.0 for s in ALL_STATUSES},
            "timing": {"hod": {}, "lod": {}, "hod_mode": None, "lod_mode": None},
            "range": {"high_pct": {"median": None, "mean": None},
                      "low_pct":  {"median": None, "mean": None}},
            "hit_rates": {k: 0.0 for k in HIT_KEYS},
            "by_outcome": {},
        }

    # --- Distribution ---
    dist = defaultdict(int)
    for s in sessions:
        status = s.get("status")
        if status in ALL_STATUSES:
            dist[status] += 1

    dist_pct = {k: round(v / n * 100, 1) for k, v in dist.items()}

    # --- HOD / LOD Timing ---
    def timing_stats(field: str, sess_list: List[dict]) -> dict:
        buckets = defaultdict(int)
        raw_minutes = []
        for s in sess_list:
            t = _bucket_time(s.get(field))
            if t:
                buckets[t] += 1
                h, m = map(int, t.split(":"))
                raw_minutes.append(h * 60 + m)

        mode = max(buckets, key=buckets.get) if buckets else None
        median_min = int(statistics.median(raw_minutes)) if raw_minutes else None
        median_t = f"{median_min // 60:02d}:{median_min % 60:02d}" if median_min is not None else None

        return {
            "buckets": dict(sorted(buckets.items())),
            "mode": mode,
            "median": median_t,
        }

    hod_t = timing_stats("high_time", sessions)
    lod_t = timing_stats("low_time", sessions)

    timing = {
        "hod": hod_t["buckets"],
        "lod": lod_t["buckets"],
        "hod_mode": hod_t["mode"],
        "lod_mode": lod_t["mode"],
        "hod_median": hod_t["median"],
        "lod_median": lod_t["median"],
    }

    # --- Range stats ---
    def range_stats(field: str, sess_list: List[dict]) -> dict:
        vals = [s[field] for s in sess_list if s.get(field) is not None]
        if not vals:
            return {"median": None, "mean": None}
        return {
            "median": round(statistics.median(vals), 3),
            "mean":   round(sum(vals) / len(vals), 3),
        }

    rng = {
        "high_pct": range_stats("high_pct", sessions),
        "low_pct":  range_stats("low_pct", sessions),
    }

    # --- Hit Rates ---
    def hit_stats(sess_list: List[dict]) -> dict:
        rates = {}
        count = len(sess_list)
        if count == 0:
            return {k: 0.0 for k in HIT_KEYS}
        for k in HIT_KEYS:
            hits = sum(1 for s in sess_list if s.get(k) is True)
            rates[k] = round(hits / count * 100, 1)
        return rates

    hits = hit_stats(sessions)

    # --- Per-outcome breakdown ---
    by_outcome = {}
    for status in ALL_STATUSES:
        subset = [s for s in sessions if s.get("status") == status]
        if not subset:
            continue
        by_outcome[status] = {
            "count": len(subset),
            "timing": {
                "hod": timing_stats("high_time", subset),
                "lod": timing_stats("low_time", subset),
            },
            "range": {
                "high_pct": range_stats("high_pct", subset),
                "low_pct":  range_stats("low_pct", subset),
            },
            "hit_rates": hit_stats(subset),
            "broken_count": sum(1 for s in subset if s.get("broken")),
        }

    return {
        "count": n,
        "distribution": dict(dist),
        "distribution_pct": dist_pct,
        "timing": timing,
        "range": rng,
        "hit_rates": hits,
        "by_outcome": by_outcome,
        "all_sessions": sessions,
    }


class ProfilerStats:
    """Namespace wrapper for stat functions. Use ProfilerStats.compute(sessions)."""
    compute = staticmethod(compute)
