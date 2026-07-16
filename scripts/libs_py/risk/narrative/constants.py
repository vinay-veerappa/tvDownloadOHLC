# filepath: scripts/libs_py/risk/narrative/constants.py
"""Risk numbers for the narrative validator.

This module holds the risk-policy data for the LLM-output validator
(`validate_trade_plan`). It is the narrative-chain counterpart to the
backtest `sessions.yaml` risk section — the validator must NOT import
from `scripts.trading_framework.config.config_loader` because that would
couple narrative concerns to backtest concerns.

The values mirror the canonical `scripts/trading_framework/config/sessions.yaml`
and `scripts/streaming/options/config.py` so that the backtest and the
narrative chain agree on contract specs and risk thresholds. If you
change a value here, also update the corresponding YAML entry and add
a note to the change-log at the bottom of this file.

────────────────────────────────────────────────────────────────────────
# TODO — risk-management-module evolution roadmap
#
# This constants file is intentionally a flat data dump. As the project
# grows we will evolve it into a proper risk management module:
#
#   1) Per-prop-firm profiles (Apex 50K, Topstep 50K, FTMO 100K, etc.)
#      sourced from a single `firm_profiles.py` with shared schema.
#   2) Volatility-scaled contract sizing
#      (cap contracts to `floor(risk_cap / (ATR * point_value))`).
#   3) Time-of-day scaling (reduce size in lunch / NY-PM, block in news).
#   4) Correlation caps across correlated instruments (ES+MES, NQ+MNQ).
#   5) News-blackout windows (CPI/FOMC minutes).
#   6) Realized-loss carry-over across days (eval-trail logic).
#   7) Auto-flush at flatten_by from SessionConfig.
#   8) Per-account profit targets (eval pass / consistency rules).
#
# Until then, treat every constant here as a single-source-of-truth
# that the narrative validator and any future trade-execution path
# must agree on. Add a change-log entry below for any modification.
────────────────────────────────────────────────────────────────────────

CHANGE LOG
  2026-07-14  v0.1.0  Initial scaffolding (issue #1: trade-plan validator).
  2026-07-14  v0.1.1  Added PROXY_SYMBOLS and ACCOUNT_SIZE_USD (issue #1.7:
              single source of truth for prompt risk-params rendering).
"""
from __future__ import annotations

from typing import Final


# ── Schema version ──────────────────────────────────────────────────
# Bump on any breaking change to the constants shape. Callers should
# assert `RISK_CONFIG_VERSION` matches the version they were written
# against before reading the tables below.
RISK_CONFIG_VERSION: Final[str] = "0.1.0"


# ── Instrument contract specs ───────────────────────────────────────
# These describe the FUTURES PRODUCT the trader actually executes. They
# do NOT describe the source of options data (that's in
# scripts/streaming/options/config.py).
#
# Fields:
#   name: human-readable label for logs / Discord.
#   multiplier_dollar_per_pt: $ gained/lost for a 1.00 price move
#       (1 contract). For MNQ this is 2.0, MES 5.0, NQ 20.0, ES 50.0.
#   tick_size: minimum price increment in points.
#   tick_value_dollar: dollar value of one tick (1 contract).
#
# KEEP IN SYNC with scripts/trading_framework/config/sessions.yaml
# `execution.point_value` and `execution.tick_size`.
INSTRUMENT_SPECS: Final[dict[str, dict]] = {
    "MNQ": {
        "name": "Micro E-mini Nasdaq-100",
        "multiplier_dollar_per_pt": 2.0,
        "tick_size": 0.25,
        "tick_value_dollar": 0.50,
    },
    "MES": {
        "name": "Micro E-mini S&P 500",
        "multiplier_dollar_per_pt": 5.0,
        "tick_size": 0.25,
        "tick_value_dollar": 1.25,
    },
    "MYM": {
        "name": "Micro E-mini Dow",
        "multiplier_dollar_per_pt": 0.5,
        "tick_size": 1.0,
        "tick_value_dollar": 0.50,
    },
    "M2K": {
        "name": "Micro E-mini Russell 2000",
        "multiplier_dollar_per_pt": 5.0,
        "tick_size": 0.10,
        "tick_value_dollar": 0.50,
    },
    "NQ": {
        "name": "E-mini Nasdaq-100",
        "multiplier_dollar_per_pt": 20.0,
        "tick_size": 0.25,
        "tick_value_dollar": 5.00,
    },
    "ES": {
        "name": "E-mini S&P 500",
        "multiplier_dollar_per_pt": 50.0,
        "tick_size": 0.25,
        "tick_value_dollar": 12.50,
    },
}


# ── Proxy ETF symbols ───────────────────────────────────────────────
# The equity ETF the trader watches for context (volume, gex, EM
# levels) for each futures product. Used by the prompt-renderer
# (`prompt_render.py`) so the LLM has a clear "watch this ETF in
# parallel with this futures" link. This is *not* a tradeable
# contract in the prop-firm account — the LLM still sizes to the
# futures product and the micro contract.
PROXY_SYMBOLS: Final[dict[str, str]] = {
    "MNQ": "QQQ",
    "MES": "SPY",
    "MYM": "DIA",
    "M2K": "IWM",
    "NQ":  "QQQ",
    "ES":  "SPY",
}


# ── Account phases ──────────────────────────────────────────────────
# Prop firms typically run two phases:
#   EVAL    — paying for the challenge, strict daily/total DD, can pass
#             with profit. Tighter daily stop to protect the eval fee.
#   FUNDED  — passed the eval, looser daily DD but TIGHT trailing DD
#             that thins the account every day you trade (Topstep,
#             Apex). Tighter per-trade risk; trailing DD becomes the
#             binding constraint.
#
# Fields:
#   default_risk_cap_per_trade_usd: $ cap on a single trade's risk
#       (all-instruments combined). Overridden by PER_INSTRUMENT_CAPS
#       where set.
#   daily_stop_usd: cumulative realized loss for the day → stop trading.
#   total_dd_buffer_usd: reserve respecting the trailing-DD buffer.
#   max_open_trades: maximum open positions allowed in a session.
#   min_reward_to_risk: warn (do NOT block) below this.
#   block_reward_to_risk: drop the trade if R:R is below this threshold.
#   allow_overnight: whether overnight holds are permitted. Eval
#       accounts must flatten daily.
ACCOUNT_PHASES: Final[dict[str, dict]] = {
    "EVAL": {
        "description": "Prop firm evaluation account. Tighter daily stop to protect the eval fee.",
        "default_risk_cap_per_trade_usd": 150.0,
        "daily_stop_usd": 450.0,
        "total_dd_buffer_usd": 0.0,
        "max_open_trades": 3,
        "min_reward_to_risk": 1.5,
        "block_reward_to_risk": 1.0,
        "allow_overnight": False,
    },
    "FUNDED": {
        "description": "Funded account. Tighter per-trade risk; trailing DD becomes the binding constraint.",
        "default_risk_cap_per_trade_usd": 100.0,
        "daily_stop_usd": 300.0,
        "total_dd_buffer_usd": 2000.0,
        "max_open_trades": 2,
        "min_reward_to_risk": 2.0,
        "block_reward_to_risk": 1.0,
        "allow_overnight": False,
    },
}


# ── Per-instrument risk caps ────────────────────────────────────────
# Per-trade $ cap, OVERRIDING the account-phase default for that
# specific instrument. e.g., on ES1 (full-size) we want a tighter
# per-trade cap than the account default would suggest. If an
# instrument is not listed here, the account-phase
# `default_risk_cap_per_trade_usd` applies.
#
# Values below assume 1 contract and the typical stop distance:
#   MNQ $100  ~ 50 pts stop × $2/pt × 1c
#   MES $150  ~ 30 pts stop × $5/pt × 1c
#   MYM $100  ~200 pts stop × $0.5/pt × 1c
#   M2K  $50  ~ 10 pts stop × $5/pt × 1c
#   NQ  $200  ~ 10 pts stop × $20/pt × 1c
#   ES  $250  ~  5 pts stop × $50/pt × 1c
PER_INSTRUMENT_CAPS: Final[dict[str, dict]] = {
    "MNQ": {"risk_cap_per_trade_usd": 100.0},
    "MES": {"risk_cap_per_trade_usd": 150.0},
    "MYM": {"risk_cap_per_trade_usd": 100.0},
    "M2K": {"risk_cap_per_trade_usd": 50.0},
    "NQ":  {"risk_cap_per_trade_usd": 200.0},
    "ES":  {"risk_cap_per_trade_usd": 250.0},
}


# ── Active phase ────────────────────────────────────────────────────
# Which phase the validator applies. Update this when the trader
# passes the eval and switches to a funded account. In the future
# this may be driven by a broker API status read.
ACTIVE_PHASE: Final[str] = "EVAL"

# ── Account size (for prompt context) ────────────────────────────
# The size of the active prop-firm account in USD. Used by the
# prompt-renderer (`prompt_render.py`) to give the LLM the
# "we are running a $50k eval" context that shapes the size of
# the trailing-DD buffer line. NOT a parameter the validator
# acts on (the validator only enforces the per-trade cap, the
# daily stop, and the max open trades).
ACCOUNT_SIZE_USD: Final[dict[str, int]] = {
    "EVAL": 50_000,
    "FUNDED": 100_000,
}

# ── Validator rules ─────────────────────────────────────────────────
# Tunable thresholds for the validate_trade_plan() pipeline. These
# are separate from the account-phase data because they describe the
# VALIDATOR'S behaviour, not the trader's risk appetite.
#
# Fields:
#   max_price_decimals: prices are rounded to this many decimals.
#   drop_on_unknown_asset: True → drop trade; False → log and keep.
#   log_warnings: True → write each warning to module log; False →
#       return them silently.
VALIDATOR_RULES: Final[dict] = {
    "max_price_decimals": 2,
    "drop_on_unknown_asset": True,
    "log_warnings": True,
}


# Public alias used in `Config.__init__` validation
VALID_PHASES: Final[frozenset[str]] = frozenset(ACCOUNT_PHASES.keys())
