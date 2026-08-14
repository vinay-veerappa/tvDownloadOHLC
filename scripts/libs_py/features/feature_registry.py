"""
Central feature registry — ADR-009 compliant.

Strategies request features by name.  The registry ensures each feature
group is computed exactly once per DataFrame and dispatches independent
groups in parallel via ThreadPoolExecutor (ADR-009 rule 6).

Usage:
    from scripts.libs_py.features.feature_registry import FeatureRegistry
    from scripts.trading_framework.config.config_loader import load_config

    config = load_config()
    registry = FeatureRegistry(config)
    df = registry.ensure_features(df, ["vwap", "ib_high", "chop_score"])
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Feature dependency graph
# ---------------------------------------------------------------------------
# Maps each feature-group name → list of features it depends on.
# ensure_features() uses this to topologically resolve order automatically.

_DEPENDENCIES: dict[str, list[str]] = {
    "atr":              [],
    "vwap":             ["atr"],
    "ib":               [],           # only needs trading_date + is_rth
    "orb_bias":         [],           # 09:30 1m opening range breakout bias
    "quarterly_cycles": [],           # Pack Quarterly Theory & 90-min sessions
    "internals":        [],
    "chop":             ["internals", "vwap"],
    "ema":              [],
    "bollinger":        ["atr"],
    "keltner":          ["atr"],
    "acceptance":       ["vwap", "ib"],
    "auction":          [],
    "context":          [],
    "session":          [],
}

# ---------------------------------------------------------------------------
# Feature group → output column names
# ---------------------------------------------------------------------------
# Used by ensure_features() to detect whether a group has already been run.

_GROUP_SENTINEL: dict[str, str] = {
    "atr":              "atr_14",
    "vwap":             "vwap",
    "ib":               "ib_high",
    "orb_bias":         "orb_1m_bias",
    "quarterly_cycles": "quarter_90m",
    "internals":        "tick_persistence",
    "chop":             "chop_score",
    "ema":              "ema_9",
    "bollinger":        "bb_mid",
    "keltner":          "kc_mid",
    "acceptance":       "level_state",
    "auction":          "fast_move_detected",
    "context":          "vix_regime",
    "session":          "session_block",
}

# Convenience map: individual feature name → group name
_FEATURE_TO_GROUP: dict[str, str] = {
    # ATR
    "atr_14":               "atr",
    "atr_5m_14":            "atr",
    # VWAP family
    "vwap":                 "vwap",
    "vwap_distance":        "vwap",
    "vwap_distance_atr":    "vwap",
    "vwap_slope":           "vwap",
    "vwap_cross_count":     "vwap",
    "above_vwap":           "vwap",
    "vwap_std_1":           "vwap",
    "vwap_std_neg1":        "vwap",
    # IB family
    "ib_high":              "ib",
    "ib_low":               "ib",
    "ib_mid":               "ib",
    "ib_width":             "ib",
    "ib_width_pctile_20d":  "ib",
    "ib_width_pctile_50d":  "ib",
    "ib_bias":              "ib",
    "ib_ext_up_50":         "ib",
    "ib_ext_up_100":        "ib",
    "ib_ext_dn_50":         "ib",
    "ib_ext_dn_100":        "ib",
    "ib_formed":            "ib",
    "price_vs_ib":          "ib",
    # ORB Bias family
    "orb_1m_high":          "orb_bias",
    "orb_1m_low":           "orb_bias",
    "orb_1m_width":         "orb_bias",
    "orb_1m_confirmed_up":  "orb_bias",
    "orb_1m_confirmed_dn":  "orb_bias",
    "orb_1m_bias":          "orb_bias",
    "orb_1m_formed":        "orb_bias",
    # Quarterly Cycles family
    "quarter_90m":          "quarterly_cycles",
    "is_quarterly_expansion_window": "quarterly_cycles",
    "is_quarterly_consolidation_window": "quarterly_cycles",
    "hour_quarter":         "quarterly_cycles",
    "is_05_box":            "quarterly_cycles",
    "hour_box05_high":      "quarterly_cycles",
    "hour_box05_low":       "quarterly_cycles",
    "q1_sweep_retreat":     "quarterly_cycles",
    # Internals family
    "vold":                 "internals",
    "tick_abs":             "internals",
    "tick_persistence":     "internals",
    "tick_zero_cross":      "internals",
    "vold_slope":           "internals",
    "trin_avg":             "internals",
    "trin_in_chop_band":    "internals",
    # Chop family
    "chop_tick_score":      "chop",
    "chop_vold_score":      "chop",
    "chop_trin_score":      "chop",
    "chop_score":           "chop",
    "chop_vwap_flag":       "chop",
    "chop_regime":          "chop",
    # EMA family
    "ema_9":                "ema",
    "ema_20":               "ema",
    "ema_50":               "ema",
    "ema_200":              "ema",
    # Bollinger
    "bb_upper":             "bollinger",
    "bb_lower":             "bollinger",
    "bb_mid":               "bollinger",
    "bb_pct_b":             "bollinger",
    "bb_bandwidth":         "bollinger",
    # Keltner
    "kc_upper":             "keltner",
    "kc_lower":             "keltner",
    "kc_mid":               "keltner",
    # Acceptance / Rejection
    "level_state":          "acceptance",
    # Auction
    "roc_10bar":            "auction",
    "fast_move_detected":   "auction",
    "fast_move_origin":     "auction",
    "fast_move_direction":  "auction",
    "single_print_level":   "auction",
    # Context (externally added by DataLoader)
    "vix_regime":           "context",
    "vix_daily":            "context",
    "vix_close":            "context",
    "vvix_level":           "context",
    "vvix_regime":          "context",
    # Session (externally added by DataLoader)
    "session_block":        "session",
    "context_session_block":"session",
}


class FeatureRegistry:
    """
    Central orchestrator for feature computation.

    Ensures each feature group is computed exactly once per DataFrame,
    resolves dependencies automatically, and defers imports to first use.

    Attributes:
        config:     AppConfig — passed through to every compute_* function.
        _computed:  set[str]  — tracks which groups have been applied.
    """

    def __init__(self, config=None):
        self.config = config
        self._computed: set[str] = set()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ensure_features(
        self, df: pd.DataFrame, feature_names: list[str]
    ) -> pd.DataFrame:
        """
        Compute all requested features (and their dependencies) if not already
        present.  Idempotent — calling twice is safe.

        Args:
            df:            Enriched 1-minute DataFrame from DataLoader.load_enriched().
            feature_names: List of individual feature names OR group names.

        Returns:
            df with all requested features as columns.
        """
        # Resolve dependency-ordered list of groups
        groups = self._resolve_groups(feature_names)
        # Dispatch in waves: each wave contains groups whose deps are all done
        # NOTE: functions that reassign df (like IB join) run sequentially
        # so the registry always holds the current reference.
        df = self._dispatch_waves(df, groups)
        return df

    def register(self, feature_name: str, compute_fn: Callable) -> None:
        """
        Register a custom feature computation function.

        compute_fn signature: (df: pd.DataFrame, config: AppConfig) -> pd.DataFrame
        The function should add one or more columns to df and return it.
        """
        # Map the custom feature to a synthetic group name
        group = f"custom:{feature_name}"
        _FEATURE_TO_GROUP[feature_name] = group
        _GROUP_SENTINEL[group] = feature_name
        _DEPENDENCIES[group] = []
        self._custom_computers: dict[str, Callable] = getattr(
            self, "_custom_computers", {}
        )
        self._custom_computers[group] = compute_fn

    def get_feature_list(self) -> list[str]:
        """Return sorted list of all known individual feature names."""
        return sorted(_FEATURE_TO_GROUP.keys())

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _dispatch_waves(self, df: pd.DataFrame, ordered_groups: list[str]) -> pd.DataFrame:
        """
        Execute feature groups in parallel waves (ADR-009 rule 6).

        Returns the (possibly new) df reference — needed for groups like IB
        that do a .join() and return a new DataFrame object.

        Groups whose compute_fn returns a new df are run sequentially.
        Groups that only add columns in-place can run in parallel.
        """
        # Groups known to return a new df (due to join/concat)
        _SEQUENTIAL_GROUPS = {"ib", "acceptance"}

        done: set[str] = set()
        waves: list[list[str]] = []
        current_wave: list[str] = []

        for grp in ordered_groups:
            deps = set(_DEPENDENCIES.get(grp, []))
            if deps & set(current_wave):
                waves.append(current_wave)
                done.update(current_wave)
                current_wave = [grp]
            else:
                current_wave.append(grp)

        if current_wave:
            waves.append(current_wave)

        for wave in waves:
            # Separate sequential-only and parallel-safe groups within this wave
            seq_groups  = [g for g in wave if g in _SEQUENTIAL_GROUPS]
            para_groups = [g for g in wave if g not in _SEQUENTIAL_GROUPS]

            # Run parallel-safe groups concurrently
            if para_groups:
                if len(para_groups) == 1:
                    self._compute_group_inplace(df, para_groups[0])
                else:
                    from concurrent.futures import ThreadPoolExecutor, as_completed
                    with ThreadPoolExecutor(max_workers=len(para_groups)) as ex:
                        futures = {ex.submit(self._compute_group_inplace, df, g): g
                                   for g in para_groups}
                        for fut in as_completed(futures):
                            exc = fut.exception()
                            if exc:
                                logger.error("Group '%s' failed: %s", futures[fut], exc)

            # Run sequential groups (may return new df)
            for g in seq_groups:
                df = self._compute_group_returning(df, g)

        return df

    def _resolve_groups(self, feature_names: list[str]) -> list[str]:
        """
        Topological sort of required groups (and their transitive deps).
        """
        required: set[str] = set()
        for name in feature_names:
            # Accept both individual feature names and group names
            group = _FEATURE_TO_GROUP.get(name, name)
            required.add(group)

        # Expand dependencies (BFS)
        frontier = list(required)
        while frontier:
            grp = frontier.pop()
            for dep in _DEPENDENCIES.get(grp, []):
                if dep not in required:
                    required.add(dep)
                    frontier.append(dep)

        # Topological sort (Kahn's algorithm)
        in_degree = {g: 0 for g in required}
        for grp in required:
            for dep in _DEPENDENCIES.get(grp, []):
                if dep in in_degree:
                    in_degree[grp] = in_degree.get(grp, 0) + 1

        # Rebuild properly
        in_degree = {g: 0 for g in required}
        for grp in required:
            for dep in _DEPENDENCIES.get(grp, []):
                if dep in required:
                    in_degree[grp] += 1

        queue = [g for g, d in in_degree.items() if d == 0]
        sorted_groups: list[str] = []
        while queue:
            grp = queue.pop(0)
            sorted_groups.append(grp)
            for candidate in required:
                if grp in _DEPENDENCIES.get(candidate, []):
                    in_degree[candidate] -= 1
                    if in_degree[candidate] == 0:
                        queue.append(candidate)

        return sorted_groups

    def _compute_group_inplace(self, df: pd.DataFrame, group: str) -> None:
        """Run a feature group that modifies df in-place (thread-safe for parallel waves)."""
        if group in self._computed:
            return
        sentinel = _GROUP_SENTINEL.get(group)
        if sentinel and sentinel in df.columns:
            logger.debug("Feature group '%s' already present — skipping", group)
            self._computed.add(group)
            return
        logger.debug("Computing feature group (inplace): %s", group)
        compute_fn = self._get_compute_fn(group)
        if compute_fn is None:
            logger.warning("No compute function found for group '%s'", group)
            return
        compute_fn(df, self.config)
        self._computed.add(group)

    def _compute_group_returning(self, df: pd.DataFrame, group: str) -> pd.DataFrame:
        """Run a feature group that may return a new df (sequential, captures return)."""
        if group in self._computed:
            return df
        sentinel = _GROUP_SENTINEL.get(group)
        if sentinel and sentinel in df.columns:
            logger.debug("Feature group '%s' already present — skipping", group)
            self._computed.add(group)
            return df
        logger.debug("Computing feature group (returning): %s", group)
        compute_fn = self._get_compute_fn(group)
        if compute_fn is None:
            logger.warning("No compute function found for group '%s'", group)
            return df
        result = compute_fn(df, self.config)
        self._computed.add(group)
        return result if result is not None else df

    def _compute_group(self, df: pd.DataFrame, group: str) -> None:
        """Legacy: inplace wrapper (used by older call sites)."""
        self._compute_group_inplace(df, group)

    def _get_compute_fn(self, group: str) -> Callable | None:
        """Lazy-import and return the compute function for a group."""
        # Custom registered functions
        custom = getattr(self, "_custom_computers", {})
        if group in custom:
            return custom[group]

        try:
            if group == "atr":
                from scripts.libs_py.features.atr import compute_atr
                return compute_atr
            if group == "vwap":
                from scripts.libs_py.features.vwap import compute_vwap
                return compute_vwap
            if group == "ib":
                from scripts.libs_py.features.initial_balance import compute_initial_balance
                return compute_initial_balance
            if group == "orb_bias":
                from scripts.libs_py.features.orb_bias import compute_orb_bias
                return compute_orb_bias
            if group == "quarterly_cycles":
                from scripts.libs_py.features.quarterly_cycles import compute_quarterly_cycles
                return compute_quarterly_cycles
            if group == "internals":
                from scripts.libs_py.features.internals import compute_internals_features
                return compute_internals_features
            if group == "chop":
                from scripts.libs_py.features.chop import compute_chop_score
                return compute_chop_score
            if group == "ema":
                from scripts.libs_py.features.ema import compute_ema
                return compute_ema
            if group == "bollinger":
                from scripts.libs_py.features.bollinger import compute_bollinger_bands
                return compute_bollinger_bands
            if group == "keltner":
                from scripts.libs_py.features.keltner import compute_keltner_channels
                return compute_keltner_channels
            if group == "acceptance":
                from scripts.libs_py.features.acceptance_rejection import compute_acceptance_rejection
                return compute_acceptance_rejection
            if group == "auction":
                from scripts.libs_py.features.auction import compute_auction_features
                return compute_auction_features
        except ImportError as e:
            logger.warning("Import failed for group '%s': %s", group, e)
        return None
