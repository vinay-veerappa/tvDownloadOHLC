# Harmonised Trading & Research Architecture

## 1. Overview
The Harmonised Trading & Research Architecture unites all isolated trading strategies, mathematical libraries, and backtesting scripts into a single, high-performance, tz-aware US/Eastern execution flow. 

By enforcing a strict 3-layer decoupled architecture, this system eliminates redundant data loading, standardizes performance metrics via price percentage normalization (ADR-002), prevents timezone vulnerabilities during US Daylight Saving Time (DST) changes (ADR-001), and satisfies strict prop firm intraday risk profiles via a mandatory 16:00 ET hard-liquidation standard.

## 2. Key Responsibilities
*   **Pillar 1 ( Stateless Mathematical Libraries - `libs_py/` )**: Vectorized, stateless mathematical calculations. Zero file I/O, database access, or timezone assumptions.
*   **Pillar 2 ( Pure Signal Hunters - `strategies/` )**: Chaining indicator libraries to identify trade setups. Exposes a uniform `.hunt(data, params)` interface that returns a standardized **Signal List** DataFrame. Stateless and zero PnL tracking.
*   **Pillar 3 ( Centralized Execution Engine - `trading_framework/` )**: High-performance parallel PyArrow data loading via ThreadPoolExecutor, timezone localization to New York clock, matrix-based backtesting, commissions/slippage modeling, and Optuna-based hyperparameter tuning.

## 3. Data Flow
```
[UTC Parquet File] 
       │ (ThreadPoolExecutor parallel I/O)
       ▼
[DataLoader (Pillar 3)] ──► Localizes to America/New_York (Timezone Safe)
       │
       ▼
[Standardized Strategy (Pillar 2)] ──► Calls math from libs_py/ict_engine (Pillar 1)
       │
       ▼
[Canonical Signal List DF] (signal_time, direction, entry, stop, target ≤ 16:00 ET)
       │
       ▼
[VectorizedBacktester (Pillar 3)] ──► Runs Matrix search & Excursion (MFE/MAE %)
       │ (trades_detailed DataFrame)
       ▼
[PropFirmSimulator (Layer 6)] ──► Deterministic + Monte Carlo across firm profiles
       │ (pass_rate_pct, grade A-F, multi-profile summary)
       ▼
[HTML Tear Sheets & Optuna Weights]
```

## 4. Key Components
*   **`scripts/libs_py/data/loader.py` (`DataLoader`)**: ThreadPool parallel reader that localizes raw UTC dates to standard tz-aware New York `US/Eastern` time.
*   **`scripts/libs_py/ict_engine/` (`ict_engine`)**: Mathematical core containing vectorized indicators (`detect_swings`, `detect_cisd`, `detect_fvg`).
*   **`scripts/strategies/ict/core/`**: Refactored strategy hunters executing the standard `.hunt()` interface.
*   **`scripts/trading_framework/core/backtest_engine.py` (`VectorizedBacktester`)**: Layer 5 matrix simulation engine executing trades, slippage/comms, and MAE/MFE.
*   **`scripts/trading_framework/ml/prop_firm_simulator.py` (`PropFirmSimulator`)**: Layer 6 canonical prop firm viability engine. Runs deterministic path simulation and Monte Carlo permutation across multiple firm presets (Apex, TopStep, FTMO). See ADR-021.
*   **`scripts/trading_framework/strategies/registry.py`**: Dynamic factory catalog loading adapter-wrapped strategy classes.

## 5. Technology & Constraints
*   **Zero-Loop Vectorization Constraint (ADR-017)**: Loop-based bar iterations are forbidden. All mathematical indicators must be vectorized using rolling windows or shifting arrays.
*   **Statistical Normalization Standard (ADR-002)**: All statistical reporting, performance logging, and internal PnL math must be calculated as a percentage relative to reference entry prices, not absolute points.
*   **New York Session Clock Standard (ADR-001 / ADR-004)**: All trading hours and Killzones must strictly reference New York `America/New_York` clock to remain immune to DST shift bugs.
*   **Prop Firm RTH Liquidation Standard (ADR-020)**: All generated hunter signals must carry a maximum trade duration of 16:00 ET. Any open position must be forcibly closed at 16:00 ET (close of the 15:59:00 bar) to adhere to prop firm restrictions.
*   **Unified Prop Firm Simulation Standard (ADR-021)**: `PropFirmSimulator` in `trading_framework/ml/prop_firm_simulator.py` is the **only** permitted implementation for prop firm viability evaluation. Per-trade returns must never be fed directly as daily P&L to any Monte Carlo function. All other prop sim scripts (`prop_eval_mc.py`, `06_prop_sim.py`, `simulate_prop_pass.py`) are frozen legacy and must not be extended.
