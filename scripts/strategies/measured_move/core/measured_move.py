"""
Measured Move Trend Strategy ("Little RZY") — Marci-inspired trendline-structure
trend-continuation strategy. SEPARATE from BB mean reversion (docs/architecture/
BB_EXPERIMENTS.md retired that family); this is a challenger for the TREND seat
in the R01/E31 portfolio, competing with Supertrend (nt_elixir_bandits lineage).

Wraps the generic engine scripts/libs_py/price_action/trendline_structure.py —
deterministic pivot-anchored trendlines, vertical 1:1 measured projection,
structure-ordinal tagging (1st/2nd vs later "Little RZY"), optional BB-context
(Marci's stretch filter) for the E34c arm.

ADR-017 interface: hunt(data, params) + get_param_grid() (Optuna).
ADR-020: positions must exit by 16:00 ET intraday.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

_current = Path(__file__).resolve()
for _p in _current.parents:
    if _p.name == "scripts":
        sys.path.insert(0, str(_p.parent))
        break

from scripts.libs_py.price_action.trendline_structure import (  # noqa: E402
    StructureSignal,
    TrendlineStructureParams,
    scan_trendline_structures,
)


class MeasuredMoveStrategy:
    """
    Trend-continuation via pivot-anchored trendline break with measured projection.

    Entry  : price touches the pullback trendline, then CLOSES back through it
             (rejection) in trend direction, with a directional close-vs-close bar.
    Stop   : beyond the structure extreme (pullback swing high/low) + buffer * ATR.
    Targets: TP1 = 1x measured projection from the structure extreme;
             TP2 = 2x (second measured leg) — fed to the 2-leg BacktestEngine.
    Gates  : DI directional-dominance trend gate; fixed risk bps bracket
             (AGENTS.md universal statistics standard, 2-15 bps).
    """

    def __init__(self, ticker: str = "ES", params: Optional[Dict[str, Any]] = None):
        self.ticker = ticker
        self.params = params or {}
        self.output_cols = ["signal_time", "direction", "entry_price", "stop_price", "target1_price"]

    def _engine_params(self, p: Dict[str, Any]) -> TrendlineStructureParams:
        return TrendlineStructureParams(
            pivot_lookback=int(p.get("pivot_lookback", 3)),
            touch_buf_atr=float(p.get("touch_buf_atr", 0.10)),
            stop_buf_atr=float(p.get("stop_buf_atr", 0.25)),
            invalid_buf_atr=float(p.get("invalid_buf_atr", 0.10)),
            max_age_bars=int(p.get("max_age_bars", 60)),
            proj_mult=float(p.get("proj_mult", 1.0)),
            proj_min_atr=float(p.get("proj_min_atr", 0.5)),
            min_risk_bps=float(p.get("min_risk_bps", 2.0)),
            max_risk_bps=float(p.get("max_risk_bps", 15.0)),
            atr_period=int(p.get("atr_period", 14)),
            di_period=int(p.get("di_period", 14)),
            di_edge=float(p.get("di_edge", 0.0)),
            use_trend_gate=bool(p.get("use_trend_gate", True)),
            require_directional_bar=bool(p.get("require_directional_bar", True)),
        )

    def hunt(self, data: pd.DataFrame, params: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
        """ADR-017 signal hunter. `data`: OHLCV DataFrame (any bar size).

        Returns a signal DataFrame with columns:
            signal_time, direction, entry_price, stop_price, target1_price,
            target2_price, ordinal, dist_atr, line_slope
        """
        p = {**(self.params or {}), **(params or {})}
        sigs = scan_trendline_structures(data, self._engine_params(p))
        if not sigs:
            return pd.DataFrame(columns=[
                "signal_time", "direction", "entry_price", "stop_price",
                "target1_price", "target2_price", "ordinal", "dist_atr", "line_slope",
            ])
        return pd.DataFrame([
            {
                "signal_time": s.entry_time,
                "direction": s.direction,
                "entry_price": s.entry_price,
                "stop_price": s.stop_loss,
                "target1_price": s.tp1_price,
                "target2_price": s.tp2_price,
                "ordinal": s.ordinal,
                "dist_atr": s.dist_atr,
                "line_slope": s.line_slope,
            }
            for s in sigs
        ])

    @staticmethod
    def get_param_grid() -> Dict[str, Any]:
        """Optuna search space."""
        return {
            "pivot_lookback": ("int", 2, 6),
            "touch_buf_atr": ("float", 0.0, 0.5),
            "stop_buf_atr": ("float", 0.0, 1.0),
            "invalid_buf_atr": ("float", 0.0, 0.5),
            "proj_mult": ("float", 0.5, 2.0),
            "di_edge": ("float", -5.0, 10.0),
            "max_age_bars": ("int", 20, 120),
        }


def bb_context_flags(df: pd.DataFrame, bb_period: int = 20, n_std: float = 2.0,
                     extreme_pct: float = 0.85) -> pd.DataFrame:
    """E34c helper: Bollinger %B context for conditioning signals.

    Adds bb_pct_b, pb_extreme_flag columns (zero-lookahead). The extreme
    threshold is the trailing p{extreme_pct*100}/p{(1-extreme_pct)*100} of %B
    over the preceding bars (E16-percentile convention; ES 5m %B rarely prints
    fixed 0.85/0.15, so a session-relative threshold is the honest cut).
    """
    out = df.copy()
    roll = out["close"].rolling(bb_period)
    mid = roll.mean()
    std = roll.std(ddof=1).clip(lower=1e-12)
    upper = mid + n_std * std
    lower = mid - n_std * std
    width = upper - lower
    pb = (out["close"] - lower) / width.replace(0, np.nan)
    out["bb_pct_b"] = pb
    out["bb_bandwidth"] = width / mid.replace(0, np.nan)
    lo_pct = 1.0 - extreme_pct
    out["pb_hi_thr"] = pb.shift(1).rolling(100, min_periods=20).quantile(extreme_pct)
    out["pb_lo_thr"] = pb.shift(1).rolling(100, min_periods=20).quantile(lo_pct)
    return out