# filepath: scripts/libs_py/risk/narrative/config.py
"""Typed loader for the narrative risk config.

Wraps the flat data in `constants.py` into immutable dataclasses so the
rest of the validator and any future consumers can use them with static
type-checkers. The constants module remains the single edit-point; this
file just provides the typed view.

The module is intentionally decoupled from `scripts.trading_framework
.config.config_loader` (which is the backtest config). The narrative
chain must not depend on the backtest config because:

  1. The narrative chain is a higher-level abstraction that runs on
     fixed schedule and does not need the backtest machinery.
  2. Tight coupling would force the narrative to import pandas,
     pyyaml, and a large config object just to read three numbers.
  3. The two configs evolve at different cadences: a backtest tweak
     to chop detection should not require touching the narrative.

If you need to share a value with the backtest, mirror it in
`constants.py` with a clear "KEEP IN SYNC" comment.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Final

from . import constants as C


# ── Typed views ──────────────────────────────────────────────────────
@dataclass(frozen=True)
class InstrumentSpec:
    """Per-instrument contract specification.

    Attributes:
        name: human-readable label.
        multiplier_dollar_per_pt: $ gained/lost for a 1.00 price move
            for 1 contract.
        tick_size: minimum price increment in points.
        tick_value_dollar: $ value of one tick for 1 contract.
    """
    name: str
    multiplier_dollar_per_pt: float
    tick_size: float
    tick_value_dollar: float


@dataclass(frozen=True)
class AccountPhase:
    """Risk policy for a prop-firm account phase.

    Attributes:
        label: 'EVAL' or 'FUNDED'.
        description: human-readable explanation.
        default_risk_cap_per_trade_usd: per-trade $ cap when no
            per-instrument override exists.
        daily_stop_usd: cumulative realized loss that triggers a
            day-stop.
        total_dd_buffer_usd: reserve respecting the trailing-DD buffer.
        max_open_trades: maximum open positions allowed per session.
        min_reward_to_risk: warn (do not block) below this.
        block_reward_to_risk: drop the trade if R:R is below this.
        allow_overnight: whether overnight holds are permitted.
    """
    label: str
    description: str
    default_risk_cap_per_trade_usd: float
    daily_stop_usd: float
    total_dd_buffer_usd: float
    max_open_trades: int
    min_reward_to_risk: float
    block_reward_to_risk: float
    allow_overnight: bool


@dataclass(frozen=True)
class ValidatorRules:
    """Behaviour switches for the validator itself.

    Attributes:
        max_price_decimals: prices are rounded to this many decimals.
        drop_on_unknown_asset: True → drop trade; False → log+keep.
        log_warnings: True → write each warning to module log.
    """
    max_price_decimals: int
    drop_on_unknown_asset: bool
    log_warnings: bool


@dataclass(frozen=True)
class RiskConfig:
    """Top-level typed config for the narrative validator.

    Attributes:
        version: schema version, must match RISK_CONFIG_VERSION.
        active_phase: which ACCOUNT_PHASES entry is currently active.
        instruments: keyed by symbol (e.g. "MNQ").
        account_phases: keyed by phase label.
        per_instrument_caps: keyed by symbol.
        validator_rules: validator behaviour switches.
    """
    version: str
    active_phase: str
    instruments: dict[str, InstrumentSpec]
    account_phases: dict[str, AccountPhase]
    per_instrument_caps: dict[str, dict]
    validator_rules: ValidatorRules

    def get_instrument(self, symbol: str) -> InstrumentSpec | None:
        """Return the InstrumentSpec for `symbol` or None if unknown."""
        return self.instruments.get(symbol.upper())

    def get_phase(self) -> AccountPhase:
        """Return the active AccountPhase.

        Raises:
            KeyError: if `active_phase` is not in `account_phases`
                (should not happen if validation passed).
        """
        return self.account_phases[self.active_phase]

    def get_risk_cap(self, symbol: str) -> float:
        """Per-trade $ cap for `symbol`.

        Order of precedence:
          1. PER_INSTRUMENT_CAPS[symbol].risk_cap_per_trade_usd
          2. active phase `default_risk_cap_per_trade_usd`
        """
        cap = self.per_instrument_caps.get(symbol.upper(), {}).get("risk_cap_per_trade_usd")
        if cap is not None:
            return float(cap)
        return self.get_phase().default_risk_cap_per_trade_usd


# ── Loader ──────────────────────────────────────────────────────────
def _build_config() -> RiskConfig:
    """Construct a frozen RiskConfig from the constants module."""
    instruments: dict[str, InstrumentSpec] = {
        sym: InstrumentSpec(
            name=spec["name"],
            multiplier_dollar_per_pt=float(spec["multiplier_dollar_per_pt"]),
            tick_size=float(spec["tick_size"]),
            tick_value_dollar=float(spec["tick_value_dollar"]),
        )
        for sym, spec in C.INSTRUMENT_SPECS.items()
    }
    phases: dict[str, AccountPhase] = {
        label: AccountPhase(
            label=label,
            description=spec["description"],
            default_risk_cap_per_trade_usd=float(spec["default_risk_cap_per_trade_usd"]),
            daily_stop_usd=float(spec["daily_stop_usd"]),
            total_dd_buffer_usd=float(spec["total_dd_buffer_usd"]),
            max_open_trades=int(spec["max_open_trades"]),
            min_reward_to_risk=float(spec["min_reward_to_risk"]),
            block_reward_to_risk=float(spec["block_reward_to_risk"]),
            allow_overnight=bool(spec["allow_overnight"]),
        )
        for label, spec in C.ACCOUNT_PHASES.items()
    }
    rules = ValidatorRules(
        max_price_decimals=int(C.VALIDATOR_RULES["max_price_decimals"]),
        drop_on_unknown_asset=bool(C.VALIDATOR_RULES["drop_on_unknown_asset"]),
        log_warnings=bool(C.VALIDATOR_RULES["log_warnings"]),
    )

    active = C.ACTIVE_PHASE
    if active not in phases:
        raise ValueError(
            f"ACTIVE_PHASE={active!r} is not in ACCOUNT_PHASES. "
            f"Valid phases: {sorted(phases)}"
        )

    return RiskConfig(
        version=C.RISK_CONFIG_VERSION,
        active_phase=active,
        instruments=instruments,
        account_phases=phases,
        per_instrument_caps=dict(C.PER_INSTRUMENT_CAPS),
        validator_rules=rules,
    )


@lru_cache(maxsize=1)
def get_risk_config() -> RiskConfig:
    """Return the cached, frozen RiskConfig.

    The cache is process-wide. Use `reset_cache()` in tests or after
    a hot-reload of `constants.py`.
    """
    return _build_config()


def reset_cache() -> None:
    """Clear the cached RiskConfig. Useful for tests and hot-reload."""
    get_risk_config.cache_clear()


# Re-exports for downstream `from .config import X` ergonomics
__all__: Final[tuple[str, ...]] = (
    "AccountPhase",
    "InstrumentSpec",
    "RiskConfig",
    "ValidatorRules",
    "get_risk_config",
    "reset_cache",
)
