"""The Strat Strategy Engine conforming to the repository's strategy standards.

Generates actionable Strat signals for NQ / ES:
  - 2-1-2 Continuations & Reversals
  - 2-2 Reversals
  - 3-1-2 Broadening breakouts
  - FTFC directional validation
"""

from __future__ import annotations

from datetime import time
from typing import Any, Dict, Optional
import numpy as np
import pandas as pd

from scripts.libs_py.the_strat.taxonomy import classify_bars_df
from scripts.libs_py.the_strat.combos import StratComboDetector, ComboType, TradeDirection


class TheStratStrategy:
    """Vectorized and event-driven Strat trade hunter."""

    OUTPUT_COLUMNS = [
        "signal_time",
        "direction",
        "entry_price",
        "stop_price",
        "target1_price",
        "target2_price",
        "model_name",
        "risk_pts",
        "reward_pts",
        "pattern",
    ]

    def __init__(self, ticker: str = "NQ"):
        self.ticker = ticker
        self.strategy_name = "The Strat"
        self.detector = StratComboDetector(tick_size=0.25)

    def hunt(self, data: pd.DataFrame, params: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
        """Scan DataFrame and generate structured signals compatible with simulate_trades."""
        p = params or {}
        df = data.copy()

        if "close" not in df.columns or df.empty:
            return pd.DataFrame(columns=self.OUTPUT_COLUMNS)

        min_rr = float(p.get("min_rr_ratio", 1.0))
        earliest = p.get("earliest_entry", time(9, 30))
        if isinstance(earliest, str):
            h, m = map(int, earliest.split(":"))
            earliest = time(h, m)

        latest = p.get("latest_entry", time(15, 30))
        if isinstance(latest, str):
            h, m = map(int, latest.split(":"))
            latest = time(h, m)

        setups = self.detector.scan_dataframe(df, min_rr_ratio=min_rr)

        rows = []
        for s in setups:
            ts = s.timestamp
            if hasattr(ts, "time"):
                t = ts.time()
                if t < earliest or t > latest:
                    continue

            rows.append({
                "signal_time": ts,
                "direction": 1 if s.direction == TradeDirection.LONG else -1,
                "entry_price": s.entry_trigger_price,
                "stop_price": s.stop_loss_price,
                "target1_price": s.magnitude_1_target,
                "target2_price": s.magnitude_2_target,
                "model_name": s.combo_type.value,
                "risk_pts": s.risk_points,
                "reward_pts": s.reward_points_mag1,
                "pattern": s.pattern_string,
            })

        if not rows:
            return pd.DataFrame(columns=self.OUTPUT_COLUMNS)

        sig_df = pd.DataFrame(rows)
        return sig_df
