"""The Strat Strategy Hunter (Pillar 2).

Thin adapter over the canonical library engine — all Strat logic lives in:
  scripts/libs_py/the_strat/signals.py  (StratSignalEngine: per-timeframe
    classify + scan + FTFC attach + session gate + measured targets)
  scripts/libs_py/the_strat/config.py   (strat_config.json — shared with NT8)
  scripts/strategies/the_strat/strat_config.json (single source of truth)

This class only: loads config, runs the engine, returns the canonical
Signal List DataFrame (HARMONISED_TRADING_ARCHITECTURE.md Pillar 2 contract).
No PnL, no loops over exits — execution lives in Pillar 3.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import pandas as pd

from scripts.libs_py.the_strat.config import StratConfig, load_strat_config
from scripts.libs_py.the_strat.signals import OUTPUT_COLUMNS, StratSignalEngine


class TheStratStrategy:
    """Strat trade hunter — .hunt(data, params) -> Signal List DF."""

    OUTPUT_COLUMNS = OUTPUT_COLUMNS

    def __init__(self, ticker: str = "NQ", config: StratConfig | None = None):
        self.ticker = ticker
        self.strategy_name = "The Strat"
        self.config = config or load_strat_config()
        base = ticker.upper().rstrip("1234567890!")
        spec = self.config.instrument(base)
        self.engine = StratSignalEngine(
            config=self.config, tick_size=spec.tick_size
        )

    def hunt(
        self, data: pd.DataFrame, params: Optional[Dict[str, Any]] = None
    ) -> pd.DataFrame:
        """Scan DataFrame and generate canonical Strat signals.

        params overrides (all optional): timeframe, allowed_setups,
        min_rr_ratio, min_target_points, max_risk_points, use_ftfc_filter,
        min_ftfc_score, ftfc_timeframes, earliest_entry, latest_entry,
        flatten_by, use_killzones, confirm_next_bar, tick_size.
        """
        return self.engine.generate(data, params)
