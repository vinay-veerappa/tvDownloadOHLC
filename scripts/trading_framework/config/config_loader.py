"""
Load and validate YAML configuration into typed dataclasses.
"""
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional
import yaml


class RiskMode(Enum):
    RAW = "raw"
    STRATEGY = "strategy"
    PORTFOLIO = "portfolio"


class TrailMethod(Enum):
    ATR = "atr"
    STRUCTURE = "structure"
    FIXED = "fixed"


class TrailingType(Enum):
    EOD = "eod"
    INTRADAY = "intraday"


@dataclass(frozen=True)
class SessionConfig:
    rth_start: str
    rth_end: str
    ib_end: str
    ny_am_end: str
    lunch_start: str
    lunch_end: str
    ny_pm_start: str
    last_entry: str
    flatten_by: str


@dataclass(frozen=True)
class ExecutionConfig:
    slippage_ticks: int
    commission_per_contract: float
    tick_size: dict[str, float]
    point_value: dict[str, float]
    default_contracts: int


@dataclass(frozen=True)
class SessionRiskConfig:
    daily_max_loss: float
    max_consecutive_losers: int
    pause_after_consecutive_minutes: int
    hard_stop_consecutive_losers: int
    max_trades_per_day: int
    max_concurrent_positions: int


@dataclass(frozen=True)
class AccountRiskConfig:
    starting_equity: float
    trailing_drawdown: float
    trailing_type: TrailingType
    profit_target: float
    weekly_drawdown_limit: float
    weekly_action: str


@dataclass(frozen=True)
class ChopConfig:
    tick_persistence: dict
    vold_slope: dict
    trin_regime: dict
    vwap_cross: dict


@dataclass(frozen=True)
class MfeMaeConfig:
    forward_horizons_minutes: list[int]
    max_forward_bars_1m: int
    normalize_by: str
    atr_period: int
    atr_timeframe: str


@dataclass(frozen=True)
class WalkForwardConfig:
    train_days: int
    test_days: int
    step_days: int
    embargo_bars: int


@dataclass(frozen=True)
class MonteCarloConfig:
    n_simulations: int
    eval_days: int


@dataclass(frozen=True)
class OptimizationConfig:
    n_trials: int
    n_jobs: int
    primary_metric: str
    secondary_metrics: list[str]
    walk_forward: WalkForwardConfig
    monte_carlo: MonteCarloConfig


@dataclass
class AppConfig:
    """Top-level configuration. Loaded from YAML, validated, and passed
    to every library/strategy module."""
    data_dir: Path
    symbols_price: list[str]
    symbols_internals: list[str]
    date_start: str
    date_end: str
    sessions: SessionConfig
    risk_mode: RiskMode
    trade_risk_policy: str
    trade_risk_policies: dict          # Raw dict — policies parse themselves
    session_risk: SessionRiskConfig
    account_risk: AccountRiskConfig
    execution: ExecutionConfig
    chop: ChopConfig
    mfe_mae: MfeMaeConfig
    optimization: OptimizationConfig


def load_config(path: str = "scripts/trading_framework/config/sessions.yaml") -> AppConfig:
    """Load YAML config and return a validated AppConfig instance.

    Steps:
    1. Read YAML file
    2. Parse each section into its typed dataclass
    3. Validate cross-field constraints (e.g., weekly_drawdown_limit < trailing_drawdown)
    4. Return frozen AppConfig

    Raises ValueError on invalid config.
    """
    with open(path, encoding='utf-8') as f:
        raw = yaml.safe_load(f)

    # Parse each section into dataclasses
    sessions = SessionConfig(**raw["sessions"])
    execution = ExecutionConfig(**raw["execution"])
    session_risk = SessionRiskConfig(**raw["session_risk"])
    account_risk = AccountRiskConfig(
        **{**raw["account_risk"],
           "trailing_type": TrailingType(raw["account_risk"]["trailing_type"])}
    )
    chop = ChopConfig(**raw["chop"])
    mfe_mae = MfeMaeConfig(**raw["mfe_mae"])
    wf = WalkForwardConfig(**raw["optimization"]["walk_forward"])
    mc = MonteCarloConfig(**raw["optimization"]["monte_carlo"])
    opt = OptimizationConfig(
        n_trials=raw["optimization"]["n_trials"],
        n_jobs=raw["optimization"]["n_jobs"],
        primary_metric=raw["optimization"]["primary_metric"],
        secondary_metrics=raw["optimization"]["secondary_metrics"],
        walk_forward=wf,
        monte_carlo=mc,
    )

    config = AppConfig(
        data_dir=Path(raw["data"]["parquet_dir"]),
        symbols_price=raw["data"]["symbols"]["price"],
        symbols_internals=raw["data"]["symbols"]["internals"],
        date_start=raw["data"]["date_range"]["start"],
        date_end=raw["data"]["date_range"]["end"],
        sessions=sessions,
        risk_mode=RiskMode(raw["risk_mode"]),
        trade_risk_policy=raw["trade_risk"]["default_policy"],
        trade_risk_policies=raw["trade_risk"]["policies"],
        session_risk=session_risk,
        account_risk=account_risk,
        execution=execution,
        chop=chop,
        mfe_mae=mfe_mae,
        optimization=opt,
    )

    # Cross-field validation
    assert config.account_risk.weekly_drawdown_limit < config.account_risk.trailing_drawdown, \
        "weekly_drawdown_limit must be less than trailing_drawdown"
    assert config.session_risk.hard_stop_consecutive_losers >= config.session_risk.max_consecutive_losers, \
        "hard_stop must be >= pause threshold"

    return config
