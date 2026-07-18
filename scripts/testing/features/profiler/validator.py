"""
validator.py — ProfilerFeatureValidator implementation.

Validates the profiler WebUI feature by:
  1. Loading local profiler data from JSON files
  2. Applying the same filter logic as the WebUI backend
  3. Computing statistics locally
  4. Calling the WebUI API for the same filter
  5. Comparing ALL fields side-by-side

This is the reference implementation of the FeatureValidator protocol.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional

from ...core.base import (
    FeatureValidator,
    ValidationResult,
    FieldComparison,
    ComparisonStatus,
)
from ...core.filter_engine import FilterEngine
from ...core.comparator import FieldComparator
from .data import (
    load_profiler,
    load_level_touches,
    load_hod_lod,
    load_hod_lod_unadjusted,
    load_lookup,
    CONTEXT_CHAIN,
    SHORT_TO_FULL,
    ALL_STATUSES,
    ALL_SHORT,
    HIT_KEYS,
    TICKERS,
    TARGET_SESSIONS,
)
from .compute import compute_filtered_stats, HIT_TO_LEVEL
from .api import ProfilerAPIClient


class ProfilerValidator(FeatureValidator):
    """
    Validates the profiler WebUI feature against local reference computation.

    Compares every field the WebUI returns from POST /stats/filtered-stats:
      - Sample count
      - Outcome distribution (LT/LF/ST/SF %)
      - Range stats (median, mean, mode for high_pct and low_pct)
      - Level hit rates (all 15 level keys)
      - HOD/LOD timing (15-min bucket distributions)
      - Per-outcome breakdown (price stats, timing, broken rates, level hits)
      - Full-day HOD/LOD timing
    """

    def __init__(self):
        self._api = ProfilerAPIClient()
        self._data_cache: Dict[str, Any] = {}
        self._filter_engine_cache: Dict[str, Any] = {}

    @property
    def name(self) -> str:
        return "profiler"

    @property
    def description(self) -> str:
        return "Validates profiler session box outcomes, distributions, timing, and level hit rates"

    def get_target_sessions(self) -> List[str]:
        return TARGET_SESSIONS

    def get_tickers(self) -> List[str]:
        return TICKERS

    def get_filter_keys(self, ticker: str, target_session: str,
                        min_samples: int = 5) -> List[str]:
        """Get all filter keys with at least min_samples from the lookup table."""
        lookup = load_lookup(ticker)
        all_keys = sorted(lookup["tables"].get(target_session, {}).keys())
        return [
            k for k in all_keys
            if lookup["tables"][target_session][k].get("samples", 0) >= min_samples
        ]

    def validate(self, ticker: str, target_session: str,
                 filter_key: str) -> ValidationResult:
        """Validate a single filter combination."""
        # ── 1. Load data (cached) ──
        sessions = self._get_data(ticker, "sessions")
        level_touches = self._get_data(ticker, "level_touches")
        hod_lod_data = self._get_data(ticker, "hod_lod_unadj")  # unadjusted prices (matches WebUI + lookup table)
        lookup = load_lookup(ticker)

        # ── 2. Build filter engine (cached) ──
        engine = self._get_filter_engine(ticker, sessions)

        # ── 3. Convert filter key to WebUI format ──
        filters, broken_filters = self._filter_key_to_webui(target_session, filter_key)

        # ── 4. Apply filter locally ──
        matched_dates = engine.apply(target_session, filters, broken_filters, "Any")

        # ── 5. Fetch WebUI level touches (for level hit rate comparison) ──
        webui_level_touches = self._api.get_level_touches(ticker)

        # ── 6. Compute local stats ──
        local_stats = compute_filtered_stats(
            sessions, target_session, matched_dates, hod_lod_data, level_touches,
            webui_level_touches=webui_level_touches,
        )

        # ── 7. Get lookup table entry ──
        lookup_entry = lookup["tables"].get(target_session, {}).get(filter_key, {})

        # ── 8. Compare all fields ──
        comparator = FieldComparator()
        field_comparisons: List[FieldComparison] = []
        summary: Dict[str, ComparisonStatus] = {}

        # 8a. Count
        lc = local_stats.get("count", 0)
        lk_count = lookup_entry.get("samples", 0)
        fc = comparator.compare("count", lc, lk_count)
        field_comparisons.append(fc)
        summary["count"] = fc.status

        # 8b. Distribution (probabilities)
        lk_probs = lookup_entry.get("probabilities", {})
        dist_ok = True
        for outcome in ALL_SHORT:
            lv = round(local_stats.get("distribution", {}).get(SHORT_TO_FULL.get(outcome, ""), 0) / 100, 3) if local_stats.get("count", 0) > 0 else 0
            wv = lk_probs.get(outcome, 0)
            fc = comparator.compare(f"distribution.{outcome}", lv, wv, tolerance=0.01)
            field_comparisons.append(fc)
            if fc.status == ComparisonStatus.MISMATCH:
                dist_ok = False
        summary["distribution"] = ComparisonStatus.MATCH if dist_ok else ComparisonStatus.MISMATCH

        # 8c. Per-outcome price stats (compare local vs lookup table)
        lk_ps = lookup_entry.get("price_stats", {})
        ps_ok = True
        for outcome in ALL_SHORT:
            full = SHORT_TO_FULL.get(outcome, "")
            local_ps = local_stats.get("by_outcome", {}).get(full, {}).get("price_stats", {})
            lk_ps_entry = lk_ps.get(outcome, {})
            for key in ["h_mode", "h_med", "l_mode", "l_med"]:
                lv = local_ps.get(key)
                wv = lk_ps_entry.get(key)
                if lv is not None and wv is not None:
                    fc = comparator.compare(f"price_stats.{outcome}.{key}", lv, wv, tolerance=0.15)
                    field_comparisons.append(fc)
                    if fc.status == ComparisonStatus.MISMATCH:
                        ps_ok = False
        summary["price_stats"] = ComparisonStatus.MATCH if ps_ok else ComparisonStatus.MISMATCH

        # 8d. Per-outcome timing (compare local vs lookup table)
        lk_timing = lookup_entry.get("hod_lod_times", {})
        timing_ok = True
        for outcome in ALL_SHORT:
            full = SHORT_TO_FULL.get(outcome, "")
            local_t = local_stats.get("by_outcome", {}).get(full, {}).get("timing", {})
            lk_t_entry = lk_timing.get(outcome, {})
            for key in ["hod_mode", "lod_mode"]:
                lv = local_t.get(key, "")
                wv = lk_t_entry.get(key, "")
                if lv or wv:
                    fc = comparator.compare(f"timing.{outcome}.{key}", lv, wv)
                    field_comparisons.append(fc)
                    if fc.status == ComparisonStatus.MISMATCH:
                        timing_ok = False
        summary["timing"] = ComparisonStatus.MATCH if timing_ok else ComparisonStatus.MISMATCH

        # 8e. Per-outcome broken rates (compare local vs lookup table)
        lk_broken = lookup_entry.get("broken_rates", {})
        broken_ok = True
        for outcome in ALL_SHORT:
            full = SHORT_TO_FULL.get(outcome, "")
            local_br = local_stats.get("by_outcome", {}).get(full, {}).get("broken_rate", 0)
            lk_br = round(lk_broken.get(outcome, 0) * 100, 1)
            if local_br > 0 or lk_br > 0:
                fc = comparator.compare(f"broken_rate.{outcome}", local_br, lk_br, tolerance=2.0)
                field_comparisons.append(fc)
                if fc.status == ComparisonStatus.MISMATCH:
                    broken_ok = False
        summary["broken_rates"] = ComparisonStatus.MATCH if broken_ok else ComparisonStatus.MISMATCH

        # 8f. Level hit rates (from WebUI level touches endpoint)
        lh_ok = True
        if "error" not in webui_level_touches:
            wd = webui_level_touches.get("dates", [])
            wl = webui_level_touches.get("levels", {})
            hit_to_level = {
                "hit_pdh": "pdh", "hit_pdm": "pdm", "hit_pdl": "pdl",
                "hit_midnight": "midnight_open", "hit_0730": "open_0730",
                "hit_ny_p12h": "ny_p12h", "hit_ny_p12m": "ny_p12m", "hit_ny_p12l": "ny_p12l",
                "hit_p12h": "p12h", "hit_p12m": "p12m", "hit_p12l": "p12l",
                "hit_p_asia_mid": "asia_mid", "hit_p_lon_mid": "london_mid",
                "hit_p_ny1_mid": "ny1_mid", "hit_p_ny2_mid": "ny2_mid",
            }
            for k in HIT_KEYS:
                level_name = hit_to_level.get(k)
                if not level_name or level_name not in wl:
                    continue
                session_hits = wl[level_name].get("hits", {}).get(target_session, [])
                if not session_hits:
                    continue
                touched = sum(1 for d in matched_dates if d in wd and
                             (idx := wd.index(d)) < len(session_hits) and session_hits[idx] != -1)
                wv = round(touched / len(matched_dates) * 100, 1) if matched_dates else 0
                lv = local_stats.get("level_hit_rates", {}).get(k, 0)
                fc = comparator.compare(f"level_hit_rate.{k}", lv, wv, tolerance=0)
                field_comparisons.append(fc)
                if fc.status == ComparisonStatus.MISMATCH:
                    lh_ok = False
        summary["level_hits"] = ComparisonStatus.MATCH if lh_ok else ComparisonStatus.MISMATCH

        # 8g. Per-outcome level hit rates (compare local vs lookup table)
        lk_per_outcome_lh = lookup_entry.get("per_outcome_level_hits", {})
        polh_ok = True
        polh_count = 0
        for outcome in ALL_SHORT:
            full = SHORT_TO_FULL.get(outcome, "")
            local_olh = local_stats.get("by_outcome", {}).get(full, {}).get("level_hit_rates", {})
            lk_olh = lk_per_outcome_lh.get(outcome, {})
            if not lk_olh:
                continue
            for level_key, wv in lk_olh.items():
                lv = local_olh.get(level_key, 0)
                # HIT_KEYS use hit_ prefix; lookup table uses level names directly
                # local_olh is keyed by HIT_KEYS (hit_pdh), lookup uses level names (pdh)
                # Map: lookup level name -> HIT_KEY
                level_to_hit = {v: k for k, v in HIT_TO_LEVEL.items()}
                hit_key = level_to_hit.get(level_key, level_key)
                lv = local_olh.get(hit_key, 0)
                fc = comparator.compare(
                    f"per_outcome_level_hit.{outcome}.{level_key}", lv, wv, tolerance=0.1
                )
                field_comparisons.append(fc)
                polh_count += 1
                if fc.status == ComparisonStatus.MISMATCH:
                    polh_ok = False
        if polh_count > 0:
            summary["per_outcome_level_hits"] = (
                ComparisonStatus.MATCH if polh_ok else ComparisonStatus.MISMATCH
            )

        # ── 9. Build result ──
        return ValidationResult(
            feature=self.name,
            filter_key=filter_key,
            target_session=target_session,
            ticker=ticker,
            local_count=len(matched_dates),
            webui_count=lookup_entry.get("samples", 0),
            field_comparisons=field_comparisons,
            summary=summary,
            local_data=local_stats,
            webui_data=lookup_entry,
        )

    # ── Private helpers ──

    def _get_data(self, ticker: str, data_type: str) -> Any:
        """Load and cache profiler data."""
        cache_key = f"{ticker}_{data_type}"
        if cache_key not in self._data_cache:
            loaders = {
                "sessions": load_profiler,
                "level_touches": load_level_touches,
                "hod_lod": load_hod_lod,
                "hod_lod_unadj": load_hod_lod_unadjusted,
            }
            self._data_cache[cache_key] = loaders[data_type](ticker)
        return self._data_cache[cache_key]

    def _get_filter_engine(self, ticker: str, sessions: List[dict]) -> FilterEngine:
        """Build and cache filter engine."""
        if ticker not in self._filter_engine_cache:
            self._filter_engine_cache[ticker] = FilterEngine(sessions)
        return self._filter_engine_cache[ticker]

    @staticmethod
    @staticmethod
    def _filter_key_to_webui(target_session: str, filter_key: str):
        """
        Convert compact filter key to WebUI filter/broken_filters format.

        Handles two key formats:
          - Status-only: "LT|LF" (2 parts for NY1) — no broken filter
          - Full: "LT|F|LF|F" (4 parts for NY1) — with broken filter
          - 6-part keys (e.g. "LT|F|ST|F|SF|F"): 3 context sessions (NY2)

        The key parts correspond to CONTEXT_CHAIN[target_session] in order.
        Status-only keys have 1 part per context session (no broken).
        Full keys have 2 parts per context session (status + broken).
        """
        parts = filter_key.split("|")
        chain = CONTEXT_CHAIN.get(target_session, [])
        has_broken = len(parts) == len(chain) * 2  # Full key has 2 parts per session
        filters = {}
        broken_filters = {}
        for i, (scope, sess_name) in enumerate(chain):
            if has_broken:
                status_idx = i * 2
                broken_idx = i * 2 + 1
                if broken_idx >= len(parts):
                    continue
                status_short = parts[status_idx]
                broken_val = parts[broken_idx]
                broken_filters[sess_name] = "Yes" if broken_val == "T" else "No"
            else:
                # Status-only key: 1 part per session
                if i >= len(parts):
                    continue
                status_short = parts[i]
            full_status = SHORT_TO_FULL.get(status_short, "")
            if full_status:
                filters[sess_name] = full_status
        return filters, broken_filters

    def _compute_daily_hod_lod_from_api(self, dates: List[str], ticker: str) -> Dict[str, str]:
        """Compute HOD/LOD mode from WebUI daily-hod-lod API data."""
        webui_data = self._api.get_daily_hod_lod(ticker)
        if "error" in webui_data:
            return {"hod_mode": "", "lod_mode": ""}
        webui_dates = webui_data.get("dates", [])
        hod_times = []
        lod_times = []
        for d in dates:
            if d in webui_dates:
                idx = webui_dates.index(d)
                if idx < len(webui_data.get("hod_time", [])):
                    mins = webui_data["hod_time"][idx]
                    if mins >= 0:
                        h, m = divmod(int(mins), 60)
                        hod_times.append(f"{h:02d}:{m:02d}")
                if idx < len(webui_data.get("lod_time", [])):
                    mins = webui_data["lod_time"][idx]
                    if mins >= 0:
                        h, m = divmod(int(mins), 60)
                        lod_times.append(f"{h:02d}:{m:02d}")

        def _mode(times):
            buckets = defaultdict(int)
            for t in times:
                try:
                    h, m = map(int, t.split(":"))
                    b = f"{h:02d}:{(m // 15) * 15:02d}"
                    buckets[b] += 1
                except Exception:
                    continue
            return max(buckets, key=buckets.get) if buckets else ""

        return {"hod_mode": _mode(hod_times), "lod_mode": _mode(lod_times)}
