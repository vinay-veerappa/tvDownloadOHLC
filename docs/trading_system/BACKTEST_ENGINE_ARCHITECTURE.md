# Daytrading Bot Backtest Framework — Implementation Specification

## For IDE-Assisted Code Generation

---

## Table of Contents

1. [Project Overview & Conventions](#1-project-overview--conventions)
2. [Directory Structure](#2-directory-structure)
3. [Configuration System](#3-configuration-system)
4. [LIBRARY: Data Layer](#4-library-data-layer)
5. [LIBRARY: Feature Engine](#5-library-feature-engine)
6. [LIBRARY: Risk Management](#6-library-risk-management)
7. [LIBRARY: Backtest Engine](#7-library-backtest-engine)
8. [LIBRARY: Regime Detection](#8-library-regime-detection)
9. [LIBRARY: Reporting](#9-library-reporting)
10. [LIBRARY: ML / Optimization](#10-library-ml--optimization)
11. [STRATEGY: VWAP Reclaim/Rejection](#11-strategy-vwap-reclaimrejection)
12. [STRATEGY: Initial Balance Breakout/Failure](#12-strategy-initial-balance-breakoutfailure)
13. [STRATEGY: EMA Pullback Continuation](#13-strategy-ema-pullback-continuation)
14. [STRATEGY: Failed Auction Fill](#14-strategy-failed-auction-fill)
15. [STRATEGY: Initial Balance Pullback (ICT)](#15-strategy-initial-balance-pullback-ict)
16. [STRATEGY: Reversal & Mean Reversion Suite](#16-strategy-reversal--mean-reversion-suite)
17. [UTILITY: Acceptance/Rejection Classifier](#17-utility-acceptancerejection-classifier)
18. [UTILITY: Chop Detection Composite](#18-utility-chop-detection-composite)
19. [Orchestration & Run Scripts](#19-orchestration--run-scripts)
20. [Testing Strategy](#20-testing-strategy)

---

## 1. Project Overview & Conventions

### Purpose

Build a modular, reusable Python backtesting platform for intraday futures strategies
(MES, MNQ). Every component is designed as either a **LIBRARY** (generic, reusable across
any strategy) or a **STRATEGY** (specific signal logic that consumes libraries).

### Data Assumption

All source data exists as `<SYMBOL>_1m.parquet` files in `data/parquet/`.
Each file contains 1-minute bars with columns:
`datetime` (tz-aware US/Eastern), `open`, `high`, `low`, `close`, `volume`.

Available symbols: `ES`, `NQ`, `TICK`, `TICKQ`, `UVOL`, `DVOL`, `TRIN`, `TRINQ`, `ADV`, `VIX`.

Approximately 10 years of history (~2,500 trading sessions).

### Python Conventions

- Python 3.11+
- Type hints on all function signatures
- Dataclasses for structured data (not dicts)
- Enums for categorical state (regime labels, trade direction, risk mode, etc.)
- Pandas DataFrames for time series, with `datetime` always as the index
- All timestamps are timezone-aware `US/Eastern`
- Logging via `logging` module (no print statements in library code)
- Configuration via dataclasses loaded from YAML (one canonical config per run)
- Every library module is importable independently — no circular dependencies

### Naming Conventions

- Modules: `snake_case.py`
- Classes: `PascalCase`
- Functions: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Config keys: `snake_case`
- Strategy names: `snake_case` (e.g., `vwap_reclaim`, `ib_breakout`)

### Key Design Principle: Three Risk Modes

Every backtest can run in one of three modes, controlled by `risk_mode` in config:

| Mode        | What's Active                                                                                   | Purpose                                             |
| ----------- | ----------------------------------------------------------------------------------------------- | --------------------------------------------------- |
| `raw`       | No stops, no targets, no limits. Record full forward price path for every signal.               | MFE/MAE analysis. Designing risk parameters.        |
| `strategy`  | Trade-level risk only (stop, target, partials via pluggable policy). No session/account limits. | Measure per-trade expectancy with realistic exits.  |
| `portfolio` | All three risk levels: trade + session + account (prop rules).                                  | Realistic P&L simulation for prop eval Monte Carlo. |

---

## 2. Directory Structure

```
project_root/
│
├── data/
│   ├── live/                           # Real-time streaming parquet buffer
│   ├── derived/                        # Derived stationary features parquet
│   └── *_1m.parquet                    # Source data
│
├── docs/                               # Architecture and Specs
│
├── scripts/
│   ├── trading_framework/              # THE ENGINE
│   │   ├── config/                     # Core configs (e.g. sessions.yaml)
│   │   ├── core/                       # Backtest engine, execution modeling, loop
│   │   ├── ml/                         # Optuna integration, walk-forward routines
│   │   ├── reporting/                  # Tearsheets, metrics, risk profiler logic
│   │   ├── research/                   # Research databases and tools
│   │   ├── library/                    # Framework adapters
│   │   │   └── nqstats_adapter.py      # Adapter to feed nqstats to other systems
│   │   └── signals/                    # Generic signals
│   │
│   ├── libs/                           # THE DOMAINS (Reusable across any script)
│   │   ├── data/
│   │   │   ├── loader.py               # Load and merge parquet files
│   │   │   ├── session_tagger.py       # Tag bars with session labels
│   │   │   └── resampler.py            # Resample 1m to 5m, 15m, etc.
│   │   │
│   │   ├── features/
│   │   │   ├── registry.py             # Central feature registry
│   │   │   ├── vwap.py                 # VWAP and VWAP-derived features
│   │   │   ├── initial_balance.py      # IB high/low/mid/width/extensions
│   │   │   └── ...                     # Auction, ema, chop, internals
│   │   │
│   │   ├── regime/
│   │   │   ├── base.py                 # Abstract RegimeModel interface
│   │   │   ├── threshold.py            # Rule-based regime detection
│   │   │   └── hmm.py                  # Hidden Markov Model
│   │   │
│   │   └── risk/
│   │       └── trade_policies.py       # Pluggable trade management policies
│   │
│   ├── strategies/                     # STRATEGY-SPECIFIC CODE
│   │   ├── base.py                     # Abstract strategy interface
│   │   ├── vwap_reclaim/
│   │   ├── ib_breakout/
│   │   ├── ema_pullback/
│   │   └── failed_auction/
│   │
│   └── tests/
│       ├── test_loader.py
│       ├── test_features.py
│       ├── test_backtest.py
│       └── test_signals.py
│
├── notebooks/                          # Research Notebooks
└── requirements.txt
```

---

## 3. Configuration System

### File: `scripts/trading_framework/config/sessions.yaml`

```yaml
# ═══════════════════════════════════════════════════════════════
# Master Configuration
# ═══════════════════════════════════════════════════════════════

data:
  parquet_dir: "data/parquet"
  symbols:
    price: ["MES", "MNQ"]
    internals: ["TICK", "TICKQ", "UVOL", "DVOL", "TRIN", "TRINQ", "ADV", "VIX"]
  date_range:
    start: "2016-01-01"
    end: "2026-03-31"

sessions:
  # All times in US/Eastern
  rth_start: "09:30"
  rth_end: "16:00"
  ib_end: "10:30" # Initial balance period end
  ny_am_end: "11:00"
  lunch_start: "11:00"
  lunch_end: "13:30"
  ny_pm_start: "13:30"
  last_entry: "14:30" # No new entries after this
  flatten_by: "15:45" # Flatten all positions

risk_mode: "raw" # "raw", "strategy", or "portfolio"

# ── Trade-level risk (active in "strategy" and "portfolio" modes) ──
trade_risk:
  default_policy: "cover_the_queen" # Policy name from trade_policies.py
  policies:
    cover_the_queen:
      partial_exit_pct: 0.50 # Take 50% off at first target
      partial_target_rr: 1.0 # First target at 1:1 R:R
      remainder_trail_method: "atr" # "atr", "structure", "fixed"
      trail_atr_multiplier: 2.0 # For ATR trailing
      trail_atr_period: 14
      move_stop_to_breakeven: true # After partial, move stop to entry
    fixed_target:
      target_rr: 2.0 # Take 100% at 2:1 R:R
    scaled_exit:
      exits: # List of {pct, target_rr}
        - { pct: 0.33, target_rr: 1.0 }
        - { pct: 0.33, target_rr: 2.0 }
        - { pct: 0.34, trail: true, trail_atr_multiplier: 2.0 }
    breakeven_trail:
      breakeven_trigger_rr: 1.0 # Move stop to BE at 1R
      trail_atr_multiplier: 1.5
    time_stop:
      max_bars: 30 # Exit if target not hit in N bars
      applies_to: "remainder" # "full" or "remainder" (after partial)

# ── Session-level risk (active in "portfolio" mode) ──
session_risk:
  daily_max_loss: 400.0 # USD — flatten and stop if hit
  max_consecutive_losers: 2 # Pause 30 min after 2 consecutive losses
  pause_after_consecutive_minutes: 30
  hard_stop_consecutive_losers: 3 # Done for day after 3 consecutive losses
  max_trades_per_day: 3 # Across all strategies
  max_concurrent_positions: 1 # Only 1 position at a time

# ── Account-level risk (active in "portfolio" mode) ──
account_risk:
  starting_equity: 50000.0
  trailing_drawdown: 2000.0 # EOD trailing — adjust per firm
  trailing_type: "eod" # "eod" or "intraday"
  profit_target: 3000.0 # Eval profit target
  weekly_drawdown_limit: 800.0 # 40% of trailing DD
  weekly_action: "observation" # "observation" or "reduce_size"

# ── Execution model ──
execution:
  slippage_ticks: 1 # 1 tick each way
  commission_per_contract: 0.62 # Round-trip
  tick_size:
    MES: 0.25
    MNQ: 0.25
  point_value:
    MES: 5.0 # $5 per point
    MNQ: 2.0 # $2 per point
  default_contracts: 1

# ── Chop detection ──
chop:
  tick_persistence:
    window_minutes: 30
    thresholds: [150, 350] # Score: 0 if <150, 1 if 150-350, 2 if >350
  vold_slope:
    method: "linreg" # Linear regression slope from session open
    threshold: 0.0 # Positive slope = score 1
  trin_regime:
    window_minutes: 30
    chop_band: [0.9, 1.1] # Inside band = score 0, outside = score 1
  vwap_cross:
    window_bars_5m: 12 # 1 hour of 5-min bars
    max_crosses: 4 # >4 = instrument in chop

# ── MFE/MAE analysis (raw mode) ──
mfe_mae:
  forward_horizons_minutes: [5, 15, 30, 60, 120]
  max_forward_bars_1m: 120 # Track up to 2 hours forward
  normalize_by: "atr" # "atr", "points", "dollars"
  atr_period: 14
  atr_timeframe: "5min"

# ── Optimization ──
optimization:
  n_trials: 200
  n_jobs: 1
  primary_metric: "prop_pass_rate" # For portfolio mode
  secondary_metrics: ["calmar", "profit_factor", "win_rate"]
  walk_forward:
    train_days: 504 # ~2 years of trading days
    test_days: 126 # ~6 months
    step_days: 63 # ~3 months
    embargo_bars: 120 # 2 hours at 1-min
  monte_carlo:
    n_simulations: 10000
    eval_days: 30 # Simulated eval period
```

### File: `scripts/trading_framework/config/config_loader.py`

```python
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


def load_config(path: str = \"scripts/trading_framework/config/sessions.yaml\") -> AppConfig:
    """Load YAML config and return a validated AppConfig instance.

    Steps:
    1. Read YAML file
    2. Parse each section into its typed dataclass
    3. Validate cross-field constraints (e.g., weekly_drawdown_limit < trailing_drawdown)
    4. Return frozen AppConfig

    Raises ValueError on invalid config.
    """
    with open(path) as f:
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
```

---

## 4. LIBRARY: Data Layer

**Module: `scripts/libs_py/data/loader.py`**

**Purpose:** Load parquet files, merge price + internals, compute derived series.
Reusable by any strategy.

```python
"""
Data loading and merging.

Usage:
    from scripts.libs_py.data.loader import DataLoader
    loader = DataLoader(config)
    df = loader.load_enriched("MES")  # Returns 1-min DataFrame with all features
"""
from dataclasses import dataclass
from pathlib import Path
import pandas as pd
from scripts.trading_framework.config.config_loader import AppConfig


@dataclass
class DataLoader:
    """
    Loads and merges price + internals parquet files into a single enriched DataFrame.

    Attributes:
        config: AppConfig instance
        _cache: dict — caches loaded DataFrames to avoid re-reading

    Methods:
        load_price(symbol: str) -> pd.DataFrame
            Load a single price parquet. Returns DataFrame indexed by datetime
            with columns: open, high, low, close, volume.
            Filter to config.date_start / config.date_end.
            Validate: no duplicate indices, datetime is tz-aware US/Eastern,
            columns are numeric, no all-NaN rows.

        load_internals() -> dict[str, pd.DataFrame]
            Load all internals symbols. Returns dict keyed by symbol name.
            Each DataFrame has datetime index and 'close' column (rename 'close'
            to the symbol name for merging).

        compute_vold(uvol: pd.DataFrame, dvol: pd.DataFrame) -> pd.Series
            Return UVOL.close - DVOL.close as a Series named "VOLD".

        merge_all(price_symbol: str) -> pd.DataFrame
            1. Load price DataFrame for the given symbol
            2. Load all internals
            3. Compute VOLD from UVOL and DVOL
            4. Left-join all internals onto price DataFrame by datetime index
            5. Forward-fill internals (they may have gaps during pre/post market)
            6. Add column "VOLD" from compute_vold
            7. Return the merged DataFrame

        load_enriched(symbol: str) -> pd.DataFrame
            1. Call merge_all(symbol)
            2. Call session_tagger.tag_sessions(df)
            3. Call resampler to create 5-min OHLCV columns (prefixed "5m_")
            4. Return fully enriched DataFrame ready for feature computation
    """
    config: AppConfig
    _cache: dict = None

    def __post_init__(self):
        self._cache = {}
```

**Module: `scripts/libs_py/data/session_tagger.py`**

```python
"""
Tag each bar with session labels.

Usage:
    from scripts.libs_py.data.session_tagger import tag_sessions
    df = tag_sessions(df, config.sessions)
"""

def tag_sessions(df: pd.DataFrame, sessions: "SessionConfig") -> pd.DataFrame:
    """
    Add columns to the DataFrame:

    - "session": categorical — one of "pre_market", "rth", "post_market"
    - "session_block": categorical — one of:
        "pre_market", "ib" (9:30-10:30), "ny_am" (10:30-11:00),
        "lunch" (11:00-13:30), "ny_pm" (13:30-16:00), "post_market"
    - "is_rth": bool
    - "trading_date": date — the trading date this bar belongs to.
        Bars before 9:30 belong to today's session if after midnight,
        or previous session if before midnight (handle ETH).
    - "minutes_into_session": int — minutes since RTH open (9:30)
    - "bars_into_session_1m": int — bar count since RTH open

    Implementation:
    - Use df.index.time for time comparisons
    - Parse session times from SessionConfig into datetime.time objects
    - Assign labels using pd.cut or boolean masks
    - trading_date assignment: group bars into sessions accounting for
      overnight/ETH. For RTH-only analysis, filter where is_rth == True.

    Returns: df with new columns added (not a copy — modifies in place and returns).
    """
```

**Module: `scripts/libs_py/data/resampler.py`**

```python
"""
Resample 1-minute bars to higher timeframes.

Usage:
    from scripts.libs_py.data.resampler import resample_ohlcv
    df_5m = resample_ohlcv(df, "5min")
"""

def resample_ohlcv(df: pd.DataFrame, freq: str) -> pd.DataFrame:
    """
    Resample 1-min OHLCV to the given frequency.

    Args:
        df: DataFrame with open, high, low, close, volume columns and datetime index
        freq: pandas frequency string ("5min", "15min", "30min", "1h")

    Returns:
        Resampled DataFrame with same column names.
        Uses standard OHLCV aggregation: first open, max high, min low, last close, sum volume.
        Only includes bars where at least 1 source bar existed (no empty resampled bars).

    Note: Resampling should respect session boundaries — do not merge bars across
    session breaks. Use the trading_date + session columns if available.
    """

def add_resampled_columns(df_1m: pd.DataFrame, freq: str, prefix: str) -> pd.DataFrame:
    """
    Resample and merge back onto the 1-min DataFrame as additional columns.

    Example: add_resampled_columns(df, "5min", "5m_") adds columns:
    5m_open, 5m_high, 5m_low, 5m_close, 5m_volume

    Each 1-min bar gets the value of the 5-min bar it belongs to.
    Uses forward-fill within each resampled period.
    """
```

---

## 5. LIBRARY: Feature Engine

All feature modules follow the same pattern: take a DataFrame, add columns, return it.
Features are computed lazily — only when requested by a strategy or analysis.

**Module: `scripts/libs_py/features/registry.py`**

```python
"""
Central feature registry. Strategies request features by name,
and the registry ensures they are computed exactly once.

Usage:
    from scripts.libs_py.features.registry import FeatureRegistry
    registry = FeatureRegistry(config)
    df = registry.ensure_features(df, ["vwap", "vwap_distance", "bb_pct_b",
                                        "ib_high", "ib_low", "chop_score"])
"""
from typing import Callable

class FeatureRegistry:
    """
    Attributes:
        config: AppConfig
        _computers: dict[str, Callable] — maps feature name to compute function
        _computed: set[str] — tracks which features have been computed on current df

    Methods:
        register(feature_name: str, compute_fn: Callable):
            Register a feature computation function.
            compute_fn signature: (df: pd.DataFrame, config: AppConfig) -> pd.DataFrame
            The function should add one or more columns to df and return it.

        ensure_features(df: pd.DataFrame, feature_names: list[str]) -> pd.DataFrame:
            For each requested feature, if not already computed, call its compute_fn.
            Handle dependencies: if feature "chop_score" depends on "tick_persistence"
            and "vold_slope", ensure those are computed first.
            Return df with all requested features as columns.

    Feature names and their modules:
        "vwap", "vwap_distance", "vwap_slope", "vwap_cross_count" → scripts/libs_py/features/vwap.py
        "bb_upper", "bb_lower", "bb_mid", "bb_pct_b", "bb_bandwidth" → scripts/libs_py/features/bollinger.py
        "kc_upper", "kc_lower", "kc_mid" → scripts/libs_py/features/keltner.py
        "ema_9", "ema_20", "ema_50", "ema_200" → scripts/libs_py/features/ema.py
        "atr_14", "atr_5m_14" → scripts/libs_py/features/atr.py
        "ib_high", "ib_low", "ib_mid", "ib_width", "ib_width_pctile" → scripts/libs_py/features/initial_balance.py
        "vold", "tick_persistence", "tick_zero_cross", "vold_slope",
            "trin_avg", "chop_score" → scripts/libs_py/features/internals.py, scripts/libs_py/features/chop.py
        "fast_move_detected", "single_print_level" → scripts/libs_py/features/auction.py
        "level_state" → scripts/libs_py/features/acceptance_rejection.py
    """
```

**Module: `scripts/libs_py/features/vwap.py`**

```python
"""
Session VWAP and derived features.

All functions take a DataFrame and config, add columns, return the DataFrame.
VWAP resets at each session open (9:30 ET).
"""

def compute_vwap(df: pd.DataFrame, config: "AppConfig") -> pd.DataFrame:
    """
    Compute session VWAP using the standard formula:
        cumulative(typical_price * volume) / cumulative(volume)
    where typical_price = (high + low + close) / 3

    Groups by trading_date to reset at each session.

    Adds columns:
        "vwap": the VWAP value
        "vwap_distance": (close - vwap) in points
        "vwap_distance_atr": (close - vwap) / atr_14 — ATR-normalized distance
        "vwap_slope": linear regression slope of VWAP over last 12 bars (5-min equivalent)
        "vwap_cross_count": rolling count of how many times close crossed VWAP
            in the last `config.chop.vwap_cross.window_bars_5m * 5` 1-min bars
        "above_vwap": bool — close > vwap
        "vwap_std_1": vwap + 1 stddev band (session rolling stddev of typical_price * volume)
        "vwap_std_neg1": vwap - 1 stddev band

    Requires: "atr_14" column (compute ATR first).
    Requires: "trading_date" column from session_tagger.
    """
```

**Module: `scripts/libs_py/features/initial_balance.py`**

```python
"""
Initial Balance computation.

The IB is the high-low range of the first N minutes of RTH (default: 60 min, 9:30-10:30).
"""

def compute_initial_balance(df: pd.DataFrame, config: "AppConfig") -> pd.DataFrame:
    """
    For each trading_date, compute:
        "ib_high": highest high during 9:30 to config.sessions.ib_end
        "ib_low": lowest low during that window
        "ib_mid": (ib_high + ib_low) / 2
        "ib_width": ib_high - ib_low (in points)
        "ib_width_pctile_20d": percentile rank of today's ib_width
            vs the last 20 trading days' ib_widths
        "ib_width_pctile_50d": same over 50 days
        "ib_bias": "bullish" if close at ib_end > ib_mid, else "bearish"
        "ib_ext_up_50": ib_high + 0.5 * ib_width (extension targets)
        "ib_ext_up_100": ib_high + 1.0 * ib_width
        "ib_ext_dn_50": ib_low - 0.5 * ib_width
        "ib_ext_dn_100": ib_low - 1.0 * ib_width
        "ib_formed": bool — True for all bars after ib_end on this trading_date
        "price_vs_ib": categorical — "above_ib", "inside_ib", "below_ib"

    IB values are NaN for bars before ib_end.
    After ib_end, all bars on that trading_date carry the same IB values.

    The percentile computation must be strictly causal — only use IB widths
    from prior completed sessions (not the current day).
    """
```

**Module: `scripts/libs_py/features/internals.py`**

```python
"""
Market internals features derived from TICK, UVOL, DVOL, TRIN data.
"""

def compute_internals_features(df: pd.DataFrame, config: "AppConfig") -> pd.DataFrame:
    """
    Requires columns: TICK, TICKQ, UVOL, DVOL, TRIN, TRINQ, ADV
    (merged from internals parquet files via DataLoader).

    Adds columns:
        "vold": UVOL - DVOL (if not already present)
        "tick_abs": abs(TICK)
        "tick_persistence": rolling mean of tick_abs over
            config.chop.tick_persistence.window_minutes * 1 bars (1-min)
            High values (400+) = trending. Low (100-200) = chop.
        "tick_zero_cross": rolling count of TICK sign changes over
            the same window. High count = chop.
        "vold_slope": linear regression slope of vold from session open
            to current bar. Computed per trading_date.
            Positive = volume flowing into advancers. Negative = decliners.
        "trin_avg": rolling mean of TRIN over
            config.chop.trin_regime.window_minutes bars.
        "trin_in_chop_band": bool — trin_avg is between
            config.chop.trin_regime.chop_band[0] and chop_band[1]

    All rolling computations are strictly causal (no lookahead).
    NaN for bars before enough history exists for the rolling window.
    """
```

**Module: `scripts/libs_py/features/chop.py`**

```python
"""
Composite chop score combining market internals signals.
"""

def compute_chop_score(df: pd.DataFrame, config: "AppConfig") -> pd.DataFrame:
    """
    Requires columns: tick_persistence, vold_slope, trin_avg, vwap_cross_count
    (from internals.py and vwap.py).

    Adds columns:
        "chop_tick_score": int 0-2
            0 if tick_persistence < config.chop.tick_persistence.thresholds[0]
            1 if between thresholds[0] and thresholds[1]
            2 if > thresholds[1]
        "chop_vold_score": int 0-1
            1 if abs(vold_slope) > config.chop.vold_slope.threshold
            0 otherwise
        "chop_trin_score": int 0-1
            1 if trin_avg outside config.chop.trin_regime.chop_band
            0 if inside (balanced = chop)
        "chop_score": int 0-4 — sum of the above three
        "chop_vwap_flag": bool — True if vwap_cross_count > config.chop.vwap_cross.max_crosses
            (instrument-level chop, independent of internals)
        "chop_regime": categorical —
            "trending" if chop_score >= 3
            "mixed" if chop_score == 2
            "choppy" if chop_score <= 1
    """
```

**Module: `scripts/libs_py/features/bollinger.py`**

```python
"""
Bollinger Band features. Configurable period and stddev multiplier.
"""

def compute_bollinger(df: pd.DataFrame, config: "AppConfig",
                      period: int = 20, std_mult: float = 2.0,
                      source: str = "close",
                      timeframe: str = "1min") -> pd.DataFrame:
    """
    Adds columns (prefixed by timeframe if not 1min):
        "bb_mid": SMA of source over period
        "bb_upper": bb_mid + std_mult * rolling std
        "bb_lower": bb_mid - std_mult * rolling std
        "bb_pct_b": (close - bb_lower) / (bb_upper - bb_lower)
            Values > 1.0 = above upper band. Values < 0.0 = below lower band.
        "bb_bandwidth": (bb_upper - bb_lower) / bb_mid
        "bb_bandwidth_pctile": rolling percentile rank of bb_bandwidth
            over the last 100 periods. Low = squeeze. High = expansion.
        "bb_zscore": (close - bb_mid) / rolling_std

    If timeframe is "5min", use the 5m_ prefixed OHLCV columns as source
    and prefix all output columns with "5m_bb_".
    """
```

**Module: `scripts/libs_py/features/keltner.py`**

```python
"""
Keltner Channel features.
"""

def compute_keltner(df: pd.DataFrame, config: "AppConfig",
                    ema_period: int = 20, atr_mult: float = 1.5,
                    atr_period: int = 14,
                    timeframe: str = "1min") -> pd.DataFrame:
    """
    Adds columns:
        "kc_mid": EMA of close over ema_period
        "kc_upper": kc_mid + atr_mult * ATR(atr_period)
        "kc_lower": kc_mid - atr_mult * ATR(atr_period)
        "kc_position": (close - kc_lower) / (kc_upper - kc_lower)

    If timeframe is "5min", prefix with "5m_kc_".
    """
```

**Module: `scripts/libs_py/features/ema.py`**

```python
"""
EMA suite at standard periods.
"""

def compute_emas(df: pd.DataFrame, config: "AppConfig",
                 periods: list[int] = None,
                 timeframe: str = "1min") -> pd.DataFrame:
    """
    Default periods: [9, 20, 50, 200]

    Adds columns: "ema_9", "ema_20", "ema_50", "ema_200"
    Also adds:
        "ema_trend_aligned": bool — True if ema_9 > ema_20 > ema_50 (bullish)
            or ema_9 < ema_20 < ema_50 (bearish). False if mixed.
        "ema_trend_direction": "bullish", "bearish", or "mixed"
        "price_vs_ema20": (close - ema_20) / atr_14 — ATR-normalized distance

    If timeframe is "5min", prefix with "5m_".
    """
```

**Module: `scripts/libs_py/features/atr.py`**

```python
"""
ATR at multiple periods and timeframes.
"""

def compute_atr(df: pd.DataFrame, config: "AppConfig",
                period: int = 14,
                timeframe: str = "1min") -> pd.DataFrame:
    """
    Standard Wilder ATR.

    Adds column: "atr_{period}" (e.g., "atr_14")
    If timeframe is "5min", use 5m OHLC and prefix: "5m_atr_14"

    Also adds "atr_pctile_100": percentile rank of current ATR
    vs the last 100 bars of ATR. Useful for volatility regime.
    """
```

**Module: `scripts/libs_py/features/auction.py`**

```python
"""
Auction structure: fast move detection and single prints tracking.
"""

def compute_auction_features(df: pd.DataFrame, config: "AppConfig") -> pd.DataFrame:
    """
    Detects fast directional moves and marks their origins as single print levels.

    Adds columns:
        "roc_10bar": rate of change over last 10 1-min bars (percentage)
        "fast_move_detected": bool — True when abs(roc_10bar) exceeds threshold
            Default threshold: 0.15% for MES, 0.25% for MNQ (configurable)
        "fast_move_direction": "up", "down", or None
        "fast_move_origin": float — the price at the start of the fast move
            (the close 10 bars ago when fast_move_detected triggers)
        "single_print_levels": list[float] — running list of unfilled
            fast_move_origin levels from the current session.
            A level is "filled" when price revisits it (close crosses the level).
        "nearest_single_print": float — distance to nearest unfilled level
        "nearest_single_print_direction": "above" or "below"

    Single print levels reset each session.
    """
```

**Module: `scripts/libs_py/features/acceptance_rejection.py`**

```python
"""
UTILITY MODULE: Classify how price interacts with any given level.

This is NOT a feature that runs on the full DataFrame. Instead, it's a function
called by strategies when they want to evaluate a specific price level.

Usage:
    from scripts.libs_py.features.acceptance_rejection import classify_level_interaction
    state = classify_level_interaction(df, level=5400.0, lookback_bars=10)
"""
from enum import Enum


class LevelState(Enum):
    CLEAN_HOLD = "clean_hold"          # Price holds at level, no penetration
    SHARP_REJECT = "sharp_reject"      # Wick through level, close away (strong)
    SOFT_BOUNCE = "soft_bounce"        # Touches level, drifts away (weak)
    BREAK_CONFIRMED = "break_confirmed"  # 2+ closes through level
    TESTING = "testing"                # Price at level, no clear resolution
    NO_INTERACTION = "no_interaction"  # Price not near level


def classify_level_interaction(
    df: pd.DataFrame,
    level: float,
    lookback_bars: int = 10,
    proximity_atr_mult: float = 0.3,
    confirm_closes: int = 2
) -> LevelState:
    """
    Analyze the last `lookback_bars` bars relative to `level`.

    Logic:
    1. If price hasn't been within proximity_atr_mult * ATR of level → NO_INTERACTION
    2. Count bars with close above vs below level
    3. Check for wicks: bars where high > level but close < level (or vice versa)
    4. Classification:
        - SHARP_REJECT: wick through level on 1+ bars, all closes on the same side,
          wick size > 50% of bar range
        - CLEAN_HOLD: price approached level but all closes stay on one side,
          no significant wicks through
        - SOFT_BOUNCE: price touched level (within 0.1 * ATR), moved away,
          but without strong wick rejection
        - BREAK_CONFIRMED: `confirm_closes` or more consecutive closes on the
          opposite side of the level from where price approached
        - TESTING: mixed closes, price hovering around level

    Args:
        df: DataFrame with OHLC and atr_14 columns
        level: the price level to evaluate
        lookback_bars: how many recent bars to analyze
        proximity_atr_mult: how close price must be to "interact" with the level
        confirm_closes: how many consecutive closes needed for BREAK_CONFIRMED

    Returns: LevelState enum
    """


def classify_level_series(
    df: pd.DataFrame,
    level_column: str,
    lookback_bars: int = 10
) -> pd.Series:
    """
    Rolling version: for each bar, classify the interaction with the level
    specified in `level_column`. Returns a Series of LevelState values.

    Useful for tracking how price interacts with IB High, IB Low, PDH, PDL, etc.
    over the course of a session.
    """
```

---

## 6. LIBRARY: Risk Management

This is the most critical library. Three levels, fully modular, reusable by any strategy.

**Module: `scripts/libs_py/risk/risk_config.py`**

```python
"""
Shared dataclasses for risk management state.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import pandas as pd


class TradeDirection(Enum):
    LONG = "long"
    SHORT = "short"


class TradeStatus(Enum):
    PENDING = "pending"          # Signal generated, not yet entered
    OPEN = "open"                # Position is live
    PARTIAL = "partial"          # Partial exit taken, remainder open
    CLOSED = "closed"            # Fully exited
    VETOED = "vetoed"            # Rejected by risk manager


@dataclass
class Signal:
    """Generated by a strategy's signal module."""
    timestamp: pd.Timestamp
    strategy_name: str
    symbol: str
    direction: TradeDirection
    entry_price: float
    stop_price: float
    risk_points: float           # abs(entry_price - stop_price)
    risk_dollars: float          # risk_points * point_value * contracts
    context: dict                # Strategy-specific metadata (chop_score, regime, etc.)


@dataclass
class TradeRecord:
    """Complete record of a trade, filled in progressively as the trade evolves."""
    signal: Signal
    status: TradeStatus = TradeStatus.PENDING
    entry_time: Optional[pd.Timestamp] = None
    entry_fill_price: Optional[float] = None
    # Partial exit
    partial_exit_time: Optional[pd.Timestamp] = None
    partial_exit_price: Optional[float] = None
    partial_exit_pct: Optional[float] = None
    # Final exit
    exit_time: Optional[pd.Timestamp] = None
    exit_fill_price: Optional[float] = None
    exit_reason: Optional[str] = None  # "stop", "target", "trail", "time_stop", "flatten", "session_risk"
    # P&L
    realized_pnl: float = 0.0
    # Analytics
    mae_points: float = 0.0     # Maximum adverse excursion during trade
    mfe_points: float = 0.0     # Maximum favorable excursion during trade
    bars_in_trade: int = 0
    policy_name: str = ""       # Which trade management policy was used


@dataclass
class SessionState:
    """Tracks session-level risk state. Reset at each session open."""
    trading_date: Optional[pd.Timestamp] = None
    trade_count: int = 0
    consecutive_losers: int = 0
    session_pnl: float = 0.0
    is_paused: bool = False
    pause_until: Optional[pd.Timestamp] = None
    is_stopped_for_day: bool = False
    open_position: Optional[TradeRecord] = None
    trades: list = field(default_factory=list)


@dataclass
class AccountState:
    """Tracks account-level state across sessions."""
    equity: float = 50000.0
    high_water_mark: float = 50000.0   # EOD trailing — updates at session close
    peak_equity: float = 50000.0
    trailing_drawdown_remaining: float = 2000.0
    weekly_pnl: float = 0.0
    weekly_start_equity: float = 50000.0
    is_in_observation: bool = False
    is_blown: bool = False             # Trailing drawdown breached
    days_traded: int = 0
    daily_pnls: list = field(default_factory=list)
```

**Module: `scripts/libs_py/risk/trade_policies.py`**

```python
"""
PLUGGABLE trade management policies.

Each policy is a class implementing the TradePolicy interface.
The backtest engine calls policy.manage() on each bar while a trade is open.
The policy decides: do nothing, take partial, move stop, exit fully.

Usage:
    from scripts.libs_py.risk.trade_policies import get_policy
    policy = get_policy("cover_the_queen", config.trade_risk_policies["cover_the_queen"])
    action = policy.manage(trade, current_bar, bars_since_entry)
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class PolicyAction(Enum):
    HOLD = "hold"                      # Do nothing
    TAKE_PARTIAL = "take_partial"      # Exit partial_pct at current price
    MOVE_STOP = "move_stop"            # Move stop to new_stop_price
    EXIT_FULL = "exit_full"            # Exit entire remaining position
    TAKE_PARTIAL_AND_MOVE_STOP = "take_partial_and_move_stop"


@dataclass
class PolicyDecision:
    action: PolicyAction
    partial_pct: Optional[float] = None       # For TAKE_PARTIAL
    new_stop_price: Optional[float] = None    # For MOVE_STOP
    exit_reason: Optional[str] = None         # For EXIT_FULL


class TradePolicy(ABC):
    """Abstract base class for trade management policies."""

    @abstractmethod
    def manage(self, trade: "TradeRecord", current_bar: dict,
               bars_since_entry: int) -> PolicyDecision:
        """
        Called on every bar while the trade is open.

        Args:
            trade: current TradeRecord (has entry_price, stop_price, direction, etc.)
            current_bar: dict with keys: open, high, low, close, volume, datetime,
                         atr_14 (and any other features on the bar)
            bars_since_entry: int

        Returns: PolicyDecision indicating what to do.
        """
        ...

    @abstractmethod
    def reset(self):
        """Reset internal state for a new trade."""
        ...


class CoverTheQueen(TradePolicy):
    """
    Phase 1: When trade reaches partial_target_rr * risk, take partial_exit_pct off.
             Move stop to breakeven.
    Phase 2: Trail remainder using trail_method.

    Config params (from YAML):
        partial_exit_pct: float (0.5)
        partial_target_rr: float (1.0)
        remainder_trail_method: str ("atr", "structure", "fixed")
        trail_atr_multiplier: float (2.0)
        trail_atr_period: int (14)
        move_stop_to_breakeven: bool (True)

    Internal state:
        _partial_taken: bool
        _trailing_stop: Optional[float]

    manage() logic:
        1. Compute current R-multiple: (current_price - entry) / risk for longs
        2. If not _partial_taken and R-multiple >= partial_target_rr:
            → TAKE_PARTIAL_AND_MOVE_STOP (partial_pct, new_stop = entry_price)
            → set _partial_taken = True
        3. If _partial_taken:
            Update trailing stop:
              - ATR method: for longs, trail = max(trail, close - trail_atr_multiplier * atr)
              - Structure method: for longs, trail = most recent swing low on 5-min
              - Fixed method: trail = entry_price (breakeven only, no trail)
            If current low (longs) or high (shorts) crosses trailing stop:
              → EXIT_FULL
            Else:
              → MOVE_STOP(new_stop=trailing_stop)
        4. Check base stop: if price hits original stop (before partial) → EXIT_FULL
        5. Default: HOLD
    """


class FixedTarget(TradePolicy):
    """
    Exit 100% at target_rr * risk.
    Stop at original stop.

    Config: target_rr (float)
    """


class ScaledExit(TradePolicy):
    """
    Multiple partial exits at specified R-multiples.

    Config: exits — list of {pct: float, target_rr: float} or
            {pct: float, trail: True, trail_atr_multiplier: float}

    Internal state: _exits_taken (list of bools), _trailing_stop for the last tranche.

    manage() logic:
        For each exit in config.exits (in order):
            If not yet taken and R-multiple >= target_rr:
                → TAKE_PARTIAL(pct)
        For the last tranche (if trail=True):
            Apply ATR trailing stop logic.
    """


class BreakevenTrail(TradePolicy):
    """
    Move stop to breakeven at breakeven_trigger_rr.
    Then trail with ATR multiplier.
    No partial exits.

    Config: breakeven_trigger_rr, trail_atr_multiplier
    """


class TimeStop(TradePolicy):
    """
    Wraps another policy. If max_bars reached and trade still open,
    exit the remainder (or full position if applies_to == "full").

    Config: max_bars, applies_to ("full" or "remainder")
    """


def get_policy(name: str, params: dict) -> TradePolicy:
    """
    Factory function. Returns the appropriate TradePolicy instance
    based on name and params from config.

    Supported names: "cover_the_queen", "fixed_target", "scaled_exit",
                     "breakeven_trail", "time_stop"

    For "time_stop", wraps the default policy specified in config.
    """
```

**Module: `scripts/libs_py/risk/session_manager.py`**

```python
"""
Session-level risk manager. Strategy-AGNOSTIC.

It does not know or care which strategy is requesting a trade.
It only sees: "a trade request with X risk dollars" and approves/denies
based on the current session state.

Usage:
    from scripts.libs_py.risk.session_manager import SessionRiskManager
    mgr = SessionRiskManager(config.session_risk, config.sessions)
    approved = mgr.request_entry(signal)  # True/False
    mgr.record_trade_result(trade_record)
    mgr.on_session_open(trading_date)
"""

class SessionRiskManager:
    """
    Attributes:
        config: SessionRiskConfig
        sessions: SessionConfig
        state: SessionState

    Methods:
        on_session_open(trading_date: pd.Timestamp):
            Reset session state for a new trading day.
            Set trade_count = 0, consecutive_losers = 0, session_pnl = 0,
            is_paused = False, is_stopped_for_day = False.

        request_entry(signal: Signal, current_time: pd.Timestamp) -> bool:
            Returns True if the trade is approved, False if vetoed.
            Check ALL of these (reject if any fail):
            1. is_stopped_for_day == False
            2. is_paused == False (or current_time > pause_until)
            3. trade_count < config.max_trades_per_day
            4. open_position is None (no concurrent position) OR
               config.max_concurrent_positions > count of open positions
            5. current_time >= sessions.rth_start
            6. current_time <= sessions.last_entry
            7. session_pnl + signal.risk_dollars > -config.daily_max_loss
               (taking this trade wouldn't immediately breach daily max loss
                even if it's a full loser)
            If rejected, log the reason.

        record_trade_result(trade: TradeRecord):
            Update session state after a trade closes:
            1. session_pnl += trade.realized_pnl
            2. trade_count += 1
            3. If trade was a loser: consecutive_losers += 1
               If winner: consecutive_losers = 0
            4. If consecutive_losers >= config.max_consecutive_losers:
               is_paused = True, pause_until = current_time + pause_minutes
            5. If consecutive_losers >= config.hard_stop_consecutive_losers:
               is_stopped_for_day = True
            6. If session_pnl <= -config.daily_max_loss:
               is_stopped_for_day = True (also flatten any open position)
            7. Append trade to self.state.trades

        check_flatten(current_time: pd.Timestamp) -> bool:
            Returns True if all positions should be flattened:
            - current_time >= sessions.flatten_by
            - session_pnl <= -config.daily_max_loss

        get_session_summary() -> dict:
            Return summary stats: trade_count, winners, losers, session_pnl,
            max_consecutive_losers, trades list.
    """
```

**Module: `scripts/libs_py/risk/account_manager.py`**

```python
"""
Account-level risk manager. Tracks equity across sessions.

Usage:
    from scripts.libs_py.risk.account_manager import AccountRiskManager
    acct = AccountRiskManager(config.account_risk)
    acct.on_session_close(daily_pnl)
    can_trade = acct.can_trade_today()
"""

class AccountRiskManager:
    """
    Attributes:
        config: AccountRiskConfig
        state: AccountState

    Methods:
        on_session_close(daily_pnl: float):
            1. state.equity += daily_pnl
            2. state.daily_pnls.append(daily_pnl)
            3. state.days_traded += 1
            4. EOD trailing drawdown update:
               If trailing_type == EOD:
                 state.high_water_mark = max(state.high_water_mark, state.equity)
                 state.trailing_drawdown_remaining = (
                     state.high_water_mark - state.equity
                     < config.trailing_drawdown)
                 If state.equity < state.high_water_mark - config.trailing_drawdown:
                     state.is_blown = True
            5. Weekly tracking:
               state.weekly_pnl += daily_pnl
               If weekly_pnl <= -config.weekly_drawdown_limit:
                   state.is_in_observation = True

        on_week_start():
            state.weekly_pnl = 0.0
            state.weekly_start_equity = state.equity
            state.is_in_observation = False

        can_trade_today() -> bool:
            Return False if:
            - state.is_blown (account failed)
            - state.is_in_observation and config.weekly_action == "observation"

        has_passed_eval() -> bool:
            Return True if:
            - state.equity >= config.starting_equity + config.profit_target
            - state.is_blown == False

        get_equity_curve() -> pd.Series:
            Return cumulative equity as a time series from daily_pnls.

        get_account_summary() -> dict:
            Return: current equity, high_water_mark, drawdown_remaining,
            days_traded, is_blown, has_passed, weekly_pnl.
    """
```

---

## 7. LIBRARY: Backtest Engine

**Module: `scripts/trading_framework/core/execution.py`**

```python
"""
Execution model: slippage and commission.
"""

def apply_slippage(price: float, direction: "TradeDirection",
                   tick_size: float, slippage_ticks: int) -> float:
    """
    Apply slippage to a fill price.
    For entries: longs get filled higher, shorts get filled lower.
    For exits: longs get filled lower, shorts get filled higher.

    Returns adjusted price.
    """

def compute_commission(contracts: int, per_contract: float) -> float:
    """Round-trip commission."""
    return contracts * per_contract

def compute_pnl(entry_price: float, exit_price: float,
                direction: "TradeDirection", contracts: int,
                point_value: float, commission: float) -> float:
    """
    Compute realized P&L in dollars.
    For longs: (exit - entry) * contracts * point_value - commission
    For shorts: (entry - exit) * contracts * point_value - commission
    """
```

**Module: `scripts/trading_framework/core/mfe_mae.py`**

```python
"""
MFE/MAE analysis on RAW (unmanaged) signals.

This module runs in "raw" risk mode. It takes every signal generated by a strategy,
then walks forward through the 1-min price data recording the full price path.
No stops, no targets, no exits — just observation.

Usage:
    from scripts.trading_framework.core.mfe_mae import compute_mfe_mae
    results = compute_mfe_mae(signals, df_1m, config)
"""

@dataclass
class MfeMaeResult:
    """Per-signal MFE/MAE analysis result."""
    signal: "Signal"
    mfe_points: list[float]           # MFE at each forward bar
    mae_points: list[float]           # MAE at each forward bar
    mfe_atr: list[float]              # MFE normalized by ATR
    mae_atr: list[float]              # MAE normalized by ATR
    forward_returns: dict[int, float] # {horizon_minutes: return_points}
    mfe_peak_bar: int                 # Bar where MFE was highest
    mae_trough_bar: int               # Bar where MAE was deepest
    time_to_1r: Optional[int]         # Bars to reach 1x risk (None if never)
    time_to_2r: Optional[int]         # Bars to reach 2x risk
    reached_1r: bool
    reached_2r: bool
    path: list[float]                 # Full close price path (for visualization)


def compute_mfe_mae(signals: list["Signal"],
                    df_1m: pd.DataFrame,
                    config: "AppConfig") -> list[MfeMaeResult]:
    """
    For each signal:
    1. Find the entry bar in df_1m by timestamp
    2. Walk forward bar by bar for config.mfe_mae.max_forward_bars_1m bars
    3. At each bar, compute:
       - MFE: max favorable price move from entry
         (for longs: max(high) - entry; for shorts: entry - min(low))
       - MAE: max adverse price move from entry
         (for longs: entry - min(low); for shorts: max(high) - entry)
    4. Record the full path and compute forward returns at each horizon
    5. Normalize by ATR if config.mfe_mae.normalize_by == "atr"
    6. Track time-to-R-multiple milestones

    Returns list of MfeMaeResult, one per signal.

    CRITICAL: This uses raw price paths with NO trade management.
    The purpose is to understand the true distribution of price movement
    after each signal, which then informs stop/target/partial placement.
    """


def summarize_mfe_mae(results: list[MfeMaeResult]) -> dict:
    """
    Aggregate statistics across all signals:
    - MFE distribution: P10, P25, P50, P75, P90 (in ATR and points)
    - MAE distribution: P10, P25, P50, P75, P90
    - Percentage reaching 1R, 2R, 3R
    - Average time to 1R for signals that reach it
    - MAE distribution on signals that eventually reach 2R MFE
      (i.e., "how much heat do big winners take?")
    - Optimal stop placement: the MAE level that maximizes
      (trades kept * avg MFE of kept trades) — this is the stop that
      maximizes total expected profit
    - Optimal partial exit level: MFE level where >60% of trades have reached
    """
```

**Module: `scripts/trading_framework/core/engine.py`**

```python
"""
Core backtest engine. Processes signals through trade management.

Active in "strategy" and "portfolio" risk modes.

Usage:
    from scripts.trading_framework.core.engine import BacktestEngine
    engine = BacktestEngine(config)
    results = engine.run(signals, df_1m)
"""

@dataclass
class BacktestResult:
    trades: list["TradeRecord"]
    equity_curve: pd.Series          # Cumulative P&L over time
    daily_pnl: pd.Series             # Daily P&L
    metrics: dict                     # Summary statistics


class BacktestEngine:
    """
    Attributes:
        config: AppConfig
        policy: TradePolicy (from get_policy)
        execution: execution module functions

    Methods:
        run(signals: list[Signal], df_1m: pd.DataFrame) -> BacktestResult:
            For each signal (sorted by timestamp):
            1. Apply slippage to entry price
            2. Create TradeRecord
            3. Walk forward bar by bar:
               a. Update MAE/MFE on the trade
               b. Check if stop is hit (high/low crosses stop):
                  - Yes → exit, apply slippage, record P&L
               c. Call policy.manage(trade, current_bar, bars_since_entry)
               d. Process PolicyDecision:
                  - TAKE_PARTIAL → record partial exit, reduce position
                  - MOVE_STOP → update stop price
                  - EXIT_FULL → exit, apply slippage, record P&L
                  - HOLD → continue
            4. If bar reaches flatten_by time → force exit
            5. After trade closes, record final TradeRecord
            6. Compute commission on all fills
            7. Policy.reset() for next trade

            Returns BacktestResult with all trades, equity curve, and metrics.

        _simulate_trade(signal, df_1m, start_idx) -> TradeRecord:
            Internal method that processes a single trade.

        _compute_metrics(trades: list[TradeRecord]) -> dict:
            Compute: total_pnl, win_rate, avg_win, avg_loss, profit_factor,
            max_consecutive_losers, max_drawdown, sharpe (annualized from daily),
            calmar, expectancy_per_trade, avg_bars_in_trade, avg_mae, avg_mfe.
    """
```

**Module: `scripts/trading_framework/core/portfolio_sim.py`**

```python
"""
Multi-strategy portfolio simulator with session and account risk.

Active in "portfolio" risk mode.

Usage:
    from scripts.trading_framework.core.portfolio_sim import PortfolioSimulator
    sim = PortfolioSimulator(config)
    result = sim.run(strategy_signals_dict, df_1m)
"""

@dataclass
class PortfolioResult:
    per_strategy_results: dict[str, "BacktestResult"]
    combined_trades: list["TradeRecord"]
    combined_equity_curve: pd.Series
    combined_daily_pnl: pd.Series
    session_summaries: list[dict]      # Per-day summary
    account_summary: dict
    prop_eval_passed: bool
    days_to_pass: Optional[int]


class PortfolioSimulator:
    """
    Attributes:
        config: AppConfig
        session_mgr: SessionRiskManager
        account_mgr: AccountRiskManager
        engines: dict[str, BacktestEngine] — one per strategy, each with its own policy

    Methods:
        run(strategy_signals: dict[str, list[Signal]],
            df_1m: pd.DataFrame) -> PortfolioResult:

            1. Merge all signals across strategies into a single time-sorted list
            2. Group by trading_date
            3. For each trading day:
               a. session_mgr.on_session_open(date)
               b. If not account_mgr.can_trade_today(): skip day
               c. Process signals in chronological order:
                  - For each signal, call session_mgr.request_entry(signal)
                  - If approved: run the trade through its strategy's BacktestEngine
                    (but bar-by-bar, so we can check session flatten rules)
                  - After trade closes: session_mgr.record_trade_result(trade)
                  - Check session_mgr.check_flatten() after each bar
               d. At session close: compute daily_pnl, call account_mgr.on_session_close()
               e. Check account_mgr.has_passed_eval() → if True, stop simulation
               f. If account_mgr.state.is_blown → stop simulation
            4. If new week: account_mgr.on_week_start()
            5. Compile results

        Strategy priority is handled by signal ordering: IB strategy signals
        from 9:30-10:30 come first. Other strategies generate signals with
        timestamps after 10:00. The session_mgr's max_concurrent_positions = 1
        naturally enforces "one trade at a time."
    """
```

---

## 8. LIBRARY: Regime Detection

**Module: `scripts/libs_py/regime/base.py`**

```python
"""
Abstract interface for regime detection models.
All regime models implement this interface.
"""
from abc import ABC, abstractmethod
import pandas as pd
import numpy as np


class RegimeModel(ABC):
    """
    Interface:
        fit(df: pd.DataFrame) -> self
            Train/calibrate on historical data.

        predict(df: pd.DataFrame) -> pd.Series
            Return regime labels for each bar. Labels are strings:
            "mean_reverting", "trending", "coiled", "high_volatility", etc.
            Must be strictly causal (only use data up to the current bar).

        predict_proba(df: pd.DataFrame) -> pd.DataFrame
            Return probability of each regime at each bar.
            Columns are regime names, values are probabilities summing to 1.

        get_params() -> dict
            Return model parameters for serialization.

        set_params(params: dict) -> self
            Restore model from serialized parameters.
    """

    @abstractmethod
    def fit(self, df: pd.DataFrame) -> "RegimeModel": ...

    @abstractmethod
    def predict(self, df: pd.DataFrame) -> pd.Series: ...

    @abstractmethod
    def predict_proba(self, df: pd.DataFrame) -> pd.DataFrame: ...

    @abstractmethod
    def get_params(self) -> dict: ...

    @abstractmethod
    def set_params(self, params: dict) -> "RegimeModel": ...
```

Implementations in `scripts/libs_py/regime/threshold.py`, `hmm.py`, `clustering.py`, `ensemble.py`
follow the same interface. See the v2 framework plan document for detailed specifications
of each model (HMM state-to-label mapping, clustering approach, ensemble voting).

---

## 9. LIBRARY: Reporting

**Module: `scripts/trading_framework/reporting/tearsheet.py`**

```python
"""
Generate performance tearsheets from BacktestResult or PortfolioResult.

Usage:
    from scripts.trading_framework.reporting.tearsheet import generate_tearsheet
    report = generate_tearsheet(result, output_dir="reports/")
"""

def generate_tearsheet(result: "BacktestResult",
                       output_dir: str = "reports/",
                       benchmark: pd.Series = None) -> dict:
    """
    Produce a comprehensive HTML tearsheet with:
    - Summary metrics table (total PnL, Sharpe, Sortino, Calmar, max DD, win rate,
      profit factor, expectancy, avg winner, avg loser, max consecutive losers)
    - Equity curve with drawdown overlay (matplotlib or plotly)
    - Monthly returns heatmap
    - P&L distribution histogram
    - Trade duration histogram
    - Rolling 30-day Sharpe
    - Win rate by: session_block, day_of_week, month, chop_regime
    - If benchmark provided: correlation, relative performance

    Save as HTML to output_dir.
    Return dict of all computed metrics.
    """
```

**Module: `scripts/trading_framework/reporting/conditional_tables.py`**

```python
"""
Generate grouped statistical tables.

Usage:
    from scripts.trading_framework.reporting.conditional_tables import build_conditional_table
    table = build_conditional_table(trades, group_by=["session_block", "chop_regime"])
"""

def build_conditional_table(
    trades: list["TradeRecord"],
    group_by: list[str],
    min_observations: int = 30
) -> pd.DataFrame:
    """
    Group trades by the specified context fields and compute per-group:
    - count
    - win_rate
    - avg_pnl (dollars and ATR-normalized)
    - median_pnl
    - avg_mfe_atr, avg_mae_atr
    - profit_factor
    - expectancy
    - max_consecutive_losers
    - sharpe (if enough trades)

    Flag groups with fewer than min_observations.

    group_by values reference fields in trade.signal.context dict.
    Common groupings: "session_block", "chop_regime", "direction",
    "strategy_name", "day_of_week", "vix_regime", "ib_width_bucket".
    """
```

**Module: `scripts/trading_framework/reporting/mfe_mae_report.py`**

```python
"""
Visualize MFE/MAE analysis results.
"""

def generate_mfe_mae_report(results: list["MfeMaeResult"],
                            output_dir: str = "reports/") -> None:
    """
    Produce visualizations:
    1. MFE distribution histogram (ATR-normalized) with P25/P50/P75 lines
    2. MAE distribution histogram with P25/P50/P75 lines
    3. MFE vs MAE scatter plot (each dot is a trade)
       Color by winner/loser based on a reference R-multiple
    4. Average MFE path over time (bar-by-bar average across all signals)
    5. Average MAE path over time
    6. "Profit landscape" heatmap: for each (stop_level, target_level) pair,
       compute the resulting expectancy. Shows optimal stop/target zone.
    7. Time-to-R-multiple CDF: what % of trades reach 1R by bar N?
    8. MAE distribution ONLY for trades that eventually reach 2R MFE
       (shows how much heat winners take — informs stop placement)

    Save all as PNG and HTML to output_dir.
    """
```

**Module: `scripts/trading_framework/reporting/chop_filter_report.py`**

```python
"""
Analyze chop filter effectiveness.
"""

def generate_chop_filter_report(
    trades_unfiltered: list["TradeRecord"],
    trades_filtered: list["TradeRecord"],
    output_dir: str = "reports/"
) -> dict:
    """
    Compare unfiltered vs filtered trade populations:
    - Trades eliminated count and percentage
    - Win rate: before vs after filtering
    - Avg P&L: before vs after
    - Profit factor: before vs after
    - False positive rate: % of eliminated trades that would have been winners
    - False negative rate: % of chop trades that got through
    - Breakdown by chop_score level (0, 1, 2, 3, 4)
    - Time-of-day distribution of eliminated trades

    Return dict of comparison metrics. Save visualizations to output_dir.
    """
```

---

## 10. LIBRARY: ML / Optimization

**Module: `scripts/trading_framework/ml/optimizer.py`**

```python
"""
Optuna-based parameter optimization.

Usage:
    from scripts.trading_framework.ml.optimizer import StrategyOptimizer
    optimizer = StrategyOptimizer(pipeline_fn, config)
    study = optimizer.optimize()
"""
import optuna

class StrategyOptimizer:
    """
    Wraps Optuna with purged walk-forward CV.

    Attributes:
        pipeline_fn: callable(params: dict, train_df, test_df) -> BacktestResult
            The function that runs the full pipeline for a given parameter set.
        config: AppConfig
        walk_forward_cv: PurgedWalkForwardCV instance

    Methods:
        objective(trial: optuna.Trial) -> float:
            1. Sample parameters from the search space using trial.suggest_*
            2. For each walk-forward fold:
               a. Split data into train/test
               b. Call pipeline_fn(params, train, test)
               c. Collect the metric (prop_pass_rate or sharpe)
               d. Report intermediate result for pruning
            3. Return mean metric across folds

        optimize(n_trials: int = None) -> optuna.Study:
            Create study with MedianPruner, run optimization.
            Return the study object for analysis.

        get_best_params() -> dict:
            Return the best trial's parameters.
    """
```

**Module: `scripts/trading_framework/ml/walk_forward.py`**

```python
"""
Purged walk-forward cross-validation.

Usage:
    from scripts.trading_framework.ml.walk_forward import PurgedWalkForwardCV
    cv = PurgedWalkForwardCV(config.optimization.walk_forward)
    for train_idx, test_idx in cv.split(df):
        ...
"""

class PurgedWalkForwardCV:
    """
    Generates train/test index pairs for walk-forward validation.

    Parameters (from WalkForwardConfig):
        train_days: number of trading days in training window
        test_days: number of trading days in test window
        step_days: how many days to advance between folds
        embargo_bars: number of bars to drop between train end and test start
            (prevents feature lookback from bleeding into test)

    Methods:
        split(df: pd.DataFrame) -> Iterator[tuple[np.ndarray, np.ndarray]]:
            Yields (train_indices, test_indices) pairs.

            1. Get unique trading_dates from df
            2. For each fold starting position (stepping by step_days):
               - train: dates[start : start + train_days]
               - embargo: skip embargo_bars worth of bars after train end
               - test: dates[start + train_days + embargo : ... + test_days]
            3. Convert date ranges to integer indices into df
            4. Yield (train_idx, test_idx)

        get_n_folds(df: pd.DataFrame) -> int:
            Return the number of folds for this dataset.
    """
```

**Module: `scripts/trading_framework/ml/prop_eval_mc.py`**

```python
"""
Monte Carlo simulation of prop firm evaluation pass rate.

Usage:
    from scripts.trading_framework.ml.prop_eval_mc import PropEvalMonteCarlo
    mc = PropEvalMonteCarlo(config.account_risk, config.optimization.monte_carlo)
    result = mc.simulate(daily_pnls)
"""

@dataclass
class MonteCarloResult:
    pass_rate: float                   # % of simulations that passed
    median_days_to_pass: Optional[float]
    mean_max_drawdown: float
    p95_max_drawdown: float
    risk_of_ruin: float                # % of simulations that blew the account
    distribution_of_final_equity: list[float]
    pass_rate_by_day: list[float]      # Cumulative pass rate over eval period


class PropEvalMonteCarlo:
    """
    Methods:
        simulate(daily_pnls: list[float]) -> MonteCarloResult:
            1. For each of n_simulations:
               a. Sample eval_days daily P&Ls with replacement
               b. Initialize equity = starting_equity, hwm = starting_equity
               c. Walk through sampled days:
                  - equity += daily_pnl
                  - At "EOD": hwm = max(hwm, equity)
                  - If equity < hwm - trailing_drawdown: blown = True, stop
                  - If equity >= starting_equity + profit_target: passed = True, stop
               d. Record: passed/blown/neither, days taken, max drawdown
            2. Aggregate across all simulations

        sensitivity_analysis(daily_pnls, drawdown_range, target_range) -> pd.DataFrame:
            Run simulate() for various drawdown and target levels.
            Returns a grid showing pass_rate at each combination.
            Useful for comparing different prop firm rules.
    """
```

**Module: `scripts/trading_framework/ml/leakage_guard.py`**

```python
"""
Automated data leakage detection.

Run this before any optimization or ML training.
"""

def check_feature_causality(df: pd.DataFrame, features: list[str]) -> list[str]:
    """
    For each feature, verify it is strictly causal:
    1. NaN at the start of the series (rolling lookback needs warmup)
    2. No correlation with future returns that exceeds correlation with past returns
       by a suspicious margin (> 2x)
    3. Feature at bar N does not change when bars N+1, N+2, ... are removed

    Returns list of suspicious feature names with explanations.
    """

def check_train_test_separation(train_idx, test_idx, embargo_bars: int,
                                 df: pd.DataFrame) -> bool:
    """
    Verify no overlap between train and test periods,
    and that the embargo gap is sufficient.
    """
```

---

## 11. STRATEGY: VWAP Reclaim/Rejection

**File: `scripts/strategies/vwap_reclaim/config.yaml`**

```yaml
strategy_name: "vwap_reclaim"
symbol: "MES" # or "MNQ"
trade_policy: "cover_the_queen" # Override default if needed

params:
  confirmation_bars: 2 # Consecutive closes above/below VWAP
  min_time_away_minutes: 15 # Price must be away from VWAP for this long
  proximity_atr_mult: 0.3 # "At VWAP" zone width
  min_rr: 1.5 # Minimum R:R to take the trade
  allowed_sessions: ["ib", "ny_am", "ny_pm"]
  time_start: "09:30"
  time_end: "14:30"

chop_filter:
  min_chop_score: 2 # Minimum composite chop score
  max_vwap_crosses: 4 # Suppress if VWAP is a revolving door
```

**File: `scripts/strategies/vwap_reclaim/signals.py`**

```python
"""
VWAP Reclaim/Rejection signal generator.

Implements the abstract strategy interface.
"""
from scripts.strategies.base import StrategyBase
from scripts.libs_py.risk.risk_config import Signal, TradeDirection


class VWAPReclaimStrategy(StrategyBase):
    """
    Required features: vwap, vwap_distance, vwap_cross_count, above_vwap,
                       atr_14, chop_score, chop_vwap_flag, session_block

    Signal logic:

    RECLAIM LONG:
        1. Price has been below VWAP for >= min_time_away_minutes
           (count consecutive bars where above_vwap == False)
        2. Price crosses above VWAP
        3. confirmation_bars consecutive 5-min closes above VWAP
        4. Entry on the close of the confirmation bar
        5. Stop: lowest low during the time below VWAP (or entry - max_stop_atr * ATR)
        6. Target: session high or bb_upper (whichever is closer)
        7. R:R check: (target - entry) / (entry - stop) >= min_rr

    RECLAIM SHORT:
        Mirror of above (price above VWAP, crosses below, confirms below)

    REJECTION LONG:
        1. Price approaches VWAP from below (within proximity_atr_mult * ATR)
        2. Bar wicks below VWAP but closes above
        3. Next bar also closes above VWAP
        4. Entry on close of confirmation bar
        5. Stop: below the wick low
        6. Target: session high or upper BB

    REJECTION SHORT:
        Mirror of above

    Filters (applied to all signals):
        - chop_score >= config.chop_filter.min_chop_score
        - chop_vwap_flag == False (VWAP cross count below threshold)
        - session_block in config.params.allowed_sessions
        - Current time between time_start and time_end

    Methods:
        generate_signals(df: pd.DataFrame) -> list[Signal]:
            Iterate through the DataFrame bar by bar.
            Track state: how long price has been above/below VWAP.
            When conditions are met, create a Signal.
            Apply filters. Return all signals (both approved and vetoed,
            with veto reason in context dict for analysis).
    """
```

---

## 12. STRATEGY: Initial Balance Breakout/Failure

**File: `scripts/strategies/ib_breakout/config.yaml`**

```yaml
strategy_name: "ib_breakout"
symbol: "MES"
trade_policy: "cover_the_queen"

params:
  narrow_pctile_threshold: 25 # Below this = narrow IB (trade breakout)
  wide_pctile_threshold: 75 # Above this = wide IB (trade fade)
  breakout_confirmation: "close" # "close" or "wick" through IB level
  max_ib_width_points: 5.0 # Skip if IB is too wide for risk budget
  extension_target_mult: 1.0 # Target at 1x IB range from breakout
  partial_target_mult: 0.5 # Cover-the-queen at 0.5x IB range
  only_first_breakout: true # Only trade the first breakout per direction
  time_start: "10:30" # After IB forms
  time_end: "14:00"

chop_filter:
  min_chop_score: 3 # Breakouts need strong conviction
```

**File: `scripts/strategies/ib_breakout/signals.py`**

```python
"""
Initial Balance Breakout / Failure signal generator.
"""

class IBBreakoutStrategy(StrategyBase):
    """
    Required features: ib_high, ib_low, ib_mid, ib_width, ib_width_pctile_20d,
                       ib_formed, atr_14, chop_score, session_block

    Signal logic:

    NARROW IB BREAKOUT (ib_width_pctile_20d < narrow_pctile_threshold):
        1. Wait for ib_formed == True
        2. LONG: close > ib_high (if breakout_confirmation == "close")
           or high > ib_high (if "wick")
        3. Entry: close of the breakout bar
        4. Stop: ib_low (opposite side) — but cap at max_ib_width_points
           If ib_width > max_ib_width_points, use ib_mid as stop instead
        5. Target: ib_high + extension_target_mult * ib_width
        6. SHORT: mirror below ib_low

    WIDE IB FADE (ib_width_pctile_20d > wide_pctile_threshold):
        1. Wait for price to break ib_high or ib_low
        2. Then wait for price to return back inside the IB range
           (close back below ib_high for failed long breakout)
        3. Entry: close of the bar that re-enters the IB range
        4. Stop: beyond the breakout extreme + 1 ATR
        5. Target: ib_mid

    MIDDLE IB (between thresholds):
        No signals generated.

    Filters:
        - chop_score >= min_chop_score (higher threshold for breakouts)
        - if only_first_breakout: track whether a breakout has already occurred
          per direction per session. Skip subsequent ones.
        - Time window: time_start to time_end
        - Skip if ib_width > max_ib_width_points AND using full-IB stop

    State tracking per session:
        - breakout_long_taken: bool
        - breakout_short_taken: bool
        - ib_high_broken: bool (for fade setup)
        - ib_low_broken: bool
    """
```

---

## 13. STRATEGY: EMA Pullback Continuation

**File: `scripts/strategies/ema_pullback/config.yaml`**

```yaml
strategy_name: "ema_pullback"
symbol: "MES"
trade_policy: "cover_the_queen"

params:
  min_initial_move_points: 4.0 # Minimum move from open before looking for pullback
  pullback_targets: ["vwap", "ema_20"] # Levels to watch for pullback
  confirmation_patterns: ["engulfing", "pin_bar", "inside_break"]
  min_rr: 1.5
  time_start: "09:45"
  time_end: "11:00"

chop_filter:
  min_chop_score: 3
  require_tick_direction_agreement: true # TICK must agree with trade direction
```

**File: `scripts/strategies/ema_pullback/signals.py`**

```python
"""
Trend continuation pullback signal generator.
"""

class EMAPullbackStrategy(StrategyBase):
    """
    Required features: vwap, ema_20, ema_50, atr_14, chop_score,
                       tick_persistence, session_block, ema_trend_direction

    Signal logic:

    PULLBACK LONG:
        1. Between time_start and time_end
        2. Price has moved > min_initial_move_points above the session open
           (high_since_open - open > min_initial_move_points)
        3. Price pulls back to one of pullback_targets:
           - "vwap": close is within 0.3 * ATR of VWAP
           - "ema_20": close is within 0.3 * ATR of ema_20
        4. Confirmation pattern on the pullback bar or next bar:
           - "engulfing": current bar's body engulfs previous bar's body,
             and closes in the trend direction
           - "pin_bar": lower wick > 2x body size, close in upper half of range
           - "inside_break": previous bar is inside bar, current bar breaks
             its high (for longs)
        5. Entry: close of the confirmation bar
        6. Stop: below the pullback low (lowest low of the pullback swing)
        7. Target: session high (the high that was reached before the pullback)

    PULLBACK SHORT:
        Mirror of above.

    Filters:
        - chop_score >= min_chop_score
        - If require_tick_direction_agreement: TICK persistence must be positive
          for longs (avg TICK > 0 over window) or negative for shorts
        - ema_trend_direction must match trade direction
        - Only 1 pullback trade per session
        - Time window
    """
```

---

## 14. STRATEGY: Failed Auction Fill

**File: `scripts/strategies/failed_auction/config.yaml`**

```yaml
strategy_name: "failed_auction"
symbol: "MES"
trade_policy: "cover_the_queen"

params:
  fast_move_roc_threshold: 0.15 # % ROC over 10 bars to qualify
  fast_move_min_points: 3.0 # Minimum absolute move
  fast_move_max_bars: 10 # Window for the fast move (1-min bars)
  max_time_to_fill_bars: 120 # Max bars to wait for price to return
  entry_proximity_atr: 0.3 # How close price must get to origin level
  time_start: "09:30"
  time_end: "14:30"

chop_filter:
  min_chop_score: 1 # Less sensitive to chop — structural edge
```

**File: `scripts/strategies/failed_auction/signals.py`**

```python
"""
Failed Auction / Single Prints Fill signal generator.
"""

class FailedAuctionStrategy(StrategyBase):
    """
    Required features: roc_10bar, fast_move_detected, fast_move_origin,
                       fast_move_direction, atr_14, chop_score

    Signal logic:

    1. When fast_move_detected == True:
       Record the fast_move_origin level and fast_move_direction.
       This level becomes a "single print" target.

    2. Monitor for price to return to the origin level:
       - For upward fast moves: watch for price to pull back DOWN to the origin
         (close within entry_proximity_atr * ATR of fast_move_origin)
       - For downward fast moves: watch for price to rally UP to the origin

    3. When price reaches the origin:
       LONG if the fast move was DOWN (price rushed down, now filling back up)
       SHORT if the fast move was UP (price rushed up, now filling back down)

    4. Entry: close of the bar that reaches the origin level
    5. Stop: beyond the far end of the fast move
       (for a downward fast move that we're buying the fill on:
        stop = low of the fast move - 1 tick)
    6. Target: the far end of the fast move (the level price rushed to)
       Cover-the-queen target: midpoint of the fast move

    7. Expiry: if price hasn't returned within max_time_to_fill_bars,
       cancel the pending signal for that level.

    State tracking per session:
        - active_levels: list of {origin, target, direction, created_bar, expires_bar}
        - Remove levels when filled, expired, or price reaches target from the
          wrong side (invalidated)

    Filters:
        - chop_score >= min_chop_score (low threshold — structural edge)
        - Time window
        - Don't enter if there's already an active trade
    """
```

---

## 15. STRATEGY: Initial Balance Pullback (ICT)

**File: `scripts/strategies/initial_balance/core/initial_balance_pullback.py`**

```python
"""
ICT-style Initial Balance Retracement signal generator.
"""

class IBPullbackStrategy(StrategyBase):
    """
    Required features: ib_high, ib_low, ib_mid, atr_14, session_block

    Signal logic (ADR-017 Optimized):
    
    1. IB Range Check: Wait for IB to form.
    2. Pullback Confirmation: Price breaks IB level, then retraces to touch/approach it.
    3. Rejection Filter: Uses 1-min candle patterns (wick rejection) at the level.
    4. Entry: Market on close of confirmation bar.
    5. Stop: Middle of IB range or 1.5x ATR.
    6. Target: Next liquidity level (NY1 High/Low or daily EM).
    """
```

---

## 16. STRATEGY: Reversal & Mean Reversion Suite

**Files: `scripts/strategies/reversal/core/box_reversion.py`, `mean_reversion.py`**

```python
"""
Modular Reversal strategies utilizing exhaustion and false breakouts.
"""

class BoxReversionStrategy(StrategyBase):
    """
    Detects false breakouts of session boxes.
    Requires: Ny1_High, Ny1_Low, Box_Width_ATR.
    """

class MeanReversionStrategy(StrategyBase):
    """
    Statistical exhaustion via Bollinger Bands.
    Requires: bb_upper, bb_lower, bb_pctile.
    """
```

---

## 17. UTILITY: Acceptance/Rejection Classifier

Already specified in Section 5 under `scripts/libs_py/features/acceptance_rejection.py`.

This is a LIBRARY utility — not a strategy. Any strategy can import and use it:

```python
from scripts.libs_py.features.acceptance_rejection import classify_level_interaction, LevelState

# In a strategy's signal logic:
state = classify_level_interaction(df.iloc[i-10:i], level=ib_high, lookback_bars=10)
if state == LevelState.SHARP_REJECT:
    # Generate fade signal
```

---

## 18. UTILITY: Chop Detection Composite

Already specified in Section 5 under `scripts/libs_py/features/chop.py` and `scripts/libs_py/features/internals.py`.

This is a LIBRARY utility. Strategies reference `chop_score` and `chop_vwap_flag`
columns that are pre-computed on the enriched DataFrame.

---

## 19. Orchestration & Run Scripts

**File: `scripts/strategies/base.py`**

```python
"""
Abstract base class for all strategies.
"""
from abc import ABC, abstractmethod
from scripts.libs_py.risk.risk_config import Signal
from scripts.trading_framework.config.config_loader import AppConfig
import pandas as pd


class StrategyBase(ABC):
    """
    Interface that all strategies implement.

    Attributes:
        config: AppConfig
        strategy_config: dict (loaded from strategy's config.yaml)
        required_features: list[str] — features this strategy needs

    Methods:
        generate_signals(df: pd.DataFrame) -> list[Signal]:
            Scan the DataFrame and produce a list of Signals.
            Each Signal includes entry_price, stop_price, risk_points,
            and a context dict with strategy-specific metadata.

        get_required_features() -> list[str]:
            Return the list of feature names this strategy requires.
            The orchestrator ensures these are computed before calling
            generate_signals.

        get_search_space() -> dict:
            Return the Optuna search space for this strategy's parameters.
            Keys are parameter names, values are dicts with
            {type: "int"|"float"|"categorical", low:, high:, choices:}
    """

    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> list[Signal]: ...

    @abstractmethod
    def get_required_features(self) -> list[str]: ...

    @abstractmethod
    def get_search_space(self) -> dict: ...
```

**File: `scripts/run_raw_analysis.py`**

```python
"""
Run in RAW mode: generate signals, compute MFE/MAE, produce analysis reports.
No trade management, no risk rules.

Usage: python scripts/run_raw_analysis.py --strategy vwap_reclaim --symbol MES
"""
# Steps:
# 1. Load config (set risk_mode = "raw")
# 2. Load enriched DataFrame via DataLoader
# 3. Compute required features via FeatureRegistry
# 4. Instantiate strategy, generate signals
# 5. Run compute_mfe_mae on all signals
# 6. Generate MFE/MAE report
# 7. Generate conditional tables (by session, chop_score, etc.)
# 8. Save results
```

**File: `scripts/run_strategy_backtest.py`**

```python
"""
Run in STRATEGY mode: apply trade management policy, compute per-trade results.
No session or account risk.

Usage: python scripts/run_strategy_backtest.py --strategy vwap_reclaim --symbol MES --policy cover_the_queen
"""
# Steps:
# 1. Load config (set risk_mode = "strategy")
# 2. Load data, compute features, generate signals
# 3. Instantiate BacktestEngine with the selected policy
# 4. Run backtest
# 5. Generate tearsheet and conditional tables
# 6. Compare multiple policies if requested (--compare-policies)
```

**File: `scripts/run_portfolio_sim.py`**

```python
"""
Run in PORTFOLIO mode: all strategies, all risk levels, prop eval rules.

Usage: python scripts/run_portfolio_sim.py --symbol MES
"""
# Steps:
# 1. Load config (set risk_mode = "portfolio")
# 2. Load data, compute all features
# 3. Instantiate all strategies, generate all signals
# 4. Run PortfolioSimulator
# 5. Run PropEvalMonteCarlo on combined daily P&L
# 6. Generate portfolio tearsheet, chop filter report, strategy comparison
```

**File: `scripts/run_optimization.py`**

```python
"""
## Configuration & Orchestration (ADR-009)

The system enforces a **Contract Duality** model to allow institutional-grade testing on retail-size accounts.

- **Data Ingestion**: Standardizes on high-volume Mini contracts (ES/NQ) for superior liquidity and tick depth analysis.
- **Risk Execution**: Re-values Mini ticks to their Micro equivalent (e.g. 0.25 ticks = $0.50 risk for NQ) at the configuration layer.
- **Unified Loader**: All components must initialize via `scripts/trading_framework/config/config_loader.py:load_config()` to ensure multipliers are correctly applied before engine start.

### Layer 6: ML Optimization
- **Purged Walk-Forward**: Uses Lopez de Prado's "Purging and Embargo" logic in `PurgedKFold` to prevent temporal leakage between train/test folds.

Usage: python scripts/run_optimization.py --strategy vwap_reclaim --metric prop_pass_rate
"""
# Steps:
# 1. Load config
# 2. Define pipeline_fn that: loads data → computes features → generates signals
#    → runs backtest → returns metric
# 3. Instantiate StrategyOptimizer with pipeline_fn
# 4. Run optimization
# 5. Report best params, optimization landscape, parameter importance
```

---

## 18. Testing Strategy

**Unit tests for each library module:**

- `test_loader.py`: Verify parquet loading, merge, forward-fill, VOLD computation
- `test_features.py`: For each feature module, test with known inputs and verify outputs.
  Test VWAP resets at session boundaries. Test IB computation. Test chop score thresholds.
- `test_risk.py`:
  - Test each TradePolicy with scripted price sequences.
    E.g., CoverTheQueen: feed a sequence where price reaches 1R, verify partial exit,
    then price continues to 2R, verify trail, then reverses to trail stop, verify exit.
  - Test SessionRiskManager: verify it rejects trades after max_trades_per_day,
    pauses after consecutive losers, stops after daily max loss.
  - Test AccountRiskManager: verify EOD trailing drawdown updates correctly,
    weekly limit triggers observation mode, eval pass detection works.
- `test_backtest.py`: Run a small dataset through the engine with known signals
  and verify trade outcomes match expected P&L.
- `test_signals.py`: For each strategy, feed a synthetic DataFrame with known patterns
  and verify signals are generated at the expected bars with correct prices.

**Integration tests:**

- End-to-end: load real data for 1 month, run a strategy in all three risk modes,
  verify outputs are consistent (raw mode produces more signals than strategy mode,
  which produces more than portfolio mode).
- Leakage test: run leakage_guard on all features and walk-forward splits.

---

## Dependency List (`requirements.txt`)

```
pandas>=2.0
numpy>=1.24
pyarrow>=14.0
pyyaml>=6.0
matplotlib>=3.7
plotly>=5.15
optuna>=3.5
scikit-learn>=1.3
hmmlearn>=0.3
quantstats>=0.0.62
tqdm>=4.65
pytest>=7.4
```

---

## Implementation Order

1. `scripts/trading_framework/config/config_loader.py` + `config/default.yaml`
2. `scripts/libs_py/data/loader.py` + `session_tagger.py` + `resampler.py`
3. `scripts/libs_py/features/atr.py` (dependency for many other features)
4. `scripts/libs_py/features/vwap.py`
5. `scripts/libs_py/features/initial_balance.py`
6. `scripts/libs_py/features/internals.py` + `scripts/libs_py/features/chop.py`
7. `scripts/libs_py/features/bollinger.py` + `scripts/libs_py/features/keltner.py` + `scripts/libs_py/features/ema.py`
8. `scripts/libs_py/features/auction.py` + `scripts/libs_py/features/acceptance_rejection.py`
9. `scripts/libs_py/features/registry.py`
10. `scripts/libs_py/risk/risk_config.py` (dataclasses)
11. `scripts/libs_py/risk/trade_policies.py` (all policies)
12. `scripts/libs_py/risk/session_manager.py`
13. `scripts/libs_py/risk/account_manager.py`
14. `scripts/trading_framework/core/execution.py`
15. `scripts/trading_framework/core/mfe_mae.py`
16. `scripts/trading_framework/core/engine.py`
17. `scripts/trading_framework/core/portfolio_sim.py`
18. `scripts/strategies/base.py`
19. `scripts/strategies/vwap_reclaim/` (first strategy — validate full pipeline)
20. `scripts/trading_framework/reporting/` (all reporting modules)
21. `scripts/run_raw_analysis.py` (first end-to-end test)
22. Remaining strategies: `ib_breakout`, `ema_pullback`, `failed_auction`
23. `scripts/trading_framework/ml/walk_forward.py` + `leakage_guard.py`
24. `scripts/trading_framework/ml/prop_eval_mc.py`
25. `scripts/trading_framework/ml/optimizer.py`
26. `scripts/run_portfolio_sim.py` + `scripts/run_optimization.py`
27. `scripts/libs_py/regime/` (all regime models)
28. Tests throughout
