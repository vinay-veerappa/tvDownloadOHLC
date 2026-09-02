"""Trading framework core package."""
from scripts.trading_framework.core.base import BaseBacktester, SignalGenerator, RegimeModel
from scripts.trading_framework.core.backtest_engine import VectorizedBacktester
from scripts.trading_framework.core.nt8_parity_backtester import NT8ParityBacktester

__all__ = [
    "BaseBacktester",
    "SignalGenerator",
    "RegimeModel",
    "VectorizedBacktester",
    "NT8ParityBacktester",
]
