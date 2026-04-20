# Architecture Decision Records (ADR)

This file serves as the single source of truth for architectural and behavioral decisions in the tvDownloadOHLC project.

---

## [ADR-001] Data Timezone Contract
**Status:** Approved
**Date:** 2025-12-09

### Context
To support both legacy logic and seamless timezone switching on the frontend.

### Decision
*   **Charts**: Expect Naive UTC inputs, displayed in `America/New_York` by default but offsettable.
*   **Derived JSONs**: Provide a **Hybrid Output**:
    *   `_time` fields (e.g. `hod_time`): **NY-based Strings** ("09:30").
    *   `_ts` fields (e.g. `hod_ts`): **Unix Timestamps** (UTC).
*   **Implementation**: Indicators prefer `_ts` fields for marker alignment.

---

## [ADR-002] Statistical Normalization Standard
**Status:** Approved
**Date:** 2026-03-29

### Context
Absolute price values (e.g., NQ at 10,000 vs 20,000) are context-dependent and prevent reliable historical or cross-ticker comparisons.

### Decision
All statistical reporting and internal calculations for performance metrics (MAE, MFE, Expected Moves, and Session Averages) MUST use **Price Percentage** as the primary basis.

### Implementation Rules
1.  **Basis**: Percentage of the reference price (e.g., Midnight Open or Session Start).
2.  **Reporting**: Values reported in % (e.g., "MFE: +0.42%") rather than points.
3.  **Calculation**: `(Target Price - Reference Price) / Reference Price * 100`
4.  **Exceptions**: Absolute points are reserved only for execution-level "tick" calculations (e.g., slippage), but normalized for aggregate analysis.

---

## [ADR-004] Institutional Session Windows (ALN)
**Status:** Approved
**Date:** 2026-03-26

### Context
Standardizing trading session boundaries for statistical analysis (Asia/London/NY).

### Decision
The following windows (ET) are the **Absolute Rule** for all ALN-based calculations:
| Session | Hours (ET) | Purpose |
| :--- | :--- | :--- |
| **Asia** | 20:00 - 02:00 | Range Establishment |
| **London** | 02:00 - 08:00 | Range Expansion |
| **New York** | 08:00 - 16:00 | Execution |

---

## [ADR-005] Profiler Quadrant Logic (LT/ST/LF/SF)
**Status:** Approved
**Date:** 2026-03-27

### Context
Classifying market behavior based on high/low break sequences within session "Boxes".

### Decision
| Status | Sentiment | Logic |
| :--- | :--- | :--- |
| **Long True (LT)** | Strong Bullish | Break High AND Hold Low. |
| **Short True (ST)** | Strong Bearish | Break Low AND Hold High. |
| **Long False (LF)** | Reversal (Short) | Break High THEN Break Low. |
| **Short False (SF)** | Reversal (Long) | Break Low THEN Break High. |

---

## [ADR-006] Data Fusion Layer Protocol
**Status:** Approved
**Date:** 2026-03-28

### Context
Separation of deep historical data (`data/`) and recent streaming data (`data/live/`).

---

## [ADR-007] Economic Event Data Fusion
**Status:** Approved
**Date:** 2026-03-29

### Context
Maintaining a comprehensive 26-year historical database of news events (EconomicEvent) while providing real-time scheduling.

### Decision
The **Prisma `EconomicEvent` Table** is officially designated as a **Secondary Source of Truth** for all news-based analytical services, alongside the live ForexFactory/Yahoo feeds.

### Implementation Rules
1.  **Passive Sync**: The Web UI `getDashboardContext` acts as the primary background sync trigger, upserting live feed data into the DB on load.
2.  **Historical Priority**: For backtesting, correlation studies, and "Day-at-a-Glance" history, services MUST query the `EconomicEvent` table to leverage the 9,800+ record archive.
3.  **Blackout Protocol**: The `news_calendar_fetcher.py` script bridges the DB and legacy bots by mirroring the current schedule to `news_blackout.csv`.
4.  **Timezone Integrity**: All dates in the `EconomicEvent` table MUST be stored in **UTC** (per ADR-001) for cross-platform compatibility.

---

## [ADR-008] Derived Feature Persistence (Stationary Features)
**Status:** Approved
**Date:** 2026-03-30

### Context
Complexity in backtesting (Layer 6) and real-time inference (Layer 8) often leads to redundant, expensive re-calculations of stationary market features (Regimes, ALN Status, News proximity, and Normalized Distances).

### Decision
The project will enforce a **"Calculate Once, Persist Everywhere"** pattern for all features that only depend on historical OHLCV or external events (News).

### Implementation Rules
1.  **Storage Target**: High-performance features are stored in `data/derived/{ticker}_features_1m.parquet` using the UTC timeline from ADR-001.
2.  **Automatic Synchronization**:
    *   The `NQStatsAdapter` acts as the primary writer/sync-agent for institutional features.
    *   Backtesting `FrameworkLoader` MUST attempt to load the Parquet feature store before falling back to raw calculation.
3.  **Schema Governance**: All derived columns must be prefixed with `feat_` to prevent collisions with raw data (e.g., `feat_ny1_status`, `feat_vol_z`).

---

## [ADR-009] Data vs. Execution Contract Duality
**Status:** Approved
**Date:** 2026-04-04

### Context
Mini-contracts (ES/NQ) provide deep historical depth, but Micro-contracts (MES/MNQ) are the primary execution vehicle.

### Decision
*   **Data Source**: Continue using Mini-contract OHLCV for feature engineering and signal generation.
*   **Sizing Rule**: All calculations involving dollars ($) — including P&L, Session Max Loss, Trailing Drawdown, and Commissions — MUST assume Micro-contract multipliers (e.g., $5/point for MES, $2/point for MNQ).
*   **Risk Symmetry**: Backtests performed on Mini data are automatically scaled to Micro units during the "Grading" and "Portfolio" phases.

---

## [ADR-010] Institutional Risk Grading & Unified Research Suite
**Status:** Approved
**Date:** 2026-04-04

### Context
Strategy assessment often relies on noisy metrics (absolute P&L). We need institutional "passability" (Prop Firm standards).

### Decision
The project adopts a **Unified Research Suite** powered by a **Categorical Grading System (A-F)**. All backtests MUST report these grades to ensure cross-strategy comparability.

### Implementation Rules
1. **The 7-Layer Pipeline**: Every research run must follow the standard sequence:
   - Layer 1: Parallel Parquet Loading
   - Layer 2: Stationary Feature Enrichment
   - Layer 3: Signal Logic Discovery
   - Layer 4: Vectorized Backtest Engine
   - Layer 5: Excursion Analysis (MFE/MAE)
   - Layer 6: ML/Prop Evaluation (Monte Carlo)
   - Layer 7: Consolidated Reporting (Tearsheet + Dashboard)

2. **Grading Rubric**: Standardized thresholds for EV ($), PF, SQN, and DRR.

---

## [ADR-011] High-Performance Vectorized Research Analysis
**Status:** Approved
**Date:** 2026-04-04

### Context
Research analysis (MFE/MAE and Monte Carlo) typically involves N trades looking H bars forward. Naive implementing is too slow for Optuna. However, pure vectorized broadcasting on multi-million bar datasets (e.g., 2M+ NQ1 bars) can lead to massive memory allocation failures (8GB+ for a single result matrix).

### Decision
1. **Vectorized First**: All post-signal research analysis MUST use **Vectorized Windowing** and **NumPy-First Execution**.
2. **Chunked Memory Safety**: For datasets exceeding 1,000,000 bars or 100,000 signals, operations MUST be **Chunked** (recommended `CHUNK_SIZE = 50000`) to keep memory allocation within safe hardware bounds.
3. **Precision Optimization**: Use `float32` for search/lookahead buffers to reduce memory footprint by 50% without loss of significant accuracy in statistical analysis.
4. **Banned Patterns**: Manual Python loops over bars or trades are strictly prohibited in the `core/` layers.

---

## [ADR-012] Traceable Research Standard (TRS)
**Status:** Approved
**Date:** 2026-04-04

### Context
Research runs often litter the root or `results/` folder with cryptic names, making it impossible to audit past optimizations or parameter choices.

### Decision
All research executions (Backtests, Optimizations) MUST utilize a **RunID-based partitioning** system:
1. **Subfolder Pattern**: `results/RESEARCH/RUN_<timestamp>_<ticker>_<strategy>/`
2. **Mandatory Metadata**: Every run MUST persist a `run_metadata.json` containing:
    - Git Commit Hash
    - Hyperparameters (Optuna trail inputs)
    - Source Data Hash
    - Scaling Multipliers (ADR-009)

---

## [ADR-013] Institutional Reporting Suite
**Status:** Approved
**Date:** 2026-04-04

### Context
Backtest results must be "institutional grade" to enable rapid decision-making across symbols and regimes.

### Decision
1. **Automated Tear Sheets**: Every run MUST generate a `report.html` (QuantStats) and a `full_stats.json`.
2. **Leaderboard Update**: Results must be appended to the global research ledger for cross-strategy comparison.

---

## [ADR-014] Shell Native Execution Standard
**Status:** Approved
**Date:** 2026-04-04

### Context
Terminal interactions on Windows frequently fail when using Unix-style aliases (e.g., `ls | grep`). 

### Decision
1. **PowerShell-First**: All automated and research-level terminal interactions MUST use native PowerShell cmdlets (`Get-ChildItem -Filter`, `Move-Item`, `New-Item`).
2. **Path Integrity**: Use backslashes (`\`) or `Join-Path` for reliability across Windows environments.

---

## [ADR-015] Architectural Bootstrapping Standard (ABS)
**Status:** Approved
**Date:** 2026-04-04

### Context
Agents occasionally skip reading the ADR or lose context during a turn.

### Decision
1. **Synchronization First**: The `sync-trading-brain` skill is the non-negotiable entry point for all development work.
2. **Explicit Verification**: Every task MUST begin by stating: "I have read and synchronized with the latest ADRs."

---

## [ADR-016] Unified Knowledge Hierarchy
**Status:** Approved
**Date:** 2026-04-04

### Context
Disconnected sources of truth (Second Brain, ADRs, MCP) create confusion.

### Decision
1. **Source of Truth Definitions**:
    - **Architectural Hub**: `docs/architecture/ADR.md` (Software, environment, process).
    - **Trading Hub**: `docs/SecondBrain_Trading.md` (Market logic, stats, bias).
    - **Visual System**: `docs/indicators/DailyNYLevels/VISUAL_SYSTEM.md` (Palette, templates, geometry).
2. **Mandatory Synchronization**: Every agent session MUST begin by synchronizing with this hierarchy via the `sync-trading-brain` skill and the root `README.md` protocol.
3. **MCP Role**: `codebase-memory-mcp` is an **Indexer & Searcher**, not an independent repository for decisions.

---

## [ADR-017] Modular Vectorized Strategy Architecture
**Status:** Approved
**Date:** 2026-04-04

### Context
As the Statistical Trading Framework scales, we require a high-performance, standardized way to write, optimize, and visualize strategies. Legacy iterative patterns (looping over bars) are insufficient for high-trial Optuna sweeps.

### Decision
All future and research-grade strategies MUST follow the **Modular Vectorized Signal Pattern**, decomposing the system into three atomic layers:
1.  **Triggers (Layer 4a)**: Vectorized mathematical logic for raw entry/exit signals.
2.  **Filters (Layer 4b)**: Contextual "gates" (Kill Zones, Regimes, News) that block or allow signals.
3.  **Risk Modules (Layer 4c)**: Standardized methods for calculating stops and targets (ATR, Fibs, Institutional Zones).

### Mandatory Implementation Rules
1. **Zero-Loop Requirement**: Total removal of `for` loops in signal generation. Use NumPy/Pandas native operations.
2. **Optuna Hook**: Strategies must expose a `get_param_grid()` method to define their hyperparameter search space.
3. **Interoperable Schema**: Signal generators must output a standardized `pd.DataFrame` containing `signal_time`, `direction`, `entry_price`, `stop_price`, and `target1_price`.
4. **No-Signal Contract (Mandatory)**: If no entries are found, strategies MUST return an **empty DataFrame with the same standardized columns** (not a bare `pd.DataFrame()`). This prevents downstream KeyError failures (for example on `signal_time`) in lifecycle/backtester integrations.
5. **Matrix Verification Gate (Run Once Per Change Set)**: For any new/ported hunter strategy or lifecycle schema change, run a one-time full matrix lifecycle smoke test across all ADR-017 hunter keys before completion. This gate is mandatory to catch no-signal and parameter-shape regressions early.

### Required Matrix Command (PowerShell)
Run from repo root:
`$strategies = @('ib_pullback','box_reversion','mean_reversion','ema_pullback','vwap_reclaim','failed_auction','six_am_reversal'); foreach ($s in $strategies) { & .\\.venv\\Scripts\\python.exe -m scripts.trading_framework.research.lifecycle_runner --ticker NQ1 --strategy $s --trials 1 --skip-persist; if ($LASTEXITCODE -ne 0) { throw "FAILED:$s" } }`

### Consequences
*   **Research Velocity**: Backtests on multi-year 1m datasets take seconds, enabling massive Optuna sweeps.
*   **Layered Flexibility**: Filters and Risk modules become "hot-swappable" across different strategy triggers.

---

## [ADR-018] Visual System Compliance
**Status:** Approved
**Date:** 2026-04-20

### Context
To maintain 100% visual consistency across all TradingView indicators and NinjaScript strategies, we require a shared visual layer.

### Decision
1. **Mandatory Adoption**: All new indicators and strategies MUST utilize the standardized visual layer (Palette, Templates, Geometry, and Profile Scaling) defined in **`docs/indicators/DailyNYLevels/VISUAL_SYSTEM.md`**.
2. **Zero-Custom-Drawing Rule**: Indicators must bind to canonical templates in the `VISUAL_TEMPLATES.md` catalog rather than invoking low-level drawing APIs (`line.new`, `box.new`, etc.) with ad-hoc colors.
3. **Governance**: Any deviation from the Visual System requires an explicit "Overrides" section in the indicator's profile documentation and a justification in code comments.
