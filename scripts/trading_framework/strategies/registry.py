"""Strategy registry for dynamic discovery and lifecycle execution."""

from typing import Any, Callable, Dict

import pandas as pd

from scripts.strategies.ema_pullback.core.ema_pullback import EMAPullbackStrategy
from scripts.strategies.failed_auction.core.failed_auction import FailedAuctionStrategy
from scripts.strategies.initial_balance.core.initial_balance_pullback import IBPullbackStrategy
from scripts.strategies.reversal.core.box_reversion import BoxReversionStrategy
from scripts.strategies.reversal.core.mean_reversion import MeanReversionStrategy
from scripts.strategies.reversal.core.six_am_reversal import SixAMReversalStrategy
from scripts.strategies.vwap_reclaim.core.vwap_reclaim import VWAPReclaimStrategy


class HunterStrategyAdapter:
    """Adapter to expose hunt()-style strategies as lifecycle-compatible strategies."""

    def __init__(self, strategy: Any, strategy_name: str):
        self._strategy = strategy
        self.strategy_name = strategy_name

    def generate_signals(self, data: pd.DataFrame, config: Dict[str, Any]) -> pd.DataFrame:
        return self._strategy.hunt(data, params=config)

    def get_param_grid(self) -> Dict[str, Any]:
        return self._strategy.get_param_grid()


STRATEGY_FACTORY_REGISTRY: Dict[str, Callable[[str], Any]] = {
    "ib_pullback": lambda ticker: HunterStrategyAdapter(IBPullbackStrategy(ticker=ticker), "IB Pullback"),
    "box_reversion": lambda ticker: HunterStrategyAdapter(BoxReversionStrategy(ticker=ticker), "Box Reversion"),
    "mean_reversion": lambda ticker: HunterStrategyAdapter(MeanReversionStrategy(ticker=ticker), "Mean Reversion"),
    "ema_pullback": lambda ticker: HunterStrategyAdapter(EMAPullbackStrategy(ticker=ticker), "EMA Pullback"),
    "vwap_reclaim": lambda ticker: HunterStrategyAdapter(VWAPReclaimStrategy(ticker=ticker), "VWAP Reclaim"),
    "failed_auction": lambda ticker: HunterStrategyAdapter(FailedAuctionStrategy(ticker=ticker), "Failed Auction"),
    "six_am_reversal": lambda ticker: HunterStrategyAdapter(SixAMReversalStrategy(ticker=ticker), "6 AM Reversal"),
}


def get_strategy(strategy_key: str, ticker: str) -> Any:
    """Resolve and instantiate a strategy by key."""
    if strategy_key not in STRATEGY_FACTORY_REGISTRY:
        raise ValueError(
            f"Strategy '{strategy_key}' not found in registry. "
            f"Available: {list(STRATEGY_FACTORY_REGISTRY.keys())}"
        )
    return STRATEGY_FACTORY_REGISTRY[strategy_key](ticker)
