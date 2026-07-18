"""
generate_profiler_lookup.py — Precompute full profiler prediction lookup tables.

Generates 4 compact JSON lookup tables (one per session) that map
context signatures directly to prediction data. Eliminates the need
for runtime filtering, pivoting, and stat computation.

Context signature format:
  Asia:   "prev_ny1_status|prev_ny1_broken|prev_ny2_status|prev_ny2_broken"
  London: "asia_status|asia_broken|prev_ny2_status|prev_ny2_broken"
  NY1:    "asia_status|asia_broken|london_status|london_broken"
  NY2:    "asia_status|asia_broken|london_status|london_broken|ny1_status|ny1_broken"

Status values: LT, LF, ST, SF
Broken values: T (True/broken), F (False/held)

Each entry contains:
  - probabilities: {outcome: probability}
  - price_stats: {outcome: {h_mode, h_med, l_mode, l_med, h_span, l_span, ...}}
  - hod_lod_times: {outcome: {hod_mode, lod_mode}}
  - broken_rates: {outcome: rate}
  - samples: total matching days
  - level_hit_rates: {outcome: {level_key: {hit_rate, mode_time}}}

Usage:
    python -m scripts.libs_py.profiler.generate_profiler_lookup
    python -m scripts.libs_py.profiler.generate_profiler_lookup --ticker NQ1
    python -m scripts.libs_py.profiler.generate_profiler_lookup --ticker ES1
"""

from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[3]
_DATA = _REPO / "data"
_DERIVED = _DATA / "derived"

# Short status codes
_STATUS_SHORT = {
    "Long True": "LT", "Long False": "LF",
    "Short True": "ST", "Short False": "SF",
    "None": "—",
}
_SHORT_TO_FULL = {v: k for k, v in _STATUS_SHORT.items() if v != "—"}

ALL_STATUSES = ["Long True", "Long False", "Short True", "Short False"]
ALL_SHORT = ["LT", "LF", "ST", "SF"]

# Context dependency chain
CONTEXT_CHAIN = {
    "Asia":   [("prev", "NY1"), ("prev", "NY2")],
    "London": [("curr", "Asia"), ("prev", "NY2")],
    "NY1":    [("curr", "Asia"), ("curr", "London")],
    "NY2":    [("curr", "Asia"), ("curr", "London"), ("curr", "NY1")],
}

# Level keys to track
LEVEL_KEYS = [
    "pdh", "pdl", "pdm",
    "p12h", "p12m", "p12l",
    "ny_p12h", "ny_p12m", "ny_p12l",
    "daily_open", "midnight_open", "open_0730",
    "asia_mid", "london_mid", "ny1_mid", "ny2_mid",
]


def _load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _mode_bucket(values: list[float], bucket_size: float = 0.1) -> float:
    if not values:
        return 0.0
    buckets: dict[float, int] = defaultdict(int)
    for v in values:
        bin_start = math.floor(v / bucket_size) * bucket_size
        buckets[round(bin_start, 1)] += 1
    if not buckets:
        return 0.0
    max_count = max(buckets.values())
    candidates = sorted([k for k, v in buckets.items() if v == max_count])
    return candidates[0]


def _median_bin(values: list[float], bucket_size: float = 0.1) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    mid_idx = len(sorted_vals) // 2
    median_val = sorted_vals[mid_idx]
    bin_start = math.floor(median_val / bucket_size) * bucket_size
    return round(bin_start, 1)


def _time_mode_bucket(times: list[str]) -> str:
    if not times:
        return ""
    buckets: dict[str, int] = defaultdict(int)
    for t in times:
        try:
            h, m = map(int, t.split(":"))
            bucket = f"{h:02d}:{(m // 15) * 15:02d}"
            buckets[bucket] += 1
        except Exception:
            continue
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


def _build_key(context_sessions: list[tuple[str, str, bool]]) -> str:
    """Build context signature key from list of (session_name, status, broken)."""
    parts = []
    for _, status, broken in context_sessions:
        short = _STATUS_SHORT.get(status, "—")
        bk = "T" if broken else "F"
        parts.append(f"{short}|{bk}")
    return "|".join(parts)


def _compute_level_hits_for_dates(
    level_touches: dict,
    dates: list[str],
) -> dict[str, dict]:
    """Compute level hit rates for a set of dates (raw daily-level, any session)."""
    if not dates or not level_touches:
        return {}

    n = len(dates)
    level_hits: dict[str, int] = defaultdict(int)
    level_times: dict[str, list[str]] = defaultdict(list)

    for d in dates:
        day_data = level_touches.get(d, {})
        if not isinstance(day_data, dict):
            continue
        for level_key, lv_data in day_data.items():
            if not isinstance(lv_data, dict):
                continue
            if lv_data.get("touched"):
                level_hits[level_key] += 1
                times = lv_data.get("touch_times", [])
                if times:
                    level_times[level_key].extend(times)

    result = {}
    for level_key, hits in level_hits.items():
        times = level_times.get(level_key, [])
        mode_time = ""
        if times:
            buckets: dict[str, int] = defaultdict(int)
            for t in times:
                try:
                    h, m = map(int, t.split(":"))
                    buckets[f"{h:02d}:{(m // 15) * 15:02d}"] += 1
                except Exception:
                    continue
            if buckets:
                mode_time = max(buckets, key=buckets.get)

        result[level_key] = {
            "hit_rate": round(hits / n * 100, 1),
            "samples": n,
            "hits": hits,
            "mode_time": mode_time,
        }

    return result


def _compute_session_level_hits_from_columnar(
    columnar: dict,
    dates: list[str],
    target_session: str,
) -> dict[str, dict]:
    """Compute per-session level hit rates and timing from columnar data.

    Replicates the WebUI's DailyLevels component logic:
    hits.{targetSession}[dateIdx] != -1 for each matched date.
    Also computes mode and median hit times (15-min buckets).

    Returns dict of {level_key: {hit_rate, mode_time, median_time}}.
    """
    if not dates or not columnar:
        return {}

    webui_dates = columnar.get("dates", [])
    webui_levels = columnar.get("levels", {})
    date_idx_map = {d: i for i, d in enumerate(webui_dates)}

    def _mins_to_str(mins):
        """Convert minutes-from-midnight to HH:MM string."""
        if mins is None or mins < 0:
            return None
        h, m = divmod(int(mins), 60)
        return f"{h:02d}:{m:02d}"

    def _bucket_time(t_str):
        """Round HH:MM to 15-min bucket."""
        if not t_str:
            return None
        try:
            h, m = map(int, t_str.split(":"))
            return f"{h:02d}:{(m // 15) * 15:02d}"
        except Exception:
            return None

    def _time_mode(times):
        """Find mode 15-min bucket from HH:MM times. Sorted tie-breaking."""
        buckets: dict[str, int] = defaultdict(int)
        for t in times:
            b = _bucket_time(t)
            if b:
                buckets[b] += 1
        if not buckets:
            return None
        max_count = max(buckets.values())
        candidates = sorted([k for k, v in buckets.items() if v == max_count])
        return candidates[0]

    def _time_median(times):
        """Find median 15-min bucket from HH:MM times."""
        buckets = sorted([_bucket_time(t) for t in times if _bucket_time(t)])
        if not buckets:
            return None
        return buckets[len(buckets) // 2]

    result = {}
    for level_key, level_data in webui_levels.items():
        session_hits = level_data.get("hits", {}).get(target_session, [])
        if not session_hits:
            continue
        touched = 0
        counted = 0
        hit_times = []
        for d in dates:
            idx = date_idx_map.get(d)
            if idx is None or idx >= len(session_hits):
                continue
            counted += 1
            if session_hits[idx] != -1:
                touched += 1
                t_str = _mins_to_str(session_hits[idx])
                if t_str:
                    hit_times.append(t_str)
        if counted > 0:
            result[level_key] = {
                "hit_rate": round(touched / counted * 100, 1),
                "mode_time": _time_mode(hit_times),
                "median_time": _time_median(hit_times),
            }
    return result


def _compute_entry(
    outcome_dates: dict[str, list[str]],
    target_session: str,
    pivot: dict[str, dict[str, dict]],
    daily_hl: dict,
    columnar_level_touches: dict | None = None,
) -> dict[str, Any]:
    """Compute a single lookup table entry from outcome→dates mapping.

    If columnar_level_touches is provided, computes per-outcome, per-session
    level hit rates matching the WebUI's DailyLevels component logic.
    """
    total = sum(len(d) for d in outcome_dates.values())
    if total == 0:
        return {"samples": 0, "probabilities": {}, "price_stats": {}, "hod_lod_times": {}, "broken_rates": {}}

    entry: dict[str, Any] = {"samples": total}

    # Probabilities
    probs = {}
    for status in ALL_SHORT:
        full = _SHORT_TO_FULL.get(status, status)
        count = len(outcome_dates.get(full, []))
        if count > 0:
            probs[status] = round(count / total, 3)
    entry["probabilities"] = probs

    # Price stats + HOD/LOD + broken + per-outcome level hits per outcome
    price_stats = {}
    hod_lod_times = {}
    broken_rates = {}
    per_outcome_level_hits = {}

    for status in ALL_SHORT:
        full = _SHORT_TO_FULL.get(status, status)
        dates_list = outcome_dates.get(full, [])
        if not dates_list:
            continue

        # Compute per-outcome level hits from columnar data (matches WebUI DailyLevels)
        if columnar_level_touches:
            olh = _compute_session_level_hits_from_columnar(
                columnar_level_touches, dates_list, target_session
            )
            if olh:
                per_outcome_level_hits[status] = olh

        h_vals = []
        l_vals = []
        hod_times = []
        lod_times = []
        broken_count = 0

        for d in dates_list:
            rec = pivot.get(d, {}).get(target_session, {})
            day_hl = daily_hl.get(d, {})
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
                h_vals.append(h_pct)
                l_vals.append(l_pct)

            ht = day_hl.get("hod_time") or rec.get("high_time", "")
            lt = day_hl.get("lod_time") or rec.get("low_time", "")
            if ht:
                hod_times.append(ht)
            if lt:
                lod_times.append(lt)

            if rec.get("broken"):
                broken_count += 1

        if h_vals and l_vals:
            h_mode = _mode_bucket(h_vals)
            h_med = _median_bin(h_vals)
            l_mode = _mode_bucket(l_vals)
            l_med = _median_bin(l_vals)
            price_stats[status] = {
                "h_avg": round(sum(h_vals) / len(h_vals), 2),
                "l_avg": round(sum(l_vals) / len(l_vals), 2),
                "h_mode": h_mode,
                "l_mode": l_mode,
                "h_med": h_med,
                "l_med": l_med,
                "h_span": f"{h_mode:.1f} to {h_mode + 0.1:.1f}%",
                "l_span": f"{l_mode:.1f} to {l_mode + 0.1:.1f}%",
                "sample_count": len(h_vals),
            }

        if hod_times or lod_times:
            hod_lod_times[status] = {
                "hod_mode": _time_mode_bucket(hod_times),
                "lod_mode": _time_mode_bucket(lod_times),
            }

        if len(dates_list) > 0:
            broken_rates[status] = round(broken_count / len(dates_list), 3)

    entry["price_stats"] = price_stats
    entry["hod_lod_times"] = hod_lod_times
    entry["broken_rates"] = broken_rates
    if per_outcome_level_hits:
        entry["per_outcome_level_hits"] = per_outcome_level_hits
    return entry


def generate(ticker: str = "NQ1") -> dict[str, dict]:
    """Generate all 4 lookup tables for a ticker.

    Returns:
        {
          "tables": {"Asia": {key: entry, ...}, "London": {...}, ...},
          "level_hits": {"Asia": {"LT": {level: {hit_rate, ...}}, ...}, ...},
          "base_rates": {"Asia": {"LT": 0.35, ...}, ...},
        }
    """
    # Load data
    profiler_path = _DATA / f"{ticker}_profiler.json"
    hl_path = _DATA / f"{ticker}_daily_hod_lod_unadjusted.json"
    touches_path = _DATA / f"{ticker}_level_touches.json"
    columnar_path = _DATA / f"{ticker}_level_touches_columnar.json"

    if not profiler_path.exists():
        print(f"ERROR: {profiler_path} not found")
        return {}

    sessions = _load_json(profiler_path)
    daily_hl = _load_json(hl_path) if hl_path.exists() else {}
    level_touches = _load_json(touches_path) if touches_path.exists() else {}
    columnar_level_touches = _load_json(columnar_path) if columnar_path.exists() else {}

    # Build pivot
    pivot: dict[str, dict[str, dict]] = defaultdict(dict)
    for s in sessions:
        d = s.get("date")
        sess = s.get("session")
        if d and sess:
            pivot[d][sess] = s
    dates = sorted(pivot.keys())

    print(f"Loaded {len(sessions)} session records across {len(dates)} trading days")

    # ── Generate each table ──
    tables: dict[str, dict] = {}
    # Level hit rates: keyed by (session, outcome) only — NOT by context
    level_hits_global: dict[str, dict[str, dict]] = {}
    # Base rates: unconditional outcome distribution per session
    base_rates: dict[str, dict] = {}

    for target_session, context_specs in CONTEXT_CHAIN.items():
        print(f"\n  Generating {target_session} table...")

        # Accumulator: key → {outcome: [dates]}
        key_outcomes: dict[str, dict[str, list[str]]] = defaultdict(
            lambda: defaultdict(list)
        )
        # Global accumulator: outcome → [dates] (all contexts combined)
        global_outcomes: dict[str, list[str]] = defaultdict(list)

        for i, curr_date in enumerate(dates):
            # Only skip first date if the context chain requires prev-day sessions
            needs_prev = any(src == "prev" for src, _ in context_specs)
            if i == 0 and needs_prev:
                continue
            prev_date = dates[i - 1] if i > 0 else ""
            curr = pivot.get(curr_date, {})
            prev = pivot.get(prev_date, {}) if prev_date else {}

            # Build context
            context = []
            valid = True
            for src, sess_name in context_specs:
                if src == "prev":
                    rec = prev.get(sess_name, {})
                else:
                    rec = curr.get(sess_name, {})

                status = rec.get("status", "")
                broken = bool(rec.get("broken", False))
                if status not in ALL_STATUSES:
                    valid = False
                    break
                context.append((sess_name, status, broken))

            if not valid:
                continue

            # Get target outcome — include "None" status in count (matches WebUI)
            target_rec = curr.get(target_session, {})
            target_status = target_rec.get("status", "")
            if not target_status:
                continue

            key = _build_key(context)
            # Only track valid outcome statuses for per-outcome stats
            if target_status in ALL_STATUSES:
                key_outcomes[key][target_status].append(curr_date)
                global_outcomes[target_status].append(curr_date)
            else:
                # "None" or other statuses: still count in total (matches WebUI distribution)
                key_outcomes[key][target_status].append(curr_date)
                global_outcomes[target_status].append(curr_date)

        # ── Compute per-key stats ──
        table: dict[str, dict] = {}
        # Also accumulate by status-only key (no broken) for aggregation
        status_only_outcomes: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))

        for key, outcome_dates in key_outcomes.items():
            total = sum(len(d) for d in outcome_dates.values())
            if total == 0:
                continue
            entry = _compute_entry(outcome_dates, target_session, pivot, daily_hl,
                                    columnar_level_touches=columnar_level_touches)
            table[key] = entry

            # Also accumulate to status-only key (drop broken bits)
            parts = key.split("|")
            status_parts = []
            for j in range(0, len(parts), 2):
                status_parts.append(parts[j])
            status_key = "|".join(status_parts)
            for status, dlist in outcome_dates.items():
                status_only_outcomes[status_key][status].extend(dlist)

        # Add status-only keys (aggregated across broken/held)
        for status_key, outcome_dates in status_only_outcomes.items():
            total = sum(len(d) for d in outcome_dates.values())
            if total == 0:
                continue
            entry = _compute_entry(outcome_dates, target_session, pivot, daily_hl,
                                    columnar_level_touches=columnar_level_touches)
            table[status_key] = entry

        tables[target_session] = table

        # ── Compute global level hit rates (per outcome, not per context) ──
        session_level_hits: dict[str, dict] = {}
        for status in ALL_SHORT:
            full = _SHORT_TO_FULL.get(status, status)
            dates_list = global_outcomes.get(full, [])
            if dates_list:
                lh = _compute_level_hits_for_dates(level_touches, dates_list)
                if lh:
                    session_level_hits[status] = lh
        level_hits_global[target_session] = session_level_hits

        # ── Base rates ──
        total_global = sum(len(d) for d in global_outcomes.values())
        br = {}
        for status in ALL_SHORT:
            full = _SHORT_TO_FULL.get(status, status)
            count = len(global_outcomes.get(full, []))
            if count > 0:
                br[status] = round(count / total_global, 3)
        base_rates[target_session] = br

        print(f"    {len(table)} context keys, {sum(e['samples'] for e in table.values())} total samples")

    return {"tables": tables, "level_hits": level_hits_global, "base_rates": base_rates}


def save(result: dict, ticker: str = "NQ1"):
    """Save lookup tables to JSON file in data/derived/."""
    _DERIVED.mkdir(parents=True, exist_ok=True)
    output_path = _DERIVED / f"{ticker}_profiler_lookup.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    size_kb = output_path.stat().st_size / 1024
    tables = result.get("tables", {})
    total_keys = sum(len(t) for t in tables.values())
    print(f"\nSaved {total_keys} context keys to {output_path} ({size_kb:.0f} KB)")
    print(f"  tables: {sum(len(t) for t in tables.values())} context entries")
    print(f"  level_hits: {sum(len(lh) for lh in result.get('level_hits', {}).values())} outcome entries")
    print(f"  base_rates: {sum(len(br) for br in result.get('base_rates', {}).values())} entries")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate profiler lookup tables")
    parser.add_argument("--ticker", default="NQ1", help="Ticker symbol")
    args = parser.parse_args()

    result = generate(args.ticker)
    if result:
        save(result, args.ticker)
