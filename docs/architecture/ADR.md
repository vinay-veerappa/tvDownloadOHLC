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

---

## [ADR-019] Options Rolling Strategy Pattern
**Status:** Approved
**Date:** 2026-05-19

### Context
In multi-silo options strategies (e.g., Wheel, Income Covered Call, Long DTE Credit), active positions frequently require rolling (to a new expiration and/or strike) upon breaching management thresholds (e.g., target profit, delta breach, DTE threshold). A choice exists between implementing a complex, stateful atomic "roll" order structure, or using a "close + rescan" pattern.

### Decision
1. **Close-then-Rescan Pattern**: The Options Strategy Engine will standardly execute rolls by returning a `ManageAction(close=True, reason="ROLL")`.
2. **Scan Re-entry**: Once the paper executor closes the existing option position, the strategy is free to scan for a new entry on the subsequent tick.
3. **Execution Rationale**:
    - **Re-validation**: Rather than blindly rolling into a new option contract, this pattern forces the standard strategy entry filters (IV Rank, spot price, economic calendar blackouts, and upcoming earnings) to re-evaluate the market context.
    - **Simplicity & Safety**: Eliminates the risk of complex double-leg executions hanging in the broker service, and guarantees that any new entry adheres to current capital allocation and sizing rules.

---

## [ADR-020] Prop Firm RTH Liquidation & Harmonised Strategy Integration Standard
**Status:** Approved
**Date:** 2026-05-20

### Context
To support institutional prop-firm funding rules, we must eliminate overnight carryover risk and swap exposure. Furthermore, to prevent maintenance overhead and duplicate data-handling code, we must enforce a unified, decoupled strategy pattern.

### Decision
1.  **Mandatory 16:00 ET Hard Exit:** All strategy hunters (Pillar 2) and adapters must enforce absolute liquidation of outstanding trades at or before 16:00 New York Time (the close of the 15:59 bar).
2.  **Strategy Decoupling Rule:** Custom strategy scripts are forbidden from reading files directly, converting timezones, or performing raw bar-by-bar looping. They must derive calculations from centralized libraries (`libs_py/`) and return a standardized Signal List DataFrame.
3.  **Optuna-ready Dynamic Pivots:** Swing pivoting structures must be parameter-driven to allow Optuna execution sweeps to discover optimal pivot lookbacks per index.

### Implementation Rules
1.  **Exits:** Intraday signals are capped at 16:00 ET. The strategy's `hunt()` output enforces `target1_price` or `stop_price` execution, with an absolute exit boundary at 16:00 ET if neither is hit.
2.  **I/O and Timezones:** Strategies accept standardized, tz-aware `America/New_York` DataFrames from the `DataLoader`. No direct `pd.read_parquet` calls or custom naive timezone conversions are permitted inside `strategies/`.
3.  **Libraries first:** Strategies must import core structural math (`detect_swings`, `detect_cisd`, `detect_fvg`) directly from `libs_py.ict_engine` and avoid duplicating pivot/gap logic.

---

## [ADR-021] Unified Prop Firm Simulation Standard
**Status:** Approved
**Date:** 2026-05-20

### Context
Prop firm simulation logic had proliferated across four separate, incompatible implementations:
1. `scripts/trading_framework/ml/prop_eval_mc.py` — Monte Carlo on daily P&L (called with per-trade data — **methodologically incorrect input**).
2. `scripts/orb_generic/strategy_validation/scripts/06_prop_sim.py` — Full rule-set (daily loss limit, trailing DD, consistency rule, max trades/day) but isolated to ORB strategies only.
3. `scripts/strategies/nine_thirty_breakout/utils/simulate_prop_pass.py` — Bootstrap MC hardcoded to a single Excel file from one ORB variant.
4. `scripts/trading_framework/reporting/risk_profiler.py` — Institutional grading (EV, PF, SQN, DRR) but no firm-rule enforcement.

This created maintenance risk, inconsistent metrics, and a silent correctness bug (per-trade returns fed as daily P&L to the Monte Carlo).

### Decision
A single canonical `PropFirmSimulator` module is adopted as the **only** source for prop firm viability evaluation. All other implementations are demoted to legacy and must not be extended.

### Implementation Rules
1. **Single Source of Truth:** `scripts/trading_framework/ml/prop_firm_simulator.py` is the canonical module. All backtesting pipelines must import from this module for prop firm simulation.
2. **Input Contract:** The simulator accepts the `trades_detailed` DataFrame emitted by `VectorizedBacktester.run()` (columns: `pnl_pct`, `exit_time`). It aggregates trades to daily P&L internally after applying rule-based trade caps and daily loss limits. Per-trade returns must never be treated as daily P&L.
3. **Firm Profiles:** All firm rule configurations (trailing DD, static DD, daily loss limit, consistency rule, max trades/day, eval period) are codified as immutable `PropFirmProfile` dataclasses in `FIRM_PROFILES`. Canonical presets: `apex_50k`, `apex_100k`, `topstep_50k`, `topstep_100k`, `ftmo_50k`, `generic_50k`.
4. **Config Override:** Firm parameters may be overridden in `sessions.yaml` under `prop_firm.overrides` without modifying code. The `primary_profile` key selects which firm drives the tearsheet pass/fail badge.
5. **Grading:** Monte Carlo pass-rate maps to ADR-010 letter grades (A ≥ 80%, B ≥ 65%, C ≥ 50%, D ≥ 30%, F < 30%).
6. **Pipeline Integration:** Prop firm simulation is **Layer 6** of the 7-Layer Research Pipeline (ADR-010). `run_backtest.py` runs `run_all_profiles()` across all configured firm profiles and attaches the multi-profile summary markdown to the tearsheet output.
7. **Legacy Shims:** `prop_eval_mc.run_prop_mc_simulation()` and `compute_prop_eval_stats()` in `run_backtest.py` are retained as deprecated shims for backward compatibility with existing tests. They must not be called from new strategy code.

### Files
| Path | Role |
| :--- | :--- |
| `scripts/trading_framework/ml/prop_firm_simulator.py` | **Canonical implementation** |
| `scripts/trading_framework/config/sessions.yaml` | Firm profile config & overrides (`prop_firm:` section) |
| `scripts/trading_framework/config/config_loader.py` | `PropFirmConfig` dataclass parser |
| `scripts/trading_framework/run_backtest.py` | Layer 6 integration (consumes `PropFirmSimulator`) |
| `scripts/trading_framework/ml/prop_eval_mc.py` | **Deprecated shim** — do not extend |
| `scripts/orb_generic/strategy_validation/scripts/06_prop_sim.py` | Legacy standalone — ORB-specific only |
| `scripts/strategies/nine_thirty_breakout/utils/simulate_prop_pass.py` | Legacy standalone — NTB-specific only |

---

## [ADR-022] Parallel & GPU-Accelerated Sweep Execution
**Status:** Approved
**Date:** 2026-07-15

### Context
ADR-017 mandates zero-loop vectorization for individual strategy `hunt()` calls. However, large parameter sweeps (e.g., 1,152 arms × 20 years of 1-min ES1 data) can still take 3-4 hours even with vectorized strategies because arms execute sequentially. The FVG freshness mitigation loop (per-FVG binary search on cumulative min/max arrays) also benefits from JIT compilation and GPU acceleration.

Available hardware:
- **CPU**: 24 cores (AMD/Intel)
- **GPU**: NVIDIA RTX 4060 Laptop, 8GB VRAM, CUDA 12.x
- **Libraries**: joblib (CPU parallel), Numba (JIT), CuPy (GPU arrays)

### Decision
Large parameter sweeps (≥32 arms) MUST use the parallel sweep runner architecture. The following acceleration layers are adopted:

1. **Arm-Level Parallelism (joblib)**: Each arm is independent and can run on a separate CPU core. Use `joblib.Parallel(n_jobs=N, backend="loky")` with `N = min(arms, cpu_count)`. Each worker loads the shared OHLC data from cache and runs the strategy independently.

2. **Numba JIT for Per-Element Loops**: Any remaining per-element loops (e.g., FVG mitigation detection, group-based cumulative operations) MUST be decorated with `@njit(cache=True)` to compile to native machine code. This applies to loops that cannot be expressed as pure NumPy vectorized operations but iterate over a bounded set (FVGs, swing points).

3. **GPU Acceleration (CuPy)**: Large array cumulative operations (`cummin`, `cummax`, `cumsum`) and search operations (`searchsorted`) on arrays exceeding 1M elements SHOULD use CuPy GPU arrays when available. Fallback to NumPy when CUDA is unavailable. Guard with `try: import cupy` pattern.

4. **Binary Search on Monotonic Arrays**: When searching for "first occurrence" thresholds on cumulative arrays (e.g., first bar where `cummin_low <= level`), use `np.searchsorted` on the monotonic cumulative array instead of `np.argmax(mask)` over slices. This reduces O(n) per element to O(log n).

### Implementation Rules

1. **Parallel Sweep Runner**: Sweeps with ≥32 arms MUST use `run_fvg_cisd_sweep_parallel.py` pattern (joblib). Single-arm execution via `run_backtest.py` remains sequential.

2. **Numba JIT Functions**: Pure numerical functions (no pandas/Python objects) that contain loops MUST use `@njit(cache=True, parallel=True)` where the loop can be parallelized with `prange`. Functions must accept/return NumPy arrays only.

3. **GPU Fallback Pattern**: Always wrap CuPy usage in try/except, falling back to NumPy:
```python
try:
    import cupy as cp
    gpu_arr = cp.asarray(arr)
    result = cp.asnumpy(cp.minimum.accumulate(gpu_arr))
except Exception:
    result = np.minimum.accumulate(arr)
```

4. **Worker Data Caching**: Shared OHLC data must be loaded once and cached (module-level `_DATA_CACHE`) to avoid re-reading parquet files per worker. joblib's `loky` backend handles inter-process sharing via pickling.

5. **Memory Awareness**: Each worker loads ~200MB of 1m OHLC data. With 24 workers, this is ~4.8GB total — within 16GB RAM. GPU operations must stay within 8GB VRAM (single 6.7M element float64 array = ~54MB, safe).

### Files
| Path | Role |
| :--- | :--- |
| `scripts/strategies/ict/runners/run_fvg_cisd_sweep_parallel.py` | **Canonical parallel sweep runner** (joblib + Numba + CuPy) |
| `scripts/strategies/ict/runners/run_fvg_cisd_sweep.py` | Sequential sweep runner (legacy, for small sweeps) |
| `scripts/strategies/ict/strategies/ict_fvg_cisd_rejection.py` | Strategy with vectorized + Numba-accelerated fresh mode |

### Performance Benchmarks (ES1, 6.7M bars, 1,152 arms)

| Mode | Per-Arm Time | Total Sweep Time | Speedup |
| :--- | :--- | :--- | :--- |
| Sequential (original) | ~12s avg | ~3.9 hours | 1× |
| Sequential + Numba fresh mode | ~17s (fresh) / ~0.3s (multi) | ~2 hours est. | ~2× |
| Parallel (8 workers) + Numba | ~2s effective | ~20 min est. | ~12× |
| Parallel (24 workers) + Numba + GPU | ~1s effective | ~10 min est. | ~24× |

### Consequences
* **Research Velocity**: 1,152-arm sweeps complete in minutes instead of hours, enabling rapid iteration on strategy design.
* **Hardware Utilization**: Full use of 24 CPU cores + RTX 4060 GPU instead of single-core sequential execution.
* **JIT Compilation**: Numba-compiled functions run 10-100× faster than Python loops on first call (cached after first compile).
* **GPU Offload**: Cumulative array operations on 6.7M elements take ~5ms on GPU vs ~50ms on CPU.

---

## [ADR-023] Universal Basis Points (bps), Price Percentage & Excursion Statistics Standard
**Status:** Approved  
**Date:** 2026-08-25  

### Context
Arbitrary point-based stops and targets (e.g. 10/20 pts on NQ) degrade as asset prices scale over time (e.g., 20 pts was 18.2 bps in 2022 at NQ 11k, but only 10.0 bps at NQ 20k). Furthermore, cross-asset comparisons (NQ vs ES vs YM) are invalidated by raw point figures.

### Decision
1. **Absolute Ban on Arbitrary Points**: All strategies across Python, Pine Script v6, and NinjaTrader 8 MUST define risk, stops, targets, and excursions in **Basis Points (bps, where 1 bps = 0.01% = 0.0001)** and **Price Percentage (%)**.
2. **Mandatory Excursion Analysis**: All backtests and strategy evaluations MUST derive and report:
   - **MFE** and **MAE** distributions across percentiles (p10, p25, p50, p75, p90, p95).
   - Cumulative target reach probabilities (CDF).
   - MAE drawdown survival curves (win rate conditioned on incurred adverse drawdown bins).
3. **Execution Brackets**: Standardize on the institutional Pack Trading model:
   - Minimum Risk Floor: 2.0 bps (0.02%).
   - Maximum Risk Ceiling: 15.0 bps (0.15%).
   - Target 1 ("Cover The Queen"): +10.0 bps (0.10%) — 50% scale-out + lock BE.
   - Target 2 ("Runner Target"): +30.0 bps (0.30%) or trailing structural swing pivots.

---

## [ADR-024] Evidence-Chain Integrity Controls for the Trading Brain Ledger
**Status:** Approved
**Date:** 2026-08-29

### Context
Six external audit rounds against the Trading Brain evidence chain (`scripts/trading_brain/`)
surfaced a recurring class of defect: governance controls that exist in code but can be
circumvented through caller-supplied inputs — receipt timestamps that forge ex-ante
provenance, predictor callbacks that return sealed labels, per-fold significance that
masks a null candidate, sibling-index FDR borrowing, and calendar-date filtering that
drops the prior-evening Globex leg from sealed manifests. Each remediation round
hardened one boundary; this ADR records the final trust architecture so future
changes do not silently regress it.

### Decision
1. **Receipt-time authority is capability-gated and never self-service.**
   `received_at_utc` overrides on plans and intake items require override_reason +
   override_actor AND the process capability `TRADING_BRAIN_ALLOW_RECEIPT_OVERRIDE=1`.
   Override-path plans are stamped `HISTORICAL_SOURCE_ASSERTED` and carry NO live-plan
   authority unless a capability-gated `verify_historical_snapshot()` records the
   append-only `HISTORICAL_VERIFIED` lifecycle event (optionally with an evidenced
   `verified_effective_from_utc`). Long-running services must call
   `assert_next_process_is_migration()` at startup and refuse to boot with the flag set:
   the capability exists only inside short-lived offline migration commands.
2. **Historical queries never rewrite themselves.** `get_plan_as_of` defaults to
   `knowledge_mode='AS_RECORDED'`: verification events authorize only from their own
   receipt time (or an evidenced effective-from instant). The administrative
   `CURRENTLY_VERIFIED_HISTORY` view is explicit by name, never a default. Provenance
   eligibility is resolved in SQL BEFORE ordering/limit, so an unverified assertion can
   never mask an eligible ex-ante plan. Amendments apply only when BOTH
   `effective_at_utc <= as_of AND received_at_utc <= as_of`.
3. **Shadow-gate evaluation executes a BOUND predictor, never a caller-chosen callback.**
   `preregister_candidate_finding` binds the predictor by module, qualified name, source
   hash, closure cell contents, referenced-globals subset, and defaults. Evaluation
   refuses any mismatch BEFORE the terminal-stage lock. Benchmark/MDE authority is the
   sealed holdout registry row, never a preceding event payload. Design power is frozen
   from the PREREGISTERED effect (observed power is a diagnostic only); promotion
   requires significance AND observed improvement >= preregistered MDE. Resumes require
   strictly larger sample sizes (sample-extension custody). KNOWN LIMIT (separate
   workstream): final certification requires executing a registered immutable model
   artifact in an isolated process with no label-store access.
4. **Walk-forward significance is candidate-scoped, dependence-aware, and
   family-corrected.** Fold p-values are UPPER-tail and combine via a centered circular
   block bootstrap over the full chronological out-of-sample stream (Stouffer retained as
   cross-check). Multiplicity is applied at the FAMILY level with strict identity
   binding: the preferred interface is ID-keyed (`family_results{ candidate_id: p }` +
   `current_candidate_id`); positional `family_p_values[index]` is honored only when
   `family_p_values[index] == aggregated_p` (else refused as identity borrowing;
   duplicate equal values are ambiguous and refused). `evaluate_candidate_family()` is
   the one-shot family correction stage. Promotion-capable rounds must set
   `require_family_declaration=True` (FAMILY_UNDECLARED fails closed); the precomputed
   `evaluate_walk_forward_folds` path is AUDIT-ONLY and never promotable.
5. **Data scope in sealed manifests must match what the analysis consumed.**
   Wargame manifests slice the LOGICAL CME futures session
   (`get_futures_session_bounds`: prior business day 18:00 ET -> 17:00 ET, DST-aware),
   never the civil ET calendar date; the prior-evening Globex leg (P12 window) is part
   of the sealed input hash. Post-market ingest binds missing sessions from
   `derive_futures_session_date(event_timestamp_utc)` and excludes cross-session/
   cross-ticker records; executions beyond matched opportunities are
   `RISK_UNASSESSABLE`, never compliant evidence.
6. **Honest staging labels.** The operational gate's status remains
   `FIXTURE_REPLAY_ACCEPTED` — a fixture completeness battery, NOT live operational
   acceptance (which requires a persistent live-soak ledger and a ten-session soak).
   Synthetic drills are "mechanics/UI practice only", never remediation evidence;
   curricula attempt authentic weakness sessions first and disclose per-session
   fallbacks. Promotion metrics are `CALLER_ATTESTED` until artifact-derived evaluation
   exists (separate workstream).

### Alternatives Considered
* Caller-asserted receipt overrides with audit events only (rounds 2-3): rejected —
  an audited forgery is still a forgery; capability gating + provenance downgrade is
  the honest combination.
* Positional-only family correction: rejected in round 6 — an index a caller chooses
  can borrow a sibling's identity; ID-keyed families bind identity.
* Observer-effect design power: rejected — an extreme realized result would manufacture
  its own power; prospective power must be frozen pre-holdout.

### Consequences
* Normal application paths cannot fabricate ex-ante provenance, sealed evaluation
  results, or candidate significance. Every escape hatch is capability-gated,
  append-only, or explicitly named as administrative.
* Tests that exercise migration semantics set the capability flag at module import and
  use evidenced effective-from instants — a standing reminder that migration fixtures
  simulate the privileged path, not a general API.
* Remaining certification gaps are explicit workstreams: registered-artifact isolated
  evaluation (F5), artifact-derived promotion metrics (F6), and the live-soak ledger
  with ten-session certification (F7).


---

## [ADR-026] Session-Range Knowability (REG-2 Option A): no value before its window closes
**Status:** Approved (user-ratified 2026-09-05)
**Date:** 2026-09-05

### Context
`scripts/libs_py/nqstats/sessions.py::get_nq_session_ranges` stamped a session's
whole-day final aggregate (open/high/low/close/mid) onto EVERY bar of the logical
trading day, including bars from 18:00 the prior evening. A 01:21 Asia bar therefore
read the NY1 box mid (classification window 07:30-08:29 ET) seven hours before it
existed. The `box_reversion` causality probe caught this live (LOOKAHEAD at 1 of 3
informative cutoffs, a 01:21 signal appearing only when future bars were appended);
the same stamping contaminated every consumer of `extract_all_sessions` -- about
20 call sites including live trader scripts. Research item REG-2
(`docs/strategies/research_backlog/14_session_range_lookahead.md`) recorded three
remediation options; the user ratified option A.

### Decision
1. **A session value is knowable only from the end of its own window onward.**
   `get_nq_session_ranges` (and therefore `extract_all_sessions`) emits NaN on
   every bar strictly BEFORE the session's window-close bar, then the final
   aggregate from the window-close bar onward. Consumers wanting "today's value"
   on an early bar must read the explicit `prev_*` columns.
2. **Box status is as-of-t, not as-of-day.** `compute_box_status` emits "Pending"
   while a box's classification window is still forming (the LT/SF split is not
   final), the FINAL status from the window-close bar onward, and "None" before
   the window opens. Previously the day's final status was visible from 18:00.
3. **NaN is not a value.** Classifiers that converted NaN inputs into concrete
   labels now propagate NaN / "Unknown" instead: `get_broken_status_vectorized`
   ("Held" on NaN), `NQStatsEngine`'s `c_anchor` ("BEARISH" on NaN). A fabricated
   label reads as a measurement; a NaN reads as not-measured.
4. `compute_box_broken` continues to check the mid only inside its post-session
   broken window (already time-scoped); with the stamper fixed its input mid is
   now knowable inside that window.

### Alternatives Considered
* Option B (value from session start, forward-filled): rejected -- still exposes
  the FINAL aggregate on the bars where the box is still forming.
* Option C (leave the shared layer, gate each consumer): rejected by the user --
  it leaves the lookahead in place for every consumer not yet gated, which is the
  status quo that produced the defect.

### Consequences
* Every framework hunter consuming box features inherits causality without its
  own window gate. `box_reversion`'s consumer-side 08:30-11:30 gate remains
  (entries are only taken there anyway) and is now redundant-but-harmless.
* Live trader scripts (`intraday_blocks.py`, `briefing_core.py`) that read
  "today's session value" on early bars now see NaN and must use `prev_*`; the
  blast-radius harness and recorded runs quantify each script's exposure.
* The PineScript/profiler convention (LT/SF are PENDING states that can flip)
  now has its Python equivalent: the "Pending" status value is new to the Python
  side and appears only inside classification windows.
* Pinned by `tests/test_session_range_knowability.py` (boundary tests per
  session, negative controls, and a causality probe on the adapter path).
