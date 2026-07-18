"""
compute.py — Local profiler statistics computation.

Replicates the WebUI backend's get_filtered_stats() computation logic
using raw profiler JSON data. Used as the "local reference" to compare
against the WebUI API response.
"""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from typing import Any, Dict, List, Optional

import numpy as np

from .data import ALL_STATUSES, HIT_KEYS


# ── Level hit rate helpers ──────────────────────────────────────────────────

HIT_TO_LEVEL = {
    "hit_pdh": "pdh", "hit_pdm": "pdm", "hit_pdl": "pdl",
    "hit_midnight": "midnight_open", "hit_0730": "open_0730",
    "hit_daily_open": "daily_open",
    "hit_ny_p12h": "ny_p12h", "hit_ny_p12m": "ny_p12m", "hit_ny_p12l": "ny_p12l",
    "hit_p12h": "p12h", "hit_p12m": "p12m", "hit_p12l": "p12l",
    "hit_p_asia_mid": "asia_mid", "hit_p_lon_mid": "london_mid",
    "hit_p_ny1_mid": "ny1_mid", "hit_p_ny2_mid": "ny2_mid",
    "hit_prev_asia_mid": "prev_asia_mid", "hit_prev_lon_mid": "prev_london_mid",
    "hit_prev_ny1_mid": "prev_ny1_mid", "hit_prev_ny2_mid": "prev_ny2_mid",
}


def _compute_level_hits_from_columnar(
    result: Dict[str, float],
    columnar_data: Dict[str, Any],
    matched_dates: List[str],
    target_session: str,
    total: int,
):
    """
    Compute level hit rates from WebUI columnar level touches data.

    The WebUI frontend computes hit rates by checking if
    hits.{targetSession}[dateIdx] != -1 for each matched date.
    """
    webui_dates = columnar_data.get("dates", [])
    webui_levels = columnar_data.get("levels", {})
    for k in HIT_KEYS:
        level_name = HIT_TO_LEVEL.get(k)
        if not level_name or level_name not in webui_levels:
            result[k] = 0.0
            continue
        level_data = webui_levels[level_name]
        session_hits = level_data.get("hits", {}).get(target_session, [])
        if not session_hits:
            result[k] = 0.0
            continue
        touched = 0
        counted = 0
        for d in matched_dates:
            if d in webui_dates:
                idx = webui_dates.index(d)
                counted += 1
                if idx < len(session_hits) and session_hits[idx] != -1:
                    touched += 1
        result[k] = round(touched / counted * 100, 1) if counted else 0.0


def _compute_level_hits_from_raw(
    result: Dict[str, float],
    level_touches: Dict[str, dict],
    matched_dates: List[str],
    total: int,
):
    """Fallback: compute from raw level_touches.json (daily-level)."""
    for k in HIT_KEYS:
        level_name = HIT_TO_LEVEL.get(k)
        if level_name:
            hits = sum(
                1 for d in matched_dates
                if d in level_touches and level_touches[d].get(level_name, {}).get("touched")
            )
        else:
            hits = 0
        result[k] = round(hits / total * 100, 1) if total else 0.0


def _mode_bucket(values: List[float], bucket_size: float = 0.1) -> Optional[float]:
    """Find the mode bin from a list of floats.
    Uses floor-to-bin-start (matching WebUI's modeBin function).
    Tie-breaking: pick first numerically (sorted) — deterministic and robust."""
    if not values:
        return None
    buckets: Dict[float, int] = defaultdict(int)
    for v in values:
        bin_start = math.floor(v / bucket_size) * bucket_size
        buckets[round(bin_start, 1)] += 1
    max_count = max(buckets.values())
    candidates = sorted([k for k, v in buckets.items() if v == max_count])
    return candidates[0]


def _median_bin(values: List[float], bucket_size: float = 0.1) -> Optional[float]:
    """Find the median bin from a list of floats.
    Uses floor-to-bin-start (matching WebUI's medianBin function)."""
    if not values:
        return None
    sorted_vals = sorted(values)
    mid_idx = len(sorted_vals) // 2
    median_val = sorted_vals[mid_idx]
    bin_start = math.floor(median_val / bucket_size) * bucket_size
    return round(bin_start, 1)


def _bucket_time(t_str: Optional[str]) -> Optional[str]:
    """Round a HH:MM string to the nearest 15-min bucket."""
    if not t_str:
        return None
    try:
        h, m = map(int, t_str.split(":"))
        m_bucket = (m // 15) * 15
        return f"{h:02d}:{m_bucket:02d}"
    except Exception:
        return None


def _time_mode(times: List[str]) -> str:
    """Find the mode 15-min bucket from a list of HH:MM times.
    Returns range format like '14:45-15:00' (matches lookup table).
    Tie-breaking: pick first numerically (sorted) — deterministic and robust."""
    buckets: Dict[str, int] = defaultdict(int)
    for t in times:
        b = _bucket_time(t)
        if b:
            buckets[b] += 1
    if not buckets:
        return ""
    max_count = max(buckets.values())
    candidates = sorted([k for k, v in buckets.items() if v == max_count])
    mode = candidates[0]
    h, m = map(int, mode.split(":"))
    end_m = m + 15
    end_h = h
    if end_m >= 60:
        end_m -= 60
        end_h += 1
    return f"{mode}-{end_h:02d}:{end_m:02d}"


def _time_buckets(sess_list: List[dict], field: str) -> Dict[str, int]:
    """Build 15-min bucket distribution for a time field."""
    buckets: Dict[str, int] = defaultdict(int)
    for s in sess_list:
        t = _bucket_time(s.get(field))
        if t:
            buckets[t] += 1
    return dict(sorted(buckets.items()))


def compute_filtered_stats(
    sessions: List[dict],
    target_session: str,
    matched_dates: List[str],
    hod_lod_data: Optional[Dict[str, dict]] = None,
    level_touches: Optional[Dict[str, dict]] = None,
    webui_level_touches: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Compute statistics for a set of matched dates.

    Replicates the WebUI backend's get_filtered_stats() computation.
    Per-outcome stats use FULL-DAY data from raw daily_hod_lod.json
    (adjusted prices + times), matching the lookup table generator's logic.

    Args:
        sessions: Flat list of all profiler session dicts.
        target_session: Target session name (Asia/London/NY1/NY2).
        matched_dates: List of date strings that passed the filter.
        hod_lod_data: Optional daily HOD/LOD data (dict keyed by date).
        level_touches: Optional raw level touches data (daily-level).
        webui_level_touches: Optional WebUI columnar level touches data.

    Returns:
        Dict with keys matching the WebUI API response structure.
    """
    date_set = set(matched_dates)
    # Build a date->session map for ordered iteration (matching lookup generator's date order)
    sessions_by_date: Dict[str, Dict[str, dict]] = defaultdict(dict)
    for s in sessions:
        d = s.get("date")
        sn = s.get("session")
        if d and sn and d in date_set:
            sessions_by_date[d][sn] = s

    # Iterate in sorted date order (matching lookup table generator)
    target_sessions = []
    for d in sorted(date_set):
        sess = sessions_by_date.get(d, {}).get(target_session)
        if sess:
            target_sessions.append(sess)

    n = len(matched_dates)  # WebUI counts ALL matched dates
    if n == 0:
        return {"count": 0}

    # ── Distribution (WebUI includes "None" as a status) ──
    dist: Dict[str, int] = defaultdict(int)
    for s in target_sessions:
        status = s.get("status") or "None"
        dist[status] += 1

    dist_pct: Dict[str, float] = {}
    for status in ALL_STATUSES:
        dist_pct[status] = round(dist.get(status, 0) / n * 100, 1)

    # ── Range stats (median, mean, mode) ──
    high_pcts = [s.get("high_pct", 0) for s in target_sessions if s.get("high_pct") is not None]
    low_pcts = [s.get("low_pct", 0) for s in target_sessions if s.get("low_pct") is not None]

    range_stats = {
        "high_pct": {
            "median": round(float(np.median(high_pcts)), 3) if high_pcts else None,
            "mean": round(float(np.mean(high_pcts)), 3) if high_pcts else None,
            "mode": _mode_bucket(high_pcts),
        },
        "low_pct": {
            "median": round(float(np.median(low_pcts)), 3) if low_pcts else None,
            "mean": round(float(np.mean(low_pcts)), 3) if low_pcts else None,
            "mode": _mode_bucket(low_pcts),
        },
    }

    # ── Level hit rates ──
    # The WebUI frontend computes these from GET /stats/level-touches/{ticker}
    # which returns per-session hit times (columnar format).
    # Use that data when available for accurate comparison.
    level_hit_rates: Dict[str, float] = {}
    if webui_level_touches and "error" not in webui_level_touches:
        _compute_level_hits_from_columnar(level_hit_rates, webui_level_touches,
                                          matched_dates, target_session, n)
    elif level_touches:
        # Fallback: raw level_touches.json (daily-level, not session-level)
        _compute_level_hits_from_raw(level_hit_rates, level_touches, matched_dates, n)
    else:
        for k in HIT_KEYS:
            level_hit_rates[k] = 0.0

    # ── HOD/LOD timing ──
    hod_timing = _time_buckets(target_sessions, "high_time")
    lod_timing = _time_buckets(target_sessions, "low_time")

    # ── Per-outcome breakdown ──
    # Uses FULL-DAY data from raw daily_hod_lod.json (adjusted prices + times),
    # matching the lookup table generator's logic.
    by_outcome: Dict[str, dict] = {}
    for status in ALL_STATUSES:
        subset = [s for s in target_sessions if s.get("status") == status]
        if not subset:
            continue

        subset_dates = [s.get("date") for s in subset if s.get("date")]

        # ── Full-day HOD/LOD timing + price range from raw hod_lod_data ──
        hod_times = []
        lod_times = []
        h_pcts = []
        l_pcts = []
        broken_count = 0

        for d in subset_dates:
            rec = next((s for s in subset if s.get("date") == d), {})
            day_hl = hod_lod_data.get(d, {}) if hod_lod_data else {}
            daily_open = day_hl.get("daily_open")
            # Use daily_high/daily_low (matching WebUI RangeDistribution component)
            daily_high = day_hl.get("daily_high")
            daily_low = day_hl.get("daily_low")

            if daily_open and daily_open > 0:
                # Do NOT round — WebUI uses unrounded values for binning
                h_pct = ((daily_high / daily_open - 1) * 100) if daily_high is not None else None
                l_pct = ((daily_low / daily_open - 1) * 100) if daily_low is not None else None
            else:
                h_pct = rec.get("high_pct")
                l_pct = rec.get("low_pct")

            if h_pct is not None and l_pct is not None:
                h_pcts.append(h_pct)
                l_pcts.append(l_pct)

            ht = day_hl.get("hod_time") or rec.get("high_time", "")
            lt = day_hl.get("lod_time") or rec.get("low_time", "")
            if ht:
                hod_times.append(ht)
            if lt:
                lod_times.append(lt)

            if rec.get("broken"):
                broken_count += 1

        # Price stats from full-day data (matching lookup table generator)
        h_mode = _mode_bucket(h_pcts) if h_pcts else None
        l_mode = _mode_bucket(l_pcts) if l_pcts else None
        # WebUI uses floor-to-bin-start for median (matching medianBin function)
        h_med = _median_bin(h_pcts) if h_pcts else None
        l_med = _median_bin(l_pcts) if l_pcts else None
        h_avg = round(sum(h_pcts) / len(h_pcts), 2) if h_pcts else None
        l_avg = round(sum(l_pcts) / len(l_pcts), 2) if l_pcts else None

        # Per-outcome level hit rates
        olh: Dict[str, float] = {}
        subset_dates = [s.get("date") for s in subset if s.get("date")]
        if webui_level_touches and "error" not in webui_level_touches:
            _compute_level_hits_from_columnar(olh, webui_level_touches,
                                              subset_dates, target_session, len(subset))
        elif level_touches:
            _compute_level_hits_from_raw(olh, level_touches, subset_dates, len(subset))
        else:
            for k in HIT_KEYS:
                olh[k] = 0.0

        by_outcome[status] = {
            "count": len(subset),
            "price_stats": {
                "h_mode": h_mode, "h_med": h_med, "h_avg": h_avg,
                "l_mode": l_mode, "l_med": l_med, "l_avg": l_avg,
            },
            "timing": {
                "hod_mode": _time_mode(hod_times),
                "lod_mode": _time_mode(lod_times),
                "hod_buckets": _time_buckets(subset, "high_time"),
                "lod_buckets": _time_buckets(subset, "low_time"),
            },
            "broken_rate": round(broken_count / len(subset) * 100, 1),
            "level_hit_rates": olh,
        }

    # ── Full-day HOD/LOD ──
    full_day_hod: List[str] = []
    full_day_lod: List[str] = []
    if hod_lod_data:
        for d in matched_dates:
            if d in hod_lod_data:
                full_day_hod.append(hod_lod_data[d].get("hod_time", ""))
                full_day_lod.append(hod_lod_data[d].get("lod_time", ""))

    return {
        "count": n,
        "distribution": dist_pct,
        "distribution_counts": dict(dist),
        "range_stats": range_stats,
        "level_hit_rates": level_hit_rates,
        "hod_timing": hod_timing,
        "lod_timing": lod_timing,
        "by_outcome": by_outcome,
        "full_day_hod_lod": {
            "hod_mode": _time_mode(full_day_hod),
            "lod_mode": _time_mode(full_day_lod),
        },
    }
