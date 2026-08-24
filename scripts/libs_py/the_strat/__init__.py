"""The Strat trading library.

Provides:
  - Taxonomy (StratType, classify_bar, classify_bars_df, ActionableWickType)
  - Multi-Timeframe Continuity (FTFCEngine, FTFCResult, Direction)
  - Combos & Setup Recognition (StratComboDetector, StratSetup, ComboType)
  - Backtesting (StratBacktester, StratBacktestSummary)
"""

from scripts.libs_py.the_strat.taxonomy import (
    ActionableWickType,
    StratBarInfo,
    StratType,
    classify_bar,
    classify_bars_df,
)
from scripts.libs_py.the_strat.ftfc import (
    Direction,
    FTFCEngine,
    FTFCResult,
    TimeframeState,
)
from scripts.libs_py.the_strat.combos import (
    ComboType,
    StratComboDetector,
    StratSetup,
    TradeDirection,
)
from scripts.libs_py.the_strat.strategy import (
    StratBacktester,
    StratBacktestSummary,
    StratTradeResult,
)

__all__ = [
    "StratType",
    "ActionableWickType",
    "StratBarInfo",
    "classify_bar",
    "classify_bars_df",
    "Direction",
    "FTFCEngine",
    "FTFCResult",
    "TimeframeState",
    "ComboType",
    "StratComboDetector",
    "StratSetup",
    "TradeDirection",
    "StratBacktester",
    "StratBacktestSummary",
    "StratTradeResult",
]
