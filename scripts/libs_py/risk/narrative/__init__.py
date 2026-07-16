# filepath: scripts/libs_py/risk/narrative/__init__.py
"""Narrative-chain risk validation.

This sub-package contains the validator that scrubs LLM-generated trade
plans before they reach the Prisma DB. It is intentionally separate
from the backtest risk files in `scripts.libs_py.risk` (which contain
`AccountRiskManager`, `SessionRiskManager`, and `TradePolicy`).

Why a separate sub-package:
  - Backtest risk is realtime/strategy-facing (entry gating, state
    transitions, trade management policies). Narrative risk is
    post-LLM, offline, geometry/position-sizing validation.
  - The two have different change cadences. A backtest tweak to chop
    detection should not require touching the narrative validator,
    and a tweak to LLM-output rules should not require rerunning
    backtests.
  - Keeping them decoupled lets the narrative chain stay free of
    backtest-only dependencies (pandas-heavy code, yaml configs).

Public API:
    from scripts.libs_py.risk.narrative import (
        validate_trade_plan,
        get_risk_config,
        RiskConfig,
        InstrumentSpec,
        AccountPhase,
        ValidatorRules,
        reset_cache,
    )

See `README.md` in this directory for the module's evolution roadmap.
"""
from __future__ import annotations

from typing import Final

from .config import (
    AccountPhase,
    InstrumentSpec,
    RiskConfig,
    ValidatorRules,
    get_risk_config,
    reset_cache,
)
from .validator import (
    DIR_LONG,
    DIR_SHORT,
    KEY_ASSET,
    KEY_CONTRACTS,
    KEY_DIRECTION,
    KEY_DOLLAR_RISK,
    KEY_ENTRY,
    KEY_LOGIC,
    KEY_NOTRADE,
    KEY_NOTRADE_REASON,
    KEY_REGIME,
    KEY_RR,
    KEY_STOP,
    KEY_STOP_DIST,
    KEY_TARGET,
    KEY_TRADES,
    validate_trade_plan,
)
from .track_mandate import (
    KEY_MANDATED_TRACK,
    KEY_VIOLATION,
    validate_track_mandate,
)
from .prompt_render import (
    DEFAULT_INSTRUMENT_ORDER,
    EMPTY_BLOCK,
    format_risk_params_block,
    insert_risk_params,
)

__all__: Final[tuple[str, ...]] = (
    # Main API
    "validate_trade_plan",
    "get_risk_config",
    "reset_cache",
    # Typed config classes
    "AccountPhase",
    "InstrumentSpec",
    "RiskConfig",
    "ValidatorRules",
    # Validator key constants (for downstream consumers)
    "KEY_ASSET",
    "KEY_CONTRACTS",
    "KEY_DIRECTION",
    "KEY_DOLLAR_RISK",
    "KEY_ENTRY",
    "KEY_LOGIC",
    "KEY_NOTRADE",
    "KEY_NOTRADE_REASON",
    "KEY_REGIME",
    "KEY_RR",
    "KEY_STOP",
    "KEY_STOP_DIST",
    "KEY_TARGET",
    "KEY_TRADES",
    "DIR_LONG",
    "DIR_SHORT",
    # Track-mandate enforcer (issue §1.4)
    "validate_track_mandate",
    "KEY_MANDATED_TRACK",
    "KEY_VIOLATION",    # Prompt-render helpers (issue §1.7)
    "format_risk_params_block",
    "insert_risk_params",
    "DEFAULT_INSTRUMENT_ORDER",
    "EMPTY_BLOCK",)
