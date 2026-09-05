"""Strategy registry for dynamic discovery and lifecycle execution."""

from typing import Any, Callable, Dict

import pandas as pd


import sys
from pathlib import Path

# Add project root to sys.path dynamically
_current_dir = Path(__file__).resolve().parent
while _current_dir.name and _current_dir.name != "scripts":
    _current_dir = _current_dir.parent
if _current_dir.name == "scripts":
    _root_dir = str(_current_dir.parent)
    if _root_dir not in sys.path:
        sys.path.insert(0, _root_dir)

from scripts.strategies.ema_pullback.core.ema_pullback import EMAPullbackStrategy
from scripts.strategies.failed_auction.core.failed_auction import FailedAuctionStrategy
from scripts.strategies.initial_balance.core.initial_balance_pullback import IBPullbackStrategy
from scripts.strategies.reversal.core.box_reversion import BoxReversionStrategy
from scripts.strategies.reversal.core.mean_reversion import MeanReversionStrategy
from scripts.strategies.reversal.core.six_am_reversal import SixAMReversalStrategy
from scripts.strategies.vwap_reclaim.core.vwap_reclaim import VWAPReclaimStrategy
from scripts.strategies.vwap_reclaim.core.vwap_institutional import VWAPInstitutionalStrategy
from scripts.strategies.ifvg_cisd.core.ifvg_cisd_strategy import IFVGCISDStrategy

# ── ICT Suite (Harmonised Pillar-2, ADR-020 compliant) ─────────────────────
from scripts.strategies.ict.strategies import (
    ICTDisplacementStrategy,
    ICTLiquiditySweepStrategy,
    ICTFVGRejectionStrategy,
    ICTFVGCISDRejectionStrategy,
    ICTNYSessionStrategy,
    ICTAsiaVolatilityStrategy,
)


class HunterStrategyAdapter:
    """Adapter to expose hunt()-style strategies as lifecycle-compatible strategies."""

    def __init__(self, strategy: Any, strategy_name: str):
        self._strategy = strategy
        self.strategy_name = strategy_name

    def generate_signals(self, data: pd.DataFrame, config: Dict[str, Any]) -> pd.DataFrame:
        return self._strategy.hunt(data, params=config)

    def get_param_grid(self) -> Dict[str, Any]:
        return self._strategy.get_param_grid()

    @property
    def last_decisions(self):
        """The wrapped hunter's decision log, or None if it is not instrumented.

        Forwarded HERE rather than read off `._strategy` by the caller, because
        every hunter reaches the engine through this adapter -- so one property
        instruments all of them, and a reporting layer that reached through the
        wrapper would work for exactly as long as the wrapper stayed one layer
        deep. `None` means NOT INSTRUMENTED and is deliberately distinct from an
        empty frame, which would mean "instrumented and nothing triggered".
        """
        return getattr(self._strategy, "last_decisions", None)


STRATEGY_FACTORY_REGISTRY: Dict[str, Callable[[str], Any]] = {
    # ── Existing strategies ─────────────────────────────────────────────────
    "ib_pullback":        lambda ticker: HunterStrategyAdapter(IBPullbackStrategy(ticker=ticker),        "IB Pullback"),
    "box_reversion":      lambda ticker: HunterStrategyAdapter(BoxReversionStrategy(ticker=ticker),      "Box Reversion"),
    "mean_reversion":     lambda ticker: HunterStrategyAdapter(MeanReversionStrategy(ticker=ticker),     "Mean Reversion"),
    "ema_pullback":       lambda ticker: HunterStrategyAdapter(EMAPullbackStrategy(ticker=ticker),       "EMA Pullback"),
    "vwap_reclaim":       lambda ticker: HunterStrategyAdapter(VWAPReclaimStrategy(ticker=ticker),       "VWAP Reclaim"),
    "vwap_institutional": lambda ticker: HunterStrategyAdapter(VWAPInstitutionalStrategy(ticker=ticker), "Institutional VWAP"),
    "ifvg_cisd":          lambda ticker: HunterStrategyAdapter(IFVGCISDStrategy(ticker=ticker),          "5m IFVG CISD Distribution"),
    "failed_auction":     lambda ticker: HunterStrategyAdapter(FailedAuctionStrategy(ticker=ticker),     "Failed Auction"),
    "six_am_reversal":    lambda ticker: HunterStrategyAdapter(SixAMReversalStrategy(ticker=ticker),    "6 AM Reversal"),
    # ── ICT Suite (Harmonised, ADR-020) ────────────────────────────────────
    "ict_displacement":    lambda ticker: HunterStrategyAdapter(ICTDisplacementStrategy(ticker=ticker),    "ICT Displacement (MSS)"),
    "ict_liquidity_sweep": lambda ticker: HunterStrategyAdapter(ICTLiquiditySweepStrategy(ticker=ticker), "ICT Liquidity Sweep"),
    "ict_fvg_rejection":   lambda ticker: HunterStrategyAdapter(ICTFVGRejectionStrategy(ticker=ticker),   "ICT FVG Rejection"),
    "ict_fvg_cisd_rejection": lambda ticker: HunterStrategyAdapter(ICTFVGCISDRejectionStrategy(ticker=ticker), "ICT FVG+CISD Rejection"),
    "ict_ny_session":      lambda ticker: HunterStrategyAdapter(ICTNYSessionStrategy(ticker=ticker),      "ICT NY Session KZ"),
    "ict_asia_volatility": lambda ticker: HunterStrategyAdapter(ICTAsiaVolatilityStrategy(ticker=ticker), "ICT Asia Volatility"),
}


def get_strategy(strategy_key: str, ticker: str) -> Any:
    """Resolve and instantiate a strategy by key."""
    if strategy_key not in STRATEGY_FACTORY_REGISTRY:
        raise ValueError(
            f"Strategy '{strategy_key}' not found in registry. "
            f"Available: {list(STRATEGY_FACTORY_REGISTRY.keys())}"
        )
    return STRATEGY_FACTORY_REGISTRY[strategy_key](ticker)
