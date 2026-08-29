# 🛠️ Trading Second Brain: Master Implementation Plan

> **Document Version**: 2.0.0 (Execution-Ready & Formally Gated)  
> **Status**: Canonical Phased Engineering Roadmap & Review Document  
> **Architecture Reference**: [`docs/architecture/TRADING_SECOND_BRAIN_MASTER_ARCHITECTURE.md`](file:///c:/Users/vinay/tvDownloadOHLC/docs/architecture/TRADING_SECOND_BRAIN_MASTER_ARCHITECTURE.md) (v4.3.0)  
> **Location**: `docs/architecture/TRADING_SECOND_BRAIN_IMPLEMENTATION_PLAN.md`  
> **Core Operating Principle**: *Construct the verified schema and immutable plan ledger first. Prove legacy reconciliation in shadow mode. Guarantee server-enforced cutoff gates, fail-closed as-of semantics, and under 5 minutes of daily operator review before enabling downstream evaluation or research gates.*

---

## 1. Architectural Strategy & Phasing Roadmap

The implementation is structured into **five sequential, independently testable phases**. **Phase 0 is a self-contained, low-manual-input capture candidate** that must pass a scenario-based operational verification suite before Phase 1 commences:

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 5-PHASE ENGINEERING ROADMAP                                      │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘

  PHASE 0: LOW-MANUAL-INPUT CAPTURE SPINE & ACID DATABASE FOUNDATION [CANDIDATE SPINE]
  • M0.1: Unified SQLite Schema & Exhaustive Immutability Triggers (`trading_brain.sqlite`)
  • M0.2: Immutable Plan Snapshot & Amendment Ledger (`plan_snapshots` + Prisma adapter)
  • M0.3: Shadow Legacy Data Import, Reconciliation & Cutover (`wargame_db_bridge.py`)
  • M0.4: Server-Enforced Pre-Market Forecast Snapshot Registrar (Database-generated timestamps)
  • M0.5: As-Of Signal Opportunity Logger (Observation-only `STRATEGY_REGISTRY_V0`)
  • M0.6: Hardened NT8 Broker Ingestion & Reconciliation Adapter (Idempotency, replay, gaps)
  • M0.7: Measured Tape Actuals Extractor (Live storage path + explicit ingest manifest)
  • M0.8: Scenario-Based Operational Verification Gate (No-trade, early close, DST, roll, soak)
  
                                  │ [Operational Gate: Scenario Suite Pass + 10 Live Sessions]
                                  ▼
  PHASE 1: DAILY PROCESS DELTA & POST-MORTEM ENGINE
  • M1.1: 4-Way Mechanical Reconciler (`daily_process_delta.py` with MECE 5-class day types)
  • M1.2: One-Page Event-First EOD Process Delta Report (<5 min human review; no composite grades)
  • M1.3: Read-Only Memory Bridge (`agent_memory_bridge.py` — preserves `.agent/memory.db` boundary)
  
                                  │
                                  ▼
  PHASE 2: MINUTE-SCALE FEEDBACK & BLINDED DELIBERATE PRACTICE
  • M2.1: Python Post-Submission Deviation Annotator (`deviation_annotator.py`)
  • M2.2: Cross-Repository C# RiskGuard Plan-Friction Addon (`nt8-riskguard` isolated milestone)
  • M2.3: Blinded Deliberate-Practice Replay Engine (Hidden dates/outcomes, locked commitments)
  • M2.4: Recurring-Error Targeted Drill Generator
  
                                  │
                                  ▼
  PHASE 3: RESEARCH GATES, CALIBRATION & MULTI-TIER PROMOTION
  • M3.1: Multiclass Proper-Score Loss Engine (Multiclass Brier & Log Loss vs. 3 baselines)
  • M3.2: Multi-Fold Purged Walk-Forward Validator (Expanding historical folds + dependence control)
  • M3.3: Preregistered Shadow Validation Gate (Task-specific MDE, power >= 0.80, fail-closed policy)
  • M3.4: Decoupled Multi-Tier Promotion Engine (Forecast != Signal != Policy != Portfolio)
  
                                  │
                                  ▼
  PHASE 4: TYPED INTAKE CATALOG & WEB WORKSPACE
  • M4.1: Universal `information_items` Intake Router (9 Information Types + As-Of Boundary)
  • M4.2: Visual Next.js / Tailwind Wargaming, Process Delta & Practice Dashboard
```

---

## 2. Phase 0: Low-Manual-Input Capture Spine & Database Foundation

### Objective
Establish the canonical relational schema, immutable plan ledger, server-enforced cutoff gates, and idempotent ingestion adapters.

---

### Milestone 0.1: Unified ACID Database Schema & Exhaustive Immutability Triggers
* **Target Paths**:
  * `scripts/trading_brain/db/schema.sql`: Complete DDL for all 14 core tables.
  * `scripts/trading_brain/db/init_db.py`: Initializer with WAL mode, busy timeout, and foreign key verification.
  * `scripts/trading_brain/db/connection.py`: Thread-safe context manager enforcing `PRAGMA foreign_keys = ON`.
  * `tests/test_trading_brain_db.py`: Comprehensive schema and trigger test suite registered in `pytest`.
* **Database Location**: `data/wargaming/db/trading_brain.sqlite`.
* **Core Table DDL Manifest**:
  1. `information_items`: Universal typed intake catalog envelope.
  2. `plan_snapshots`: Immutable pre-market trading plan snapshots (ex-ante declarations).
  3. `plan_amendments`: Append-only plan adjustments with timestamps and supersession links.
  4. `forecast_snapshots`: Immutable pre-market quantitative predictions (git hash, config hash, full-precision probabilities).
  5. `signal_opportunities`: As-of mechanically eligible setup triggers (taken, passed, or missed).
  6. `signal_disposition_events`: User/system disposition events (`EXECUTED`, `PASSED`, `MISSED`, `OFFLINE`).
  7. `signal_outcomes`: Versioned theoretical MFE/MAE outcomes evaluated post-hoc.
  8. `session_tape_actuals`: Measured tape actuals with vendor provenance, contract ID, and quality state.
  9. `execution_events`: Monotonic broker event stream (orders, fills, cancellations, stop modifications).
  10. `intervention_events`: RiskGuard hard locks, soft friction warnings, and explicit overrides.
  11. `unmatched_execution_links`: Staging table for ambiguous or unmatched execution-to-opportunity links.
  12. `drill_attempts`: Blinded deliberate practice attempts and locked user decisions (DDL only; writers in Phase 2).
  13. `behavioral_declarations`: Subjective user reflections (DDL only; writers in Phase 1).
  14. `candidate_findings`, `strategies`, `model_registry`: Governance and model metadata.
* **Exhaustive Immutability Trigger Matrix**:
  Every append-only evidence table is protected by paired `BEFORE UPDATE` and `BEFORE DELETE` triggers that raise SQLite failures:
  - `plan_snapshots`, `plan_amendments`
  - `forecast_snapshots`
  - `signal_opportunities`, `signal_disposition_events`, `signal_outcomes`
  - `session_tape_actuals`
  - `execution_events`, `intervention_events`
  - `candidate_findings`
* **Acceptance Gate**:
  * Command: `pytest tests/test_trading_brain_db.py`
  * Assertions:
    - Tables initialize cleanly with foreign keys enforced.
    - `UPDATE` and `DELETE` on all 10 append-only tables raise immediate SQLite exceptions.
    - Partial unique index permits exactly one `LIVE_PRODUCTION` forecast per `(session_date, ticker, effective_cutoff_utc)`.
    - Partial unique index permits exactly one `CURRENT` plan per `(session_date, ticker, cutoff_time)`.
    - Append-only corrections link cleanly via `corrects_event_id` and `supersedes_plan_id`.

---

### Milestone 0.2: Immutable Pre-Market Plan Snapshot & Amendment Ledger
* **Target Path**: `scripts/trading_brain/plans/plan_adapter.py`
* **Problem Solved**: Fulfills the Phase 0 promise to freeze the pre-market plan by capturing Prisma `TradePlan` records into an immutable evidence ledger before the cutoff.
* **Schema**:
  ```sql
  CREATE TABLE plan_snapshots (
      plan_snapshot_id TEXT PRIMARY KEY,        -- UUID v4
      session_date DATE NOT NULL,
      ticker TEXT NOT NULL,
      preparation_cutoff_utc TIMESTAMP NOT NULL,
      source_system TEXT NOT NULL,              -- 'PRISMA_WEB', 'MARKDOWN_CLI', 'MANUAL_IMPORT'
      source_plan_id TEXT,                      -- FK / reference to Prisma TradePlan.id
      plan_status TEXT NOT NULL,                -- 'ACTIVE', 'SUPERSEDED', 'CANCELLED'
      
      -- Plan Content & Assertions
      verbatim_plan_text TEXT NOT NULL,         -- Unaltered user plan text
      primary_bias TEXT NOT NULL,               -- 'BULLISH', 'BEARISH', 'NEUTRAL', 'NO_TRADE'
      wargamed_scenarios_json TEXT NOT NULL,    -- Structured scenarios and expected branches
      invalidation_levels_json TEXT NOT NULL,   -- Explicit price invalidation boundaries
      max_intended_risk_bps REAL NOT NULL,      -- Risk budget declaration
      permitted_strategies_json TEXT NOT NULL,  -- Active strategy IDs for the session
      
      -- As-Of Provenance Timestamps (Server-Generated)
      received_at_utc TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
      available_at_utc TIMESTAMP NOT NULL,      -- When plan was finalized by user
      created_at_utc TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE plan_amendments (
      amendment_id TEXT PRIMARY KEY,
      plan_snapshot_id TEXT NOT NULL,
      amendment_seq INTEGER NOT NULL,
      amended_at_utc TIMESTAMP NOT NULL,
      reason_code TEXT NOT NULL,                -- 'MACRO_NEWS', 'REGIME_CHANGE', 'DISCIPLINE_PAUSE'
      amendment_text TEXT NOT NULL,
      amended_bias TEXT,
      amended_risk_bps REAL,
      FOREIGN KEY (plan_snapshot_id) REFERENCES plan_snapshots(plan_snapshot_id)
  );
  ```
* **Adapter Logic**:
  * Runs at `08:45 ET` (or on-demand prior to cutoff).
  * Queries Prisma database for active `TradePlan` for the logical session.
  * Writes an immutable row to `plan_snapshots`.
  * Verifies `available_at_utc <= preparation_cutoff_utc`.
* **Acceptance Gate**:
  * Command: `pytest tests/test_plan_adapter.py`
  * Assertions: Freezes Prisma plan text; rejects plans stamped after cutoff; records intraday amendments with sequential ordering without mutating original plan snapshot.

---

### Milestone 0.3: Shadow Legacy Data Import, Reconciliation & Cutover
* **Target Paths**:
  * `scripts/trading_brain/migrations/migrate_legacy_dbs.py`
  * `scripts/trading_brain/db/wargame_db_bridge.py`
* **Sequencing Contract (No Cutover Before Verified Schema & Reconciliation)**:
  1. **Schema Exists**: Milestone 0.1 schema verified.
  2. **Shadow Import**: `migrate_legacy_dbs.py` reads historical records from `system_wargames.sqlite`, `market_actuals.sqlite`, and `mickey_ground_truth.sqlite` into a staging schema within `trading_brain.sqlite`.
  3. **Field-Level Reconciliation**: Script verifies 100% match on:
     - Total session dates and tickers migrated.
     - Exact floating-point probability and price fields.
     - SHA-256 content checksums.
  4. **Dual-Read Comparison Mode**: `wargame_db_bridge.py` runs in comparison mode for 3 test runs to verify identical query outputs between legacy databases and `trading_brain.sqlite`.
  5. **Single Canonical Writer Cutover**: [`scripts/wargaming/generate_daily_wargame.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/wargaming/generate_daily_wargame.py) and [`scripts/wargaming/reconcile_wargame.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/wargaming/reconcile_wargame.py) switch to direct writes via `trading_brain.sqlite`.
  6. **Read-Only Retention in Place**: Legacy database files are marked read-only and retained in their current paths for a 90-day retention window (no physical moving during live cutover to prevent path or lock hazards).
* **Acceptance Gate**:
  * Command: `python -m scripts.trading_brain.migrations.migrate_legacy_dbs --verify`
  * Assertions: 0 record discrepancies; automated comparison test proves legacy query methods produce identical records from `trading_brain.sqlite`.

---

### Milestone 0.4: Server-Enforced Pre-Market Forecast Snapshot Registrar
* **Target Path**: `scripts/trading_brain/forecast/forecast_registrar.py`
* **Execution Contract & Database-Generated Timestamps**:
  * The registrar records the exact temporal lifecycle:
    - `forecast_started_at_utc`: When analysis pipeline began execution.
    - `source_data_cutoff_utc`: Max timestamp of market data bars consumed.
    - `received_at_utc`: Server database clock timestamp (`CURRENT_TIMESTAMP`).
    - `committed_at_utc`: Timestamp transaction committed to disk.
  * **As-Of Enforcement**: `source_data_cutoff_utc <= effective_cutoff_utc` is strictly enforced.
  * **Certified Input Contract**: Ingestion evaluates model-specific certified input contracts (e.g. required provider count, maximum bar staleness in seconds) rather than arbitrary universal constants.
  * **Abstention Policy**: If input contracts fail, registrar writes `abstain_flag = TRUE`, `abstain_reason = 'STALE_DATA_OR_MISSING_PROVIDERS'`, and sets all probability columns to `NULL`.
* **Acceptance Gate**:
  * Command: `pytest tests/test_forecast_registrar.py`
  * Assertions:
    - Attempting to register `LIVE_PRODUCTION` with input data past cutoff fails closed.
    - Database-generated `received_at_utc` cannot be overridden by caller payload.
    - Replay audits write `REPLAY_AUDIT` with `original_prediction_id` pointer.

---

### Milestone 0.5: As-Of Signal Opportunity Logger (`STRATEGY_REGISTRY_V0`)
* **Target Paths**:
  * `scripts/trading_brain/signals/opportunity_logger.py`
  * `scripts/trading_brain/strategies/registry_v0.py`
* **Operating Scope**: Explicitly labeled `EXPERIMENTAL_CAPTURE_ONLY` (no live execution authority, no trade recommendations).
* **Strict As-Of Execution Semantics**:
  * Evaluates strategy rules on bar-close only (`available_at_utc <= bar_close_utc`).
  * Zero future bar lookahead; features computed strictly from trailing historical window.
  * Deduplication key: `(session_date, ticker, strategy_id, bar_timestamp_utc)`.
  * Enforces maximum signal expiration window (e.g. signal expires if not filled within 15 minutes).
  * Theoretical outcomes written post-hoc to `signal_outcomes`, strictly separated from ex-ante `signal_opportunities`.
* **Strategy V0 Frozen Rule Definitions**:
  1. `STRAT_ALN_LPEU_V0`: London Protrusion Expansion Up breakout pullback.
  2. `STRAT_FIRECRACKER_V0`: Overnight range compression (<35% DRO spent) opening drive.
  3. `STRAT_GOALPOST_BB_V0`: Broken-Broken Asia/London sweep fade toward opposite extreme.
  4. `STRAT_P12_MID_RETEST_V0`: P12 Midline equilibrium retest before 09:45 ET.
* **Acceptance Gate**:
  * Command: `pytest tests/test_opportunity_logger.py`
  * Golden Fixtures: Tests against 5 golden session datasets including positive setup triggers, negative near-misses, duplicate suppression, and boundary bar-close cases.

---

### Milestone 0.6: Hardened NT8 Broker Ingestion & Reconciliation Adapter
* **Target Path**: `scripts/trading_brain/ingest/nt8_broker_adapter.py`
* **Functionality & Edge-Case Reconciliation**:
  * Ingests broker orders, fills, cancellations, partial executions, stop modifications, commissions, and slippage.
  * Handles reconnects, pagination gaps, and duplicate execution IDs via `idempotency_key`.
  * **Unmatched Link Isolation**: Execution-to-opportunity matching uses deterministic criteria. If an execution cannot be matched unambiguously to a single `opportunity_id`, it is flagged `AMBIGUOUS_MATCH` and written to `unmatched_execution_links` for review rather than guessing.
  * Captures RiskGuard hard lockouts, soft friction warnings, and explicit user overrides into `intervention_events`.
* **Acceptance Gate**:
  * Command: `pytest tests/test_nt8_broker_adapter.py`
  * Fixtures: Replays 8 synthetic broker event streams covering reconnects, out-of-order fills, null-order executions, stop modifications, partial fills, and ambiguous opportunity scenarios.

---

### Milestone 0.7: Measured Tape Actuals Extractor
* **Target Path**: `scripts/trading_brain/tape/tape_extractor.py`
* **Data Path & Ingest Manifest**:
  * Reads current-session live storage directly (`data/live/` or live tick feed) for post-market capture; deep parquet archive used strictly for historical backfills.
  * Extracts HOD, LOD, Open, Close, timestamps in UTC, realized MFE/MAE in Basis Points.
  * Captures explicit provider/ingest manifest: vendor, contract ID, roll rule, adjustment policy, and data quality state flags (`CLEAN`, `SUSPECT_TICKS`, `INCOMPLETE_BARS`).
  * Evaluates `LABEL_DAY_TYPE_V1` and `LABEL_EOD_CLASSIFICATION_V1`.
* **Acceptance Gate**:
  * Command: `pytest tests/test_tape_extractor.py`
  * Fixtures: Verified against 5 benchmark tape sessions (normal, early close, DST transition, contract roll, and missing bar session).

---

### Milestone 0.8: Scenario-Based Operational Verification Gate
* **Target Path**: `scripts/trading_brain/testing/operational_soak_gate.py`
* **Execution Contract**:
  * Phase 0 is formally declared complete and shippable only when it passes:
    1. **Automated Scenario Test Suite**:
       - *Scenario A*: No-trade session (zero signals, zero fills $\rightarrow$ cleanly recorded).
       - *Scenario B*: Early close session (holiday schedule correctly handled).
       - *Scenario C*: DST transition session (UTC vs. ET window correctness).
       - *Scenario D*: Contract roll date (continuous vs. actual contract mapping).
       - *Scenario E*: Feed outage & broker reconnect (gap recovery and deduplication).
       - *Scenario F*: Database crash & recovery (WAL rollback and PRAGMA integrity pass).
    2. **Live Soak Window**: 10 consecutive live trading sessions captured with zero manual interventions, zero trigger errors, and <5 minutes of operator verification.

---

## 3. Phase 1: Daily Process Delta & Mechanical Post-Mortem

### Objective
Create a deterministic, event-first 4-way reconciliation engine that produces a single concise, actionable EOD report in under 5 minutes of operator reading time without Goodhart-prone composite grading.

---

### Milestone 1.1: 4-Way Mechanical Reconciler
* **Target Path**: `scripts/trading_brain/evaluation/daily_process_delta.py`
* **The 4-Way Reconciliation Quadrant**:
  ```
  1. PRE-MARKET PLAN (plan_snapshots + forecast_snapshots @ 08:45 ET)
                           ↕
  2. SIGNAL OPPORTUNITIES (All eligible mechanical triggers via registry_v0)
                           ↕
  3. EXECUTIONS & INTERVENTIONS (Actual fills, stops, RiskGuard telemetry)
                           ↕
  4. MEASURED TAPE OUTCOMES (16:15 ET HOD/LOD, Day Type, MFE/MAE)
  ```
* **Metrics Computed (Event-First, No Composite Grades)**:
  1. **Session Forecast Loss**: Computes proper-score realized loss for the single session (labeled "session forecast loss", reserving calibration/skill claims for accumulated samples).
  2. **Opportunity Realization Table**: Explicit counts of eligible signals: $N_{\text{total}}$, $N_{\text{executed}}$, $N_{\text{passed}}$, $N_{\text{missed}}$.
  3. **Execution Capture Delta**: Fills vs. triggers (slippage in bps, scale-out adherence at +10 bps *Cover The Queen*).
  4. **Intervention Telemetry**: Factual counts of hard locks, soft friction overrides, and plan deviations.

---

### Milestone 1.2: One-Page Event-First Process Delta Report
* **Target Path**: `scripts/trading_brain/reports/render_process_delta.py`
* **Format**: Markdown (`data/wargaming/reports/daily_process_delta_YYYY-MM-DD.md`) + Terminal output.
* **Sections**:
  1. **Session Identification & Data Quality**: Date, ticker, contract ID, data quality flags.
  2. **Plan & Forecast vs. Realized Tape**: Predicted scenario vs. realized `LABEL_DAY_TYPE_V1` classification.
  3. **Opportunity & Execution Ledger**: Tabular view of all eligible signals, actions taken, trigger vs fill prices, and slippage.
  4. **RiskGuard & Intervention Log**: Factual record of guard events.
  5. **Quarantined Reflection Space**: Form for user subjective reflections (saved to `behavioral_declarations` with review state `USER_ENTERED`).
* **Acceptance Gate**:
  * Command: `python -m scripts.trading_brain.evaluation.daily_process_delta --date 2026-08-28` runs in <3 seconds and produces the complete report.

---

### Milestone 1.3: Read-Only Memory Bridge (`agent_memory_bridge.py`)
* **Target Path**: `scripts/trading_brain/bridges/agent_memory_bridge.py`
* **Architectural Boundary Preserved**:
  * `.agent/memory.db` remains the sole owner of development memories, user preferences, and agent skill proposals.
  * `trading_brain.sqlite` remains the sole canonical ledger of trading executions and market outcomes.
  * `agent_memory_bridge.py` provides a **read-only typed interface**: when an agent skill proposal queries historical trading statistics, it queries `trading_brain.sqlite` via the bridge without coupling schemas or mixing outcome types.

---

## 4. Phase 2: Minute-Scale Feedback & Blinded Deliberate Practice

### Objective
Bridge the gap between pre-market analysis and live execution through real-time friction and high-repetition blinded simulation drills.

---

### Milestone 2.1: Python Post-Submission Deviation Annotator
* **Target Path**: `scripts/trading_brain/guard/deviation_annotator.py`
* **Functionality**:
  * Asynchronously consumes the execution stream via MCP post-submission.
  * Compares executed orders against the active plan in `plan_snapshots`.
  * Flags observable deviations (e.g. unapproved strategy, trading outside permitted window), logs an event in `intervention_events`, and emits visual/audio coaching alerts.

---

### Milestone 2.2: Cross-Repository C# RiskGuard Plan-Friction Addon
* **Target Path**: `C:\Users\vinay\nt8-riskguard\Rules\PlanFrictionRule.cs`
* **Governance**: Managed as a dedicated cross-repository milestone with its own isolated test suite.
* **Safety Contract**:
  * Synchronous pre-order evaluation in NinjaTrader 8.
  * Reads daily plan constraints pushed from Python at 08:45 ET.
  * **Fail-Safe Invariant**: If Python bridge is offline or plan context is missing, plan friction **defaults to disabled/shadow** and **NEVER blocks trades**.
  * **Exit Preservation**: Plan friction **NEVER intercepts or delays risk-reducing or protective exit orders**.

---

### Milestone 2.3: Blinded Deliberate-Practice Replay Engine
* **Target Path**: `scripts/trading_brain/practice/drill_engine.py`
* **Functionality**:
  * Loads historical market sessions from the drill library.
  * Blinds date, symbol, future bars, and pre-market plan.
  * Progressively reveals bars up to key decision windows (e.g. 08:30 ET, 09:30 ET, 09:45 ET).
  * **Locks User Commitment**: Prompts the user to declare Bias (`BULLISH`, `BEARISH`, `NEUTRAL`), Setup / `NO_TRADE`, Invalidation Level, Entry Price, Stop (bps), and Target (bps).
  * Reveals subsequent bars and grades process adherence:
    - *Was the setup valid under strategy rules?*
    - *Was the invalidation respected?*
    - *Did the user avoid widening stops?*
    - *Reaction latency and recognition speed.*
  * Records the attempt in `drill_attempts`.
* **Acceptance Gate**:
  * Command: `pytest tests/test_drill_engine.py`

---

## 5. Phase 3: Research Gates, Calibration & Multi-Tier Promotion

### Objective
Provide statistical machinery for discovering, testing, and promoting decision rules with strict separation between forecast models, signal models, execution policies, and portfolio deployment.

---

### Milestone 3.1: Multiclass Proper-Score Loss Engine
* **Target Path**: `scripts/trading_brain/research/calibration_engine.py`
* **Functionality**:
  * Computes Multiclass Brier Score and Log Loss across all 5 day-type classes.
  * Generates reliability diagrams across predicted probability buckets.
  * Evaluates paired loss improvements over the 3 mandatory baselines (unconditional base rate, rolling 50-session frequency, incumbent model).

---

### Milestone 3.2: Multi-Fold Purged Walk-Forward Validator
* **Target Path**: `scripts/trading_brain/research/walk_forward_gate.py`
* **Functionality**:
  * Implements expanding rolling walk-forward folds with purged embargoes.
  * Applies **Benjamini-Hochberg False Discovery Rate (FDR)** control where independence holds, or valid family-wise control.
  * Uses **Stationary Block Bootstrap** / Newey-West HAC standard errors for time-series dependence.

---

### Milestone 3.3: Preregistered Shadow Validation Gate
* **Target Path**: `scripts/trading_brain/research/shadow_gate.py`
* **Execution Contract**:
  * Consumes a preregistered evaluation contract: primary proper score, prospective power ($1-\beta \ge 0.80$), task-specific MDE, and economic threshold after costs.
  * Evaluates 1-time sealed shadow data.
  * **Terminal States**: `PROMOTED`, `REJECTED`, `INCONCLUSIVE_WAITING`, `INVALID_TEST`.
  * **Fail-Closed Rule**: An inconclusive test is **NEVER** promoted.

---

### Milestone 3.4: Decoupled Multi-Tier Promotion Engine
* **Target Path**: `scripts/trading_brain/research/promotion_orchestrator.py`
* **Four Independent Promotion Tiers**:
  1. **Tier 1 (Forecast Model)**: Evaluated on proper-score calibration and discrimination.
  2. **Tier 2 (Signal Model)**: Evaluated on opportunity expectancy and precision.
  3. **Tier 3 (Execution Policy)**: Evaluated on realized EV in R after commissions and slippage.
  4. **Tier 4 (Portfolio Deployment)**: Evaluated on portfolio drawdown, tail risk, turnover, capacity, and prop-firm constraints.
  *(A strategy never inherits certification simply because an upstream forecast improved).*

---

## 6. Phase 4: Typed Intake Catalog & Web Workspace

### Objective
Provide a unified, human-native intake interface and interactive web dashboard for daily wargaming, post-market review, and deliberate practice.

---

### Milestone 4.1: Universal Typed Intake Catalog (`information_items`)
* **Target Path**: `scripts/trading_brain/intake/catalog_router.py`
* **Functionality**:
  * Ingests the 9 information types with canonical envelope metadata (`information_id`, `evidence_class`, `time_orientation`, `available_at_utc`, `review_state`).
  * Enforces `available_at_utc <= decision_cutoff_utc` on all inputs to prevent hindsight leakage.

---

### Milestone 4.2: Web Dashboard UI Integration
* **Target Path**: `web/` (Next.js, Tailwind CSS, Shadcn/UI, Lightweight Charts)
* **Features**:
  1. **Pre-Market Wargame & Plan Builder**: Scenario cards and plan snapshot authoring.
  2. **Daily Process Delta Scorecard**: Visual 4-way post-mortem comparison.
  3. **Deliberate Practice Replay Station**: Browser-based blinded chart drill simulator.
  4. **Model Governance & Promotion Dashboard**: Calibration curves, walk-forward folds, and shadow evaluation state.

---

## 7. Immediate Next Steps & Review Checkpoints

| Step | Action Item | Target Delivery | Prerequisite / Dependency |
| :---: | :--- | :--- | :--- |
| **1** | **Review & Approval of Implementation Plan (v2.0.0)** | User Review | This Document |
| **2** | **Milestone 0.1: Database Schema & Immutability Triggers** (`schema.sql`, `test_trading_brain_db.py`) | Step 1 Approved | Step 1 |
| **3** | **Milestone 0.2: Plan Snapshot & Amendment Ledger** (`plan_adapter.py`) | Milestone 0.1 | Step 2 |
| **4** | **Milestone 0.3: Shadow Legacy DB Import & Reconciliation** (`migrate_legacy_dbs.py`) | Milestone 0.1 | Step 2, 3 |
| **5** | **Milestone 0.4: Server-Enforced Forecast Snapshot Registrar** (`forecast_registrar.py`) | Milestone 0.1 | Step 2 |
| **6** | **Milestone 0.5: As-Of Signal Opportunity Logger** (`opportunity_logger.py` + `registry_v0`) | Milestone 0.1 | Step 2 |
| **7** | **Milestone 0.6: Hardened NT8 Broker Ingestion Adapter** (`nt8_broker_adapter.py`) | Milestone 0.1 | Step 2 |
| **8** | **Milestone 0.7: Measured Tape Actuals Extractor** (`tape_extractor.py`) | Milestone 0.1 | Step 2 |
| **9** | **Milestone 0.8: Operational Verification Gate** (Scenario suite + 10 live sessions soak) | Phase 0 Done | Step 2–8 |
| **10**| **Phase 1 Re-Approval Review** | Formal Sign-Off | Step 9 Passed |
