# 🛠️ Trading Second Brain: Master Implementation Plan

> **Document Version**: 1.1.0 (Execution-Hardened)  
> **Status**: Comprehensive Phased Engineering Roadmap & Review Document  
> **Architecture Reference**: [`docs/architecture/TRADING_SECOND_BRAIN_MASTER_ARCHITECTURE.md`](file:///c:/Users/vinay/tvDownloadOHLC/docs/architecture/TRADING_SECOND_BRAIN_MASTER_ARCHITECTURE.md) (v4.3.0)  
> **Location**: `docs/architecture/TRADING_SECOND_BRAIN_IMPLEMENTATION_PLAN.md`  
> **Core Operating Principle**: *Build the Zero-Human Capture Spine first. Ensure mechanical capture, immutable provenance, server-enforced cutoffs, and under 5 minutes of daily manual operator overhead before adding complex feedback or research layers.*

---

## 1. Architectural Strategy & Phasing Roadmap

The implementation is structured into **five sequential, independently testable phases**. **Phase 0 is shippable alone as a complete, zero-maintenance capture product**; subsequent phases require formal re-approval against Phase 0 operational evidence:

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 5-PHASE ENGINEERING ROADMAP                                      │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘

  PHASE 0: ZERO-HUMAN CAPTURE SPINE & ACID DATABASE FOUNDATION [SHIPPABLE STANDALONE]
  • M0.0: Legacy Database Coexistence & Migration (`wargame_db.py` cutover to `trading_brain.sqlite`)
  • M0.1: Unified SQLite Schema (`trading_brain.sqlite`) with Strict Immutability Triggers
  • M0.2: Server-Enforced Pre-Market Forecast Snapshot Registrar (08:45 ET Clock Gate)
  • M0.3: Deterministic Signal Opportunity Logger (Bootstrapped via `STRATEGY_REGISTRY_V0`)
  • M0.4: NT8 Broker & RiskGuard Ingestion Adapter (Idempotent order/fill/intervention stream)
  • M0.5: Mechanical Tape Actuals & Quality Extractor (`load_fused_data` + vendor provenance)
  
                                  │ [Re-Approval Gate: Verified 10 Consecutive Live Sessions]
                                  ▼
  PHASE 1: DAILY PROCESS DELTA & POST-MORTEM ENGINE
  • M1.1: 4-Way Mechanical Reconciler (`daily_process_delta.py` with MECE 5-class day types)
  • M1.2: 1-Page EOD Process Delta Markdown & Terminal Report (<5 min human review)
  • M1.3: Unified Outcome Bridge (Consolidates `.agent/memory.db` outcome queries to `trading_brain`)
  
                                  │
                                  ▼
  PHASE 2: MINUTE-SCALE FEEDBACK & BLINDED PRACTICE HARNESS
  • M2.1: NT8 C# RiskGuard Synchronous Plan Friction + Python Post-Submission Deviation Annotator
  • M2.2: Blinded Deliberate-Practice Replay Engine (Hidden dates, locked answers, process grading)
  • M2.3: Recurring-Error Targeted Drill Generator
  
                                  │
                                  ▼
  PHASE 3: EDGE RESEARCH, MULTICLASS CALIBRATION & PROMOTION GATE
  • M3.1: Multiclass Brier Score & Log Loss Calibration Engine (5 classes + 3 baseline benchmarks)
  • M3.2: Multi-Fold Purged Walk-Forward Validator (Expanding historical folds + Benjamini-Hochberg FDR)
  • M3.3: 1-Time Sealed Shadow Validation Runner ($N \ge 60$, inconclusive-fails-closed policy)
  • M3.4: Formal Strategy Registry V1 Promotion & Champion/Challenger Switch
  
                                  │
                                  ▼
  PHASE 4: TYPED INTAKE CATALOG & WEB WORKSPACE
  • M4.1: Universal `information_items` Intake Router (9 Information Types + As-Of Boundary)
  • M4.2: Visual Next.js / Tailwind Wargaming & Practice Dashboard
```

---

## 2. Phase 0: Zero-Human Capture Spine & Database Foundation

### Objective
Establish the immutable relational ledger and automated data pipelines so that every market session, pre-market plan, trading signal opportunity, broker order/fill, and tape outcome is captured automatically with zero manual data entry.

---

### Milestone 0.0: Legacy Database Coexistence, Cutover & Migration
* **Target Path**: `scripts/trading_brain/migrations/migrate_legacy_dbs.py`, `scripts/trading_brain/db/wargame_db_bridge.py`
* **Problem Solved**: Eliminates double-capture and split-brain risk between legacy `system_wargames.sqlite`, `market_actuals.sqlite`, `mickey_ground_truth.sqlite`, and the new `trading_brain.sqlite`.
* **Execution Contract**:
  1. **One-Time Migration**: `migrate_legacy_dbs.py` reads all existing historical rows from the 3 legacy SQLite files, transforms them into the canonical schema with provenance tags (`LEGACY_MIGRATION_V1`), and inserts them into `trading_brain.sqlite`.
  2. **Legacy Archival**: The 3 legacy files in `data/wargaming/db/` are moved to `data/wargaming/db/archive/` and marked read-only.
  3. **Compatibility Bridge**: `scripts/wargaming/wargame_db.py` is refactored into a thin compatibility wrapper that routes all legacy query and write methods directly to `trading_brain.sqlite`.
  4. **Single Write Path**: [`scripts/wargaming/generate_daily_wargame.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/wargaming/generate_daily_wargame.py) and [`scripts/wargaming/reconcile_wargame.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/wargaming/reconcile_wargame.py) are updated to write directly to `trading_brain.sqlite`.
* **Acceptance Criteria**:
  * Running `migrate_legacy_dbs.py` successfully migrates 100% of historical records.
  * Running `python -m scripts.wargaming.generate_daily_wargame --date 2026-08-28` writes to `trading_brain.sqlite` only, with zero orphan writes to legacy paths.

---

### Milestone 0.1: Unified ACID Database Schema & Migration Engine
* **Target Path**: `scripts/trading_brain/db/`
  * `schema.sql`: Complete DDL for all 12 core tables.
  * `init_db.py`: Database initializer with PRAGMA integrity checks, foreign key enforcement (`PRAGMA foreign_keys = ON`), WAL journal mode, and busy timeout.
  * `connection.py`: Thread-safe context manager for transactional SQLite access.
* **Database Location**: `data/wargaming/db/trading_brain.sqlite`.
* **Core Table DDL Manifest**:
  1. `information_items`: Universal typed intake catalog envelope.
  2. `forecast_snapshots`: Immutable pre-market predictions (git hash, config hash, data manifest hash, full-precision probabilities).
  3. `signal_opportunities`: Every mechanically qualified strategy setup (taken or passed).
  4. `signal_disposition_events`: User/system disposition (`EXECUTED`, `PASSED`, `MISSED`, `OFFLINE`).
  5. `signal_outcomes`: Versioned theoretical MFE/MAE and target outcomes.
  6. `session_tape_actuals`: Mechanical tape facts with vendor provenance, contract roll, and quality flags.
  7. `execution_events`: Monotonic broker event stream (orders, fills, partial exits, stop modifications, slippage).
  8. `intervention_events`: RiskGuard hard locks, soft friction events, and explicit overrides.
  9. `drill_attempts`: Blinded deliberate practice attempts, locked user decisions, and process scores (DDL created; writers deferred to Phase 2).
  10. `behavioral_declarations`: Subjective user reflection and habit compliance declarations (DDL created; writers deferred to Phase 1).
  11. `candidate_findings`: Staged statistical hypotheses under FDR control.
  12. `strategies` & `model_registry`: Certified strategy definitions, parameter versions, and risk constraints.
* **Strict Immutability Triggers**:
  ```sql
  CREATE TRIGGER prevent_forecast_update BEFORE UPDATE ON forecast_snapshots
  BEGIN SELECT RAISE(FAIL, 'CRITICAL: forecast_snapshots is an immutable ledger. Updates are prohibited.'); END;

  CREATE TRIGGER prevent_forecast_delete BEFORE DELETE ON forecast_snapshots
  BEGIN SELECT RAISE(FAIL, 'CRITICAL: forecast_snapshots is an immutable ledger. Deletions are prohibited.'); END;

  CREATE TRIGGER prevent_opportunity_update BEFORE UPDATE ON signal_opportunities
  BEGIN SELECT RAISE(FAIL, 'CRITICAL: signal_opportunities is an immutable ledger. Updates are prohibited.'); END;

  CREATE TRIGGER prevent_execution_update BEFORE UPDATE ON execution_events
  BEGIN SELECT RAISE(FAIL, 'CRITICAL: execution_events is an immutable ledger. Updates are prohibited.'); END;
  ```
* **Acceptance Criteria**:
  * Unit test `tests/test_trading_brain_db.py` is registered in `pytest` and proves:
    - Tables initialize cleanly with foreign keys enabled.
    - Attempting `UPDATE` or `DELETE` on a live forecast snapshot or opportunity raises a hard SQLite error.
    - Partial unique index enforces only one `LIVE_PRODUCTION` forecast per ticker and cutoff.
    - Append-only corrections link correctly via `corrects_event_id`.

---

### Milestone 0.2: Server-Enforced Pre-Market Forecast Registrar
* **Target Path**: `scripts/trading_brain/forecast/forecast_registrar.py`
* **Problem Solved**: Mechanically prevents post-hoc forecast registration by enforcing a server-clock cutoff gate.
* **Execution Contract & Clock Gate**:
  1. **Server-Clock Enforcement**: When `register_forecast(..., mode='LIVE_PRODUCTION')` is called, the registrar calculates:
     $$\text{cutoff\_dt\_utc} = \text{combine}(\text{session\_date}, \text{cutoff\_time}, \text{tz}=\text{'America/New\_York'}).\text{astimezone}(\text{UTC})$$
     If $\text{now\_utc} > \text{cutoff\_dt\_utc} + \text{GRACE\_WINDOW}$ (where $\text{GRACE\_WINDOW} = 120\text{s}$ for pipeline compute latency), the registrar **FAILS CLOSED** and raises:
     `ForecastCutoffExpiredError("Cannot register LIVE_PRODUCTION forecast after the session cutoff. Must register as REPLAY_AUDIT.")`
  2. **Metadata Capture**:
     - `git_commit_hash`: Active repository commit.
     - `environment_hash`: SHA-256 hash of active environment/packages.
     - `config_hash`: SHA-256 of active wargame and concept configuration.
     - `data_manifest_hash`: SHA-256 checksum of input market data.
     - `probabilities`: Full-precision floats for `SF`, `LF`, `LT`, `ST`, `ROTATIONAL_CHOP`.
     - `abstain_flag` & `abstain_reason`: Triggered if data freshness (>120s), missing sessions, or tail volatility ($>4\sigma$) occurs.
  3. **SQL Check Constraint**:
     ```sql
     CONSTRAINT ck_live_cutoff_timing CHECK (
         forecast_mode <> 'LIVE_PRODUCTION' OR
         created_at_utc <= datetime(effective_cutoff_utc, '+120 seconds')
     )
     ```
* **Acceptance Criteria**:
  * Unit test verifies: registering at `08:44 ET` succeeds with `LIVE_PRODUCTION`; attempting to register at `08:48 ET` is rejected with `ForecastCutoffExpiredError`; audit re-runs succeed with `REPLAY_AUDIT` referencing parent ID.

---

### Milestone 0.3: Deterministic Signal Opportunity Logger (`STRATEGY_REGISTRY_V0`)
* **Target Path**: `scripts/trading_brain/signals/opportunity_logger.py`, `scripts/trading_brain/strategies/registry_v0.py`
* **Problem Solved**: Resolves circular dependency by bootstrapping from manually frozen, deterministic baseline rules versioned in git (`STRATEGY_REGISTRY_V0`), enabling Phase 0 opportunity logging before Phase 3 statistical certification exists.
* **Baseline Strategies in `STRATEGY_REGISTRY_V0`**:
  1. `STRAT_ALN_LPEU_V0`: London Protrusion Expansion Up breakout pullback.
  2. `STRAT_FIRECRACKER_V0`: Overnight range compression (<35% DRO spent) opening drive.
  3. `STRAT_GOALPOST_BB_V0`: Broken-Broken Asia/London sweep fade toward opposite extreme.
  4. `STRAT_P12_MID_RETEST_V0`: P12 Midline equilibrium retest before 09:45 ET.
* **Functionality**:
  * Evaluates strategy trigger conditions bar-by-bar on fused 1m market data.
  * When a rule condition triggers mechanically, inserts a row in `signal_opportunities`:
    - `trigger_price`, `proposed_stop_bps` (e.g. 12.0 bps), `proposed_target_1_bps` (+10 bps *Cover The Queen*), `proposed_target_2_bps` (+30 bps runner).
  * Evaluates theoretical post-hoc outcome in `signal_outcomes` (realized MFE/MAE in bps).
* **Acceptance Criteria**:
  * Backtest simulation over 10 test sessions accurately logs all eligible opportunities without missing any trigger, completely decoupled from whether a human traded them.

---

### Milestone 0.4: Broker & RiskGuard Ingestion Adapter
* **Target Path**: `scripts/trading_brain/ingest/nt8_broker_adapter.py`
* **Integration Surface**: NinjaTrader 8 via `nt8-mcp-bridge` and `C:\Users\vinay\nt8-riskguard`.
* **Functionality**:
  * Ingests broker orders, fills, partial exits, cancellations, stop modifications, commissions, and slippage into `execution_events`.
  * Ingests RiskGuard hard lockouts, soft friction warnings, and explicit user overrides into `intervention_events`.
  * Enforces idempotency via `UNIQUE(account_id, idempotency_key)`.
  * Connects execution fills to candidate `signal_opportunities` via `opportunity_id` FK when matched.
* **Acceptance Criteria**:
  * Importing a simulated NT8 execution stream containing order submissions, partial fills, scale-outs (+10 bps), and stop modifications produces zero duplicate rows on repeat ingest.

---

### Milestone 0.5: Tape Actuals & Quality Provenance Extractor
* **Target Path**: `scripts/trading_brain/tape/tape_extractor.py`
* **Data Loader Contract**: Uses canonical `load_fused_data(ticker, timeframe="1m", require_historical=True)` combining live tick storage + deep parquet history.
* **Functionality**:
  * Runs at `16:15 ET` post-market.
  * Extracts session HOD, LOD, Open, Close, timestamps in UTC, realized MFE/MAE in Basis Points.
  * Evaluates key level touches (`P12_MID_TOUCHED`, `P12_HIGH_TOUCHED`, `P12_LOW_TOUCHED`, `P70_HIT`, `P70_REVERSED`).
  * Evaluates `LABEL_DAY_TYPE_V1` and `LABEL_EOD_CLASSIFICATION_V1`.
  * Attaches vendor provenance (`TradingView`, `Schwab`, `Tradovate`), contract roll, adjustment policy, and data quality state flags (`CLEAN`, `SUSPECT_TICKS`, `INCOMPLETE_BARS`).
* **Acceptance Criteria**:
  * Runs mechanically on historical sessions; verifies exact output matches verified tape data.

---

## 3. Phase 1: Daily Process Delta & Mechanical Post-Mortem

### Objective
Create a deterministic, 4-way reconciliation engine that produces a single concise, actionable EOD report in under 5 minutes of operator reading time.

---

### Milestone 1.1: 4-Way Mechanical Reconciler
* **Target Path**: `scripts/trading_brain/evaluation/daily_process_delta.py`
* **The 4-Way Reconciliation Quadrant**:
  ```
  1. PRE-MARKET PLAN (08:45 ET Snapshot via prediction_id)
                           ↕
  2. SIGNAL OPPORTUNITIES (All eligible mechanical triggers via registry_v0)
                           ↕
  3. EXECUTIONS & INTERVENTIONS (Actual fills, stops, RiskGuard telemetry)
                           ↕
  4. MEASURED TAPE OUTCOMES (16:15 ET HOD/LOD, Day Type, MFE/MAE)
  ```
* **Executable Label Functions**:
  * `LABEL_DAY_TYPE_V1`: Evaluates `SF`, `LF`, `LT`, `ST`, or `ROTATIONAL_CHOP` with deterministic precedence.
  * `LABEL_EOD_CLASSIFICATION_V1`: Evaluates `R1`, `R2`, `DNP`, `DWP`.
* **Evaluation Metrics Computed**:
  1. **Forecast Accuracy & Multiclass Brier Score**: Evaluates morning probability forecast against realized day type.
  2. **Strategy Expectancy & Opportunity Capture**: Theoretical PnL of all eligible signals vs. realized PnL of executed signals.
  3. **Execution Efficiency**: Fills vs. triggers (slippage in bps, scale-out adherence at +10 bps *Cover The Queen*).
  4. **RiskGuard & Process Compliance**: Count of hard locks, soft friction overrides, and unapproved discretionary trades.

---

### Milestone 1.2: One-Page Process Delta Report
* **Target Path**: `scripts/trading_brain/reports/render_process_delta.py`
* **Output Format**:
  * Markdown file: `data/wargaming/reports/daily_process_delta_YYYY-MM-DD.md`.
  * High-visibility terminal output.
* **Report Sections**:
  1. **Executive Scorecard**: Forecast score, Plan adherence %, Execution capture %, RiskGuard status.
  2. **Plan vs. Tape Delta**: Predicted scenario vs. realized `LABEL_DAY_TYPE_V1` classification.
  3. **Opportunities vs. Execution Matrix**: Table of all eligible signals, action taken (`EXECUTED`, `PASSED`, `MISSED`), and slippage.
  4. **Behavioral & RiskGuard Interventions**: Factual log of overrides or stop adjustments.
  5. **Quarantined Candidate Reflections**: Reviewable user reflection tags awaiting confirmation.
* **Acceptance Criteria**:
  * CLI command `python -m scripts.trading_brain.evaluation.daily_process_delta --date 2026-08-28` runs in <3 seconds and generates the complete one-page report.

---

### Milestone 1.3: Unified Memory Bridge (`.agent/memory.db` Consolidation)
* **Target Path**: `scripts/trading_brain/evaluation/query_outcomes.py`
* **Problem Solved**: Unifies the outcome surfaces so that `trading_brain.sqlite` is the sole canonical source of truth, preventing divergent outcome stats between the self-learning layer and the trading brain.
* **Execution Contract**:
  * Refactors `nq-data-bridge` / `context_manager` outcome queries to delegate directly to `trading_brain.sqlite`.
  * `capture_outcome` becomes a thin writer into `trading_brain.sqlite`.
  * The self-learning skill-proposal gate (`propose_skill`) reads verified outcome statistics directly from `trading_brain.sqlite`.

---

## 4. Phase 2: Minute-Scale Feedback & Blinded Deliberate Practice

### Objective
Bridge the gap between pre-market analysis and live execution through real-time friction and high-repetition blinded simulation drills.

---

### Milestone 2.1: Synchronous RiskGuard Rule (C#) & Python Deviation Annotator
* **Target Paths**:
  * C# Addon: `C:\Users\vinay\nt8-riskguard\Rules\PlanDeviationRule.cs`
  * Python Telemetry: `scripts/trading_brain/guard/deviation_annotator.py`
* **Process Separation Contract**:
  1. **Synchronous Pre-Order Interception (C# in NT8)**:
     * `PlanDeviationRule.cs` runs inside NinjaTrader 8 at order entry time.
     * Reads active daily plan parameters (permitted hours, allowed setups, max risk) pushed from Python at 08:45 ET.
     * When an order violates active plan constraints, raises synchronous modal friction in NT8 requiring explicit user acknowledgment.
     * Hard blocks (e.g. daily loss limit breach) reject the order immediately.
  2. **Asynchronous Post-Submission Telemetry (Python)**:
     * `deviation_annotator.py` consumes the execution stream via MCP post-submission.
     * Logs the deviation event to `intervention_events` and emits audio/visual coaching prompts.

---

### Milestone 2.2: Blinded Deliberate-Practice Replay Engine
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
* **Acceptance Criteria**:
  * Interactive CLI / Web drill runs smoothly; locks answers before revealing bars; grades simulated execution accurately.

---

## 5. Phase 3: Edge Research, Multiclass Calibration & Walk-Forward Promotion

### Objective
Provide statistical machinery for discovering, testing, and promoting decision rules without overfitting, data mining, or regime bias.

---

### Milestone 3.1: Multiclass Brier & Calibration Engine
* **Target Path**: `scripts/trading_brain/research/calibration_engine.py`
* **Functionality**:
  * Computes Multiclass Brier Score and Log Loss across all 5 day-type classes.
  * Generates reliability diagrams (predicted probability buckets vs. empirical hit rates).
  * Compares candidate models against the 3 mandatory baselines:
    1. Unconditional historical base-rate.
    2. Rolling 50-session recency-weighted frequency.
    3. Incumbent production model.

---

### Milestone 3.2: Multi-Fold Rolling Walk-Forward Validator
* **Target Path**: `scripts/trading_brain/research/walk_forward_gate.py`
* **Functionality**:
  * Implements expanding rolling walk-forward folds:
    - *Fold 1*: Train [T0–T3] -> Calibrate [T4] -> Test [T5].
    - *Fold 2*: Train [T1–T4] -> Calibrate [T5] -> Test [T6].
    - *Fold 3*: Train [T2–T5] -> Calibrate [T6] -> Test [T7].
  * Enforces **Purged Folds & Embargoes** to prevent lookahead and autocorrelation leakage.
  * Applies **Benjamini-Hochberg False Discovery Rate (FDR)** control at $\alpha = 0.05$ across the complete research family.
  * Uses **Stationary Block Bootstrap** to calculate dependence-aware confidence bounds on financial time-series.

---

### Milestone 3.3: 1-Time Sealed Shadow Validation & Inconclusive Policy
* **Target Path**: `scripts/trading_brain/research/shadow_runner.py`
* **Power & Sample Requirement**:
  * Requires a minimum prospective sample of $N \ge 60$ sessions with at least $n_k \ge 10$ occurrences per active class.
* **Inconclusive / Failure Policy**:
  * If the shadow test fails to reach statistical significance over the incumbent model ($p > 0.05$) or confidence bounds include zero improvement, the candidate model **FAILS CLOSED** and is **REJECTED**.
  * An inconclusive result **CANNOT** be promoted. The candidate is either discarded or retained in shadow observation mode without live execution authority.

---

### Milestone 3.4: Formal Strategy Registry V1 Promotion
* **Target Path**: `scripts/trading_brain/strategies/registry_v1.py`
* **Functionality**:
  * Promotes statistically verified models from `STRATEGY_REGISTRY_V0` to `STRATEGY_REGISTRY_V1` after passing all walk-forward and shadow gates.
  * Updates `model_registry` with immutable parameter hashes and sets up champion/challenger live tracking.

---

## 6. Phase 4: Typed Intake Catalog & Web Workspace

### Objective
Provide a unified, human-native intake interface and interactive web dashboard for daily wargaming, post-market review, and deliberate practice.

---

### Milestone 4.1: Universal Typed Intake Catalog (`information_items`)
* **Target Path**: `scripts/trading_brain/intake/catalog_router.py`
* **Functionality**:
  * Implements the 9-type information matrix.
  * Ingests free-form markdown plans, voice transcripts, journal entries, chart screenshots, and dynamic options/GEX snapshots.
  * Attaches the canonical intake envelope: `information_id`, `information_type`, `evidence_class`, `time_orientation`, `available_at_utc`, `review_state`, `quality_state`.
  * Enforces the **As-Of Boundary**: Ensures `available_at_utc <= decision_cutoff_utc` on all inputs to prevent hindsight leakage.

---

### Milestone 4.2: Web Dashboard UI Integration
* **Target Path**: `web/` (Next.js, Tailwind CSS, Shadcn/UI, Lightweight Charts)
* **Features**:
  1. **Daily Wargame & Scenario Card View**: Interactive pre-market HUD and decision tree.
  2. **Process Delta Scorecard**: Visual 4-way post-mortem comparison.
  3. **Deliberate Practice Replay Station**: Browser-based blinded chart drill simulator.
  4. **Model Governance & Promotion Dashboard**: Walk-forward validation curves, calibration diagrams, and candidate finding approval queue.

---

## 7. Immediate Next Steps & Review Checkpoints

| Step | Action Item | Target Delivery | Dependency |
| :---: | :--- | :--- | :--- |
| **1** | **Review & Approval of Implementation Plan (v1.1.0)** | User Review | This Document |
| **2** | **Milestone 0.0: Legacy DB Migration & Cutover** (`migrate_legacy_dbs.py`) | Step 1 Approved | Step 1 |
| **3** | **Milestone 0.1: Database Schema & Immutability Triggers** (`schema.sql`) | Milestone 0.0 | Step 2 |
| **4** | **Milestone 0.2: Server-Clock Forecast Snapshot Registrar** (`forecast_registrar.py`) | Milestone 0.1 | Step 3 |
| **5** | **Milestone 0.3: Signal Opportunity Logger** (`opportunity_logger.py` + `registry_v0`) | Milestone 0.1 | Step 3 |
| **6** | **Milestone 0.4: Broker & RiskGuard Ingestion Adapter** (`nt8_broker_adapter.py`) | Milestone 0.1 | Step 3 |
| **7** | **Milestone 0.5: Mechanical Tape Extractor** (`tape_extractor.py`) | Milestone 0.1 | Step 3 |
| **8** | **Phase 0 Operational Verification Gate** (10 live sessions verified) | Phase 0 Done | Step 4–7 |
