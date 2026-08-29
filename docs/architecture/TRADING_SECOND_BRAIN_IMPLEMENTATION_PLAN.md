# 🛠️ Trading Second Brain: Master Implementation Plan

> **Document Version**: 1.0.0  
> **Status**: Comprehensive Phased Engineering Roadmap & Review Document  
> **Architecture Reference**: [`docs/architecture/TRADING_SECOND_BRAIN_MASTER_ARCHITECTURE.md`](file:///c:/Users/vinay/tvDownloadOHLC/docs/architecture/TRADING_SECOND_BRAIN_MASTER_ARCHITECTURE.md) (v4.3.0)  
> **Location**: `docs/architecture/TRADING_SECOND_BRAIN_IMPLEMENTATION_PLAN.md`  
> **Guiding Principle**: *Build the Zero-Human Capture Spine first. Ensure mechanical capture, immutable provenance, and under 5 minutes of daily manual operator overhead before adding complex feedback or research layers.*

---

## 1. Architectural Strategy & Phasing Roadmap

The implementation is structured into **five sequential, independently testable phases**:

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 5-PHASE IMPLEMENTATION ROADMAP                                   │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘

  PHASE 0: ZERO-HUMAN CAPTURE SPINE & ACID DATABASE FOUNDATION
  • Unified SQLite Database (`trading_brain.sqlite`) with Immutability Triggers
  • Pre-Market Forecast Snapshot Registrar (08:45 ET cutoff)
  • Deterministic Signal Opportunity Logger (Records EVERY qualified setup, taken or passed)
  • Broker & RiskGuard Event Ingestion Adapter (NT8 MCP bridge)
  • Mechanical Tape Actuals & Quality Provenance Extractor (16:15 ET)
  
                                  │
                                  ▼
  PHASE 1: DAILY PROCESS DELTA & POST-MORTEM ENGINE
  • 4-Way Mechanical Reconciler (Forecast ↔ Opportunities ↔ Fills ↔ Tape)
  • 5-Class Day-Type Classifier (`LABEL_DAY_TYPE_V1` with MECE precedence)
  • 1-Page EOD Process Delta Markdown & Terminal Report (<5 min human review)
  
                                  │
                                  ▼
  PHASE 2: MINUTE-SCALE FEEDBACK & BLINDED PRACTICE HARNESS
  • RiskGuard Soft Friction Telemetry Bridge
  • Blinded Deliberate-Practice Replay Engine (Hidden dates, locked answers, process grading)
  • Recurring-Error Targeted Drill Generator
  
                                  │
                                  ▼
  PHASE 3: EDGE RESEARCH, MULTICLASS CALIBRATION & PROMOTION GATE
  • Multiclass Brier Score & Log Loss Calibration Engine
  • Multi-Fold Purged Walk-Forward Validator (Expanding historical folds)
  • Benjamini-Hochberg FDR Multiplicity Control & Block Bootstrap Inference
  • 1-Time Sealed Shadow Validation Runner & Champion/Challenger Switch
  
                                  │
                                  ▼
  PHASE 4: TYPED INTAKE CATALOG & WEB WORKSPACE
  • Universal `information_items` Intake Router (9 Information Types)
  • Human-Native Journal & Chart Extraction with Hindsight Boundary (`available_at_utc <= cutoff`)
  • Visual Next.js / Tailwind Wargaming & Practice Dashboard
```

---

## 2. Phase 0: Zero-Human Capture Spine & Database Foundation

### Objective
Establish the immutable relational ledger and automated data pipelines so that every market session, pre-market plan, trading signal opportunity, broker order/fill, and tape outcome is captured automatically with zero manual data entry.

---

### Milestone 0.1: Unified ACID Database Schema & Migration Engine
* **Target Path**: `scripts/trading_brain/db/`
  * `schema.sql`: Complete DDL for all 12 core tables.
  * `init_db.py`: Database initializer with PRAGMA integrity checks, foreign key enforcement, and WAL configuration.
  * `connection.py`: Context manager for thread-safe, transactional database access.
* **Database File**: `data/wargaming/db/trading_brain.sqlite`.
* **Core Table Definitions**:
  1. `information_items`: Universal typed intake catalog envelope.
  2. `forecast_snapshots`: Immutable pre-market predictions (git hash, config hash, data manifest hash, full-precision probabilities).
  3. `signal_opportunities`: Every mechanically qualified strategy setup (taken or passed).
  4. `signal_disposition_events`: User/system disposition (`EXECUTED`, `PASSED`, `MISSED`, `OFFLINE`).
  5. `signal_outcomes`: Versioned theoretical MFE/MAE and target outcomes.
  6. `session_tape_actuals`: Mechanical tape facts with vendor provenance, contract roll, and quality flags.
  7. `execution_events`: Monotonic broker event stream (orders, fills, partial exits, stop modifications, slippage).
  8. `intervention_events`: RiskGuard hard locks, soft friction events, and explicit overrides.
  9. `drill_attempts`: Blinded deliberate practice attempts, locked user decisions, and process scores.
  10. `behavioral_declarations`: Subjective user reflection and habit compliance declarations.
  11. `candidate_findings`: Staged statistical hypotheses under FDR control.
  12. `strategies` & `model_registry`: Certified strategy definitions, parameter versions, and risk constraints.
* **Immutability Triggers**:
  * `prevent_forecast_update`, `prevent_forecast_delete` on `forecast_snapshots`.
  * `prevent_opportunity_update`, `prevent_opportunity_delete` on `signal_opportunities`.
  * `prevent_execution_update`, `prevent_execution_delete` on `execution_events`.
* **Verification & Acceptance Criteria**:
  * Unit test `tests/test_trading_brain_db.py` proves:
    - Tables initialize cleanly with foreign keys enabled (`PRAGMA foreign_keys = ON`).
    - Attempting an `UPDATE` or `DELETE` on a live forecast snapshot raises a hard SQLite error.
    - Partial unique index enforces only one `LIVE_PRODUCTION` forecast per ticker and cutoff.
    - Append-only corrections link correctly via `corrects_event_id`.

---

### Milestone 0.2: Pre-Market Forecast Snapshot Registrar
* **Target Path**: `scripts/trading_brain/forecast/forecast_registrar.py`
* **Integration Points**:
  * `scripts/wargaming/generate_daily_wargame.py`
  * `scripts/concepts/runner.py`
* **Functionality**:
  * Freezes the pre-market forecast at the exact cutoff time (`08:45 ET`).
  * Computes and records:
    - `git_commit_hash`: Active repository commit.
    - `environment_hash`: SHA-256 hash of active environment/packages.
    - `config_hash`: SHA-256 of active wargame and concept configuration.
    - `data_manifest_hash`: SHA-256 checksum of input 1m/1d market data.
    - `probabilities`: Full-precision floats for `SF`, `LF`, `LT`, `ST`, `ROTATIONAL_CHOP`.
    - `abstain_flag` & `abstain_reason`: Set if data quality, provider count, or freshness fails.
* **Verification & Acceptance Criteria**:
  * Unit test verifies that calling `ForecastRegistrar.register_live_forecast()` writes an immutable record. Re-running in live mode fails closed with duplicate key error; re-running in audit mode creates a valid `REPLAY_AUDIT` record referencing the parent ID.

---

### Milestone 0.3: Deterministic Signal Opportunity Logger
* **Target Path**: `scripts/trading_brain/signals/opportunity_logger.py`
* **Functionality**:
  * Evaluates active certified strategy rules (e.g. `ALN_LPEU`, `FIRECRACKER_EXPANSION`, `BROKEN_BROKEN_GOALPOST`) bar-by-bar during the session.
  * When entry conditions are met mechanically, logs an immutable row in `signal_opportunities`.
  * Logs trigger price, proposed protective stop (in bps), Target 1 (+10 bps Cover The Queen), and Target 2 (+30 bps runner).
  * Records whether the user/bot executed the signal (`signal_disposition_events`).
* **Verification & Acceptance Criteria**:
  * Backtest simulation over 10 test sessions accurately logs all eligible opportunities without missing any trigger, regardless of execution state.

---

### Milestone 0.4: Broker & RiskGuard Ingestion Adapter
* **Target Path**: `scripts/trading_brain/ingest/nt8_broker_adapter.py`
* **Integration Surface**: NinjaTrader 8 via `nt8-mcp-bridge` and `nt8-riskguard`.
* **Functionality**:
  * Ingests broker orders, fills, cancellations, stop modifications, commissions, and slippage into `execution_events`.
  * Ingests RiskGuard hard lockouts, soft friction warnings, and explicit user overrides into `intervention_events`.
  * Enforces idempotency via `UNIQUE(account_id, idempotency_key)`.
* **Verification & Acceptance Criteria**:
  * Test script imports a simulated NT8 execution stream containing order submissions, partial fills, scale-outs (+10 bps), and stop modifications; verifies zero duplicates on repeat ingest.

---

### Milestone 0.5: Tape Actuals & Quality Provenance Extractor
* **Target Path**: `scripts/trading_brain/tape/tape_extractor.py`
* **Functionality**:
  * Runs at `16:15 ET` post-market.
  * Extracts session HOD, LOD, Open, Close, timestamps in UTC, realized MFE/MAE in Basis Points.
  * Evaluates key level touches (`P12_MID_TOUCHED`, `P12_HIGH_TOUCHED`, `P12_LOW_TOUCHED`, `P70_HIT`, `P70_REVERSED`).
  * Attaches vendor provenance (`TradingView`, `Schwab`, `Tradovate`), contract roll, adjustment policy, and data quality state flags (`CLEAN`, `SUSPECT_TICKS`, `INCOMPLETE_BARS`).
* **Verification & Acceptance Criteria**:
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
  2. SIGNAL OPPORTUNITIES (All eligible mechanical triggers)
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
* **Verification & Acceptance Criteria**:
  * CLI command `python -m scripts.trading_brain.evaluation.daily_process_delta --date 2026-08-28` runs in <3 seconds and generates the complete one-page report.

---

## 4. Phase 2: Minute-Scale Feedback & Blinded Deliberate Practice

### Objective
Bridge the gap between pre-market analysis and live execution through real-time friction and high-repetition blinded simulation drills.

---

### Milestone 2.1: RiskGuard Soft-Friction Telemetry Bridge
* **Target Path**: `scripts/trading_brain/guard/friction_bridge.py`
* **Functionality**:
  * Compares inbound NT8 orders against the active pre-market plan in `forecast_snapshots`.
  * If an order deviates from the plan (e.g. trading during a `NO_TRADE` window or taking an un-wargamed setup), triggers a soft friction prompt requiring explicit user acknowledgment.
  * Logs the event and acknowledgment to `intervention_events`.

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
* **Verification & Acceptance Criteria**:
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
  * Applies **Benjamini-Hochberg False Discovery Rate (FDR)** control at alpha = 0.05 across the complete research family.
  * Uses **Stationary Block Bootstrap** to calculate dependence-aware confidence bounds on financial time-series.
  * Evaluates the **1-Time Sealed Shadow Test** (2026 data).
* **Verification & Acceptance Criteria**:
  * Test validation script runs on synthetic/historical datasets; correctly rejects overfitted hypotheses; promotes only models passing all gates.

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
| **1** | **Review & Approval of Implementation Plan** | User Review | This Document |
| **2** | **Phase 0 Database DDL & Initializer** (`trading_brain.sqlite`) | Milestone 0.1 | Step 1 |
| **3** | **Pre-Market Forecast Snapshot Registrar** (`forecast_registrar.py`) | Milestone 0.2 | Step 2 |
| **4** | **Signal Opportunity Logger** (`opportunity_logger.py`) | Milestone 0.3 | Step 2 |
| **5** | **Daily Process Delta Engine** (`daily_process_delta.py`) | Milestone 1.1 | Step 2, 3, 4 |
