"""
Load and validate YAML configuration into typed dataclasses.
"""
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict
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
    tick_size: Dict[str, float]
    point_value: Dict[str, float]
    default_contracts: int
    use_micro_multipliers: bool = True


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
    forward_horizons_minutes: List[int]
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
    secondary_metrics: List[str]
    walk_forward: WalkForwardConfig
    monte_carlo: MonteCarloConfig


@dataclass(frozen=True)
class PropFirmConfig:
    """
    Config for PropFirmSimulator (ADR-021).
    Consumed by run_backtest.py Layer 6.
    """
    primary_profile: str               # Profile key for tearsheet primary result
    run_profiles: List[str]            # Profiles to run in run_all_profiles()
    n_simulations: int                 # Monte Carlo permutation count
    overrides: Dict[str, dict]         # Per-profile field overrides


@dataclass
class AppConfig:
    """Top-level configuration."""
    data_dir: Path
    symbols_price: List[str]
    symbols_internals: List[str]
    date_start: str
    date_end: str
    sessions: SessionConfig
    risk_mode: RiskMode
    trade_risk_policy: str
    trade_risk_policies: dict
    session_risk: SessionRiskConfig
    account_risk: AccountRiskConfig
    execution: ExecutionConfig
    chop: ChopConfig
    mfe_mae: MfeMaeConfig
    optimization: OptimizationConfig
    prop_firm: PropFirmConfig


def load_config(path: str = "scripts/trading_framework/config/sessions.yaml") -> AppConfig:
    """Load and validate and scale Mini -> Micro (ADR-009)."""
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    # 1. Scaling logic (ADR-009)
    exec_data = raw["execution"].copy()
    if exec_data.get("use_micro_multipliers", True):
        m_map = {"ES": 5.0, "ES1!": 5.0, "MES": 5.0, 
                 "NQ": 2.0, "NQ1!": 2.0, "MNQ": 2.0,
                 "RTY": 5.0, "M2K": 5.0, 
                 "YM": 0.5, "MYM": 0.5}
        pv = exec_data.get("point_value", {}).copy()
        for sym, val in m_map.items():
            if sym in pv and pv[sym] > val:
                pv[sym] = val
            elif sym not in pv:
                pv[sym] = val
        exec_data["point_value"] = pv
        exec_data["use_micro_multipliers"] = True

    # 2. Instantiate dataclasses
    sessions = SessionConfig(**raw["sessions"])
    execution = ExecutionConfig(**exec_data)
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

    pf_raw = raw.get("prop_firm", {})
    prop_firm = PropFirmConfig(
        primary_profile=pf_raw.get("primary_profile", "apex_50k"),
        run_profiles=pf_raw.get("run_profiles", ["apex_50k", "topstep_50k", "ftmo_50k"]),
        n_simulations=pf_raw.get("n_simulations", 5000),
        overrides=pf_raw.get("overrides", {}),
    )

    return AppConfig(
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
        prop_firm=prop_firm,
    )
