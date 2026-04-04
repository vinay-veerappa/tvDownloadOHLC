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
**Date:** 2026-03-31

### Context
Complexity in backtesting (Layer 6) and real-time inference (Layer 8) often leads to redundant, expensive re-calculations of stationary market features (Regimes, ALN Status, News proximity, and Normalized Distances). This causes performance bottlenecks in optimization loops and potential logic drift between research and production.

### Decision
The project will enforce a **"Calculate Once, Persist Everywhere"** pattern for all features that only depend on historical OHLCV or external events (News).

### Implementation Rules
1.  **Storage Target**: High-performance features are stored in `data/derived/{ticker}_features_1m.parquet` using the UTC timeline from ADR-001.
2.  **Stationarity Rule**: Only features that are independent of model hyperparameters (e.g., ATR, Session Status, Time-to-News) may be globally persisted. Target-specific features (e.g., Signal entries) remain in the Strategy layer.
3.  **Automatic Synchronization**:
    *   The `NQStatsAdapter` (Layer 8) acts as the primary writer/sync-agent for institutional features.
    *   Backtesting `FrameworkLoader` MUST attempt to load the Parquet feature store before falling back to raw calculation.
4.  **Schema Governance**: All derived columns must be prefixed with `feat_` to prevent collisions with raw data (e.g., `feat_ny1_status`, `feat_vol_z`).
5.  **Auditability**: Each derived file must contain a `metadata_json` footer or sidecar file documenting the engine version used to generate the features.

---

## [ADR-009] High-Performance Parallel Data Processing
**Status:** Approved
**Date:** 2026-04-04

### Context
The backtesting framework processes 10+ years of 1-minute bars across multiple instruments and feature groups. Sequential loading and Python-loop-based computation routinely takes minutes, which is unacceptable for interactive research and Optuna optimization loops (hundreds of trials per run).

### Decision
All data loading and feature computation in `scripts/libs/` MUST meet the following **performance contract: full pipeline (load + enrich + all features) completes in under 10 seconds for a single instrument on 10 years of 1m data.**

### Implementation Rules
1. **Parallel I/O**: All parquet reads MUST use `concurrent.futures.ThreadPoolExecutor`. Price and internals files are loaded concurrently. Target wall-time = time of the slowest single file, not the sum of all files.
2. **pyarrow engine**: All parquet reads MUST use `pyarrow.parquet.read_table()` directly. pyarrow releases the GIL during I/O, enabling true thread parallelism.
3. **Column pruning**: Only request the columns needed via `pq.read_table(..., columns=[...])`. Never read a wide derived parquet when only OHLCV is required.
4. **No Python loops in hot paths**: Any computation over bars or sessions MUST be vectorised using numpy/pandas native ops (cumsum, rolling, groupby-transform). Python `for` loops over individual bars are banned in `scripts/libs/` code.
5. **Vectorised OLS**: Expanding/rolling regression slopes MUST use the closed-form cumsum formulation `(n·Σxy − Σx·Σy) / (n·Σx² − (Σx)²)` via groupby-transform — not scipy or per-bar loops.
6. **Independent feature groups run in parallel**: `FeatureRegistry.ensure_features()` MUST dispatch independent feature groups (those with no shared dependency at that depth) to a `ThreadPoolExecutor`. Only strictly ordered (upstream dependency) groups run sequentially.
7. **Cache-first**: `DataLoader._cache` and the ADR-008 derived-features parquet store are checked before any computation. A cache hit skips all downstream work.

### Verification
- `python scripts/tools/benchmark_pipeline.py NQ1` must complete in < 10s on the developer machine.
- Any new feature module must be profiled before merging. Modules exceeding 2s on 10 years of 1m data must be vectorised before acceptance.

---

## [ADR-010] Institutional Risk Grading & Unified Research Suite
**Status:** Approved
**Date:** 2026-04-04

### Context
Strategy assessment often relies on noisy metrics (absolute P&L) that don't account for risk efficiency or institutional "passability" (Prop Firm standards). This leads to backtest overfitting and poor capital allocation.

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

2. **Grading Rubric**:
   | Metric | A (Excellent) | B (Good) | C (Fair) | D (Poor) | F (Fail) |
   | :--- | :--- | :--- | :--- | :--- | :--- |
   | **EV ($)** | >100 | >50 | >10 | >0 | <0 |
   | **PF** | >1.8 | >1.4 | >1.2 | >1.0 | <1.0 |
   | **SQN** | >3.0 | >2.5 | >2.0 | >1.5 | <1.5 |
   | **DRR** | <4.0 | <6.0 | <8.0 | <10.0 | >10.0 |

3. **Combined Edge**: Calculated as `EV_R * ProfitFactor`. This acts as the primary "Leaderboard" sorting key.
4. **Risk of Ruin (RoR)**: Probability of a fixed bankroll loss (per account size) MUST be < 1% for institutional acceptance.

### Verification
- `scripts/trading_framework/run_backtest.py` is the official implementation of this protocol.
- `scripts/trading_framework/tests/test_grading.py` enforces these thresholds.
