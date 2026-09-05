"""The Strat trading library (Pillar 1 — stateless math + signal engine).

Layers (STRATEGY_WORKFLOW.md section 1.1, the three pillars):
  - taxonomy / combos / ftfc : raw Strat primitives (bar types, patterns, continuity)
  - targets / session        : measured-move targets, ET session/killzone gates
  - signals                  : StratSignalEngine — THE single OHLC -> signals path
                               (per-timeframe classify + scan + FTFC attach)
  - config                   : canonical strat_config.json loader (shared with NT8)
  - strategy                 : legacy event backtester (kept for compat)
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
from scripts.libs_py.the_strat.config import (
    StratConfig,
    load_strat_config,
    CANONICAL_CONFIG_PATH,
)
from scripts.libs_py.the_strat.targets import MeasuredTargets, measured_targets
from scripts.libs_py.the_strat.session import (
    entry_allowed,
    killzones_from_config,
    parse_hhmm,
)
from scripts.libs_py.the_strat.signals import StratSignalEngine, OUTPUT_COLUMNS as SIGNAL_COLUMNS

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
    "StratConfig",
    "load_strat_config",
    "CANONICAL_CONFIG_PATH",
    "MeasuredTargets",
    "measured_targets",
    "entry_allowed",
    "killzones_from_config",
    "parse_hhmm",
    "StratSignalEngine",
    "SIGNAL_COLUMNS",
]
