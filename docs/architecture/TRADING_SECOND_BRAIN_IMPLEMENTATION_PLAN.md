# 🛠️ Trading Second Brain: Master Implementation Plan

> **Document Version**: 3.0.0 (Execution-Hardened Specification)  
> **Status**: Canonical Phased Engineering Roadmap & Review Document  
> **Architecture Reference**: [`docs/architecture/TRADING_SECOND_BRAIN_MASTER_ARCHITECTURE.md`](file:///c:/Users/vinay/tvDownloadOHLC/docs/architecture/TRADING_SECOND_BRAIN_MASTER_ARCHITECTURE.md) (v4.3.0)  
> **Location**: `docs/architecture/TRADING_SECOND_BRAIN_IMPLEMENTATION_PLAN.md`  
> **Core Operating Principle**: *Construct the verified schema and immutable plan ledger first. Prove legacy reconciliation in shadow mode with rollback fences. Guarantee server-enforced cutoff gates, as-of decision time contracts, and under 5 minutes of daily operator review before enabling downstream evaluation or research gates.*

---

## 1. Architectural Strategy & Phasing Roadmap

The implementation is structured into **five sequential, independently testable phases**. **Phase 0 is a self-contained, low-manual-input capture candidate** that must pass an operational scenario gate before Phase 1 commences:

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 5-PHASE ENGINEERING ROADMAP                                      │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘

  PHASE 0: LOW-MANUAL-INPUT CAPTURE SPINE & ACID DATABASE FOUNDATION [CANDIDATE SPINE]
  • M0.1: Canonical SQLite Schema & Immutability Trigger Matrix (`trading_brain.sqlite` - 16 tables)
  • M0.2: Immutable Plan Snapshot & Lifecycle Event Ledger (`plan_snapshots` + Prisma adapter)
  • M0.3: Shadow Legacy Data Import, Dual-Hash Reconciliation & Rollback Fence
  • M0.4: Server-Enforced Forecast Snapshot Registrar (Database-generated `received_at_utc`)
  • M0.5: As-Of Signal Opportunity Logger (Frozen `STRATEGY_REGISTRY_V0` + decision_time_utc)
  • M0.6: Hardened NT8 Broker Ingestion & Reconciliation Adapter (Idempotency, cursor state, gaps)
  • M0.7: Measured Tape Actuals Extractor (Live storage path + explicit ingest manifest)
  • M0.8: Scenario-Based Operational Verification Gate (6 edge scenarios + 10 live sessions soak)
  
                                  │ [Operational Gate: Scenario Suite Pass + 10 Live Sessions]
                                  ▼
  PHASE 1: DAILY PROCESS DELTA & POST-MORTEM ENGINE
  • M1.1: 4-Way Mechanical Reconciler (`daily_process_delta.py` with MECE 5-class day types)
  • M1.2: One-Page Event-First EOD Process Delta Report (8 golden session assertions; no composite grades)
  • M1.3: Read-Only Memory Bridge (`agent_memory_bridge.py` — preserves `.agent/memory.db` boundary)
  
                                  │
                                  ▼
  PHASE 2: MINUTE-SCALE FEEDBACK & BLINDED DELIBERATE PRACTICE
  • M2.1: Python Post-Submission Deviation Annotator (`deviation_annotator.py`)
  • M2.2: Cross-Repository C# RiskGuard Plan-Friction Addon (`nt8-riskguard` isolated milestone)
  • M2.3: Blinded Deliberate-Practice Replay Engine (Hidden dates/outcomes, locked commitments, split custody)
  • M2.4: Recurring-Error Targeted Drill Generator
  
                                  │
                                  ▼
  PHASE 3: RESEARCH GATES, CALIBRATION & MULTI-TIER PROMOTION
  • M3.1: Multiclass Proper-Score Loss Engine (Multiclass Brier & Log Loss vs. 3 baselines)
  • M3.2: Multi-Fold Purged Walk-Forward Validator (Expanding folds + BH/BY/Holm multiplicity control)
  • M3.3: Preregistered Shadow Validation Gate (Task-specific MDE, power >= 0.80, fail-closed policy)
  • M3.4: Decoupled Multi-Tier Promotion Engine (Forecast != Signal != Policy != Portfolio)
  
                                  │
                                  ▼
  PHASE 4: TYPED INTAKE CATALOG & WEB WORKSPACE
  • M4.1: Universal `information_items` Intake Router (9 Information Types + Consumer As-Of Filters)
  • M4.2: Visual Next.js / Tailwind Wargaming, Process Delta & Practice Dashboard
```

---

## 2. Phase 0: Low-Manual-Input Capture Spine & Database Foundation

### Objective
Establish the canonical relational schema, immutable plan ledger, server-enforced cutoff gates, and idempotent ingestion adapters.

---

### Milestone 0.1: Canonical SQLite Schema & Complete Table Classification
* **Target Paths**:
  * `scripts/trading_brain/db/schema.sql`: Complete DDL for all 16 tables.
  * `scripts/trading_brain/db/init_db.py`: Initializer with WAL mode, busy timeout, and foreign key verification (`PRAGMA foreign_keys = ON`).
  * `scripts/trading_brain/db/connection.py`: Thread-safe context manager enforcing foreign key constraints on every connection.
  * `tests/test_trading_brain_db.py`: Schema and trigger test suite registered in `pytest`.
* **Database Location**: `data/wargaming/db/trading_brain.sqlite`.
* **Complete 16-Table Classification**:
  1. **Append-Only Evidence Ledgers (11 tables)**:
     - `information_items`: Universal typed intake catalog envelope.
     - `plan_snapshots`: Immutable pre-market trading plan snapshots.
     - `plan_lifecycle_events`: State transition events (`SUBMITTED`, `SUPERSEDED`, `CANCELLED`).
     - `plan_amendments`: Append-only plan adjustments with supersession links.
     - `forecast_snapshots`: Immutable pre-market quantitative predictions.
     - `signal_opportunities`: As-of mechanically eligible setup triggers.
     - `signal_disposition_events`: User/system disposition events (`EXECUTED`, `PASSED`, `MISSED`, `OFFLINE`).
     - `signal_outcomes`: Versioned theoretical MFE/MAE outcomes evaluated post-hoc.
     - `session_tape_actuals`: Measured tape actuals with vendor provenance and quality state.
     - `execution_events`: Monotonic broker event stream (orders, fills, partial exits, stop modifications).
     - `intervention_events`: Disentangled guard lockouts, soft friction warnings, and deviation annotations.
     - `drill_attempts`: Blinded deliberate practice attempts and locked user decisions (DDL in Phase 0; writers in Phase 2).
     - `behavioral_declarations`: Subjective user reflections (DDL in Phase 0; writers in Phase 1).
  2. **Review Queues with Explicit State Transitions (2 tables)**:
     - `unmatched_execution_links`: Staging table for ambiguous execution-to-opportunity links.
     - `candidate_findings`: Staged statistical hypotheses under FDR control.
  3. **Mutable Versioned Configuration / Registries (2 tables)**:
     - `strategies`: Strategy metadata, rules doc links, and risk constraints.
     - `model_registry`: Versioned model parameter hashes and champion/challenger state.
  4. **State Tracking (1 table)**:
     - `broker_ingest_state`: Cursor and pagination checkpoint state for broker adapters.
* **Exhaustive Immutability Trigger Matrix**:
  All 11 append-only evidence tables are protected by paired `BEFORE UPDATE` and `BEFORE DELETE` triggers that raise SQLite failures:
  `information_items`, `plan_snapshots`, `plan_lifecycle_events`, `plan_amendments`, `forecast_snapshots`, `signal_opportunities`, `signal_disposition_events`, `signal_outcomes`, `session_tape_actuals`, `execution_events`, `intervention_events`, `drill_attempts`, `behavioral_declarations`.
* **Acceptance Gate**:
  * Command: `pytest tests/test_trading_brain_db.py`
  * Assertions:
    - All 16 tables initialize cleanly with foreign keys enforced.
    - `UPDATE` and `DELETE` on all 11 append-only tables raise immediate SQLite exceptions.
    - Partial unique index permits exactly one `LIVE_PRODUCTION` forecast per `(session_date, ticker, effective_cutoff_utc)`.
    - Partial unique index permits exactly one `CURRENT` plan snapshot per `(session_date, ticker, preparation_cutoff_utc)`.

---

### Milestone 0.2: Immutable Pre-Market Plan Snapshot & Lifecycle Event Ledger
* **Target Path**: `scripts/trading_brain/plans/plan_adapter.py`
* **Problem Solved**: Fulfills the Phase 0 promise to freeze the pre-market plan by capturing Prisma `TradePlan` records into an immutable evidence ledger with server-verified timestamps.
* **Schema**:
  ```sql
  CREATE TABLE plan_snapshots (
      plan_snapshot_id TEXT PRIMARY KEY,        -- UUID v4
      session_date DATE NOT NULL,
      ticker TEXT NOT NULL,
      preparation_cutoff_utc TIMESTAMP NOT NULL,
      source_system TEXT NOT NULL,              -- 'PRISMA_WEB', 'MARKDOWN_CLI', 'MANUAL_IMPORT'
      source_plan_id TEXT,                      -- Reference to Prisma TradePlan.id
      supersedes_plan_snapshot_id TEXT,         -- Nullable FK for replacement snapshots
      
      -- Plan Content & Declarations
      verbatim_plan_text TEXT NOT NULL,         -- Unaltered user plan text
      primary_bias TEXT NOT NULL,               -- 'BULLISH', 'BEARISH', 'NEUTRAL', 'NO_TRADE'
      wargamed_scenarios_json TEXT NOT NULL,    -- Structured scenarios and expected branches
      invalidation_levels_json TEXT NOT NULL,   -- Explicit price invalidation boundaries
      max_intended_risk_bps REAL NOT NULL,      -- Risk budget declaration
      permitted_strategies_json TEXT NOT NULL,  -- Active strategy IDs for the session
      
      -- As-Of Provenance Timestamps (Server-Generated)
      received_at_utc TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
      provenance_class TEXT NOT NULL,           -- 'EX_ANTE_DECLARED' or 'POST_HOC_RECONSTRUCTION'
      created_at_utc TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (supersedes_plan_snapshot_id) REFERENCES plan_snapshots(plan_snapshot_id)
  );

  CREATE TABLE plan_lifecycle_events (
      event_id TEXT PRIMARY KEY,
      plan_snapshot_id TEXT NOT NULL,
      event_type TEXT NOT NULL,                 -- 'SUBMITTED', 'SUPERSEDED', 'CANCELLED'
      recorded_at_utc TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
      reason TEXT,
      FOREIGN KEY (plan_snapshot_id) REFERENCES plan_snapshots(plan_snapshot_id)
  );

  CREATE TABLE plan_amendments (
      amendment_id TEXT PRIMARY KEY,
      plan_snapshot_id TEXT NOT NULL,
      supersedes_amendment_id TEXT,
      amendment_seq INTEGER NOT NULL,
      amended_at_utc TIMESTAMP NOT NULL,
      reason_code TEXT NOT NULL,                -- 'MACRO_NEWS', 'REGIME_CHANGE', 'DISCIPLINE_PAUSE'
      amendment_text TEXT NOT NULL,
      amended_bias TEXT,
      amended_risk_bps REAL,
      FOREIGN KEY (plan_snapshot_id) REFERENCES plan_snapshots(plan_snapshot_id),
      FOREIGN KEY (supersedes_amendment_id) REFERENCES plan_amendments(amendment_id)
  );

  CREATE VIEW v_current_active_plan AS
  SELECT p.* FROM plan_snapshots p
  WHERE p.provenance_class = 'EX_ANTE_DECLARED'
    AND NOT EXISTS (
      SELECT 1 FROM plan_lifecycle_events e 
      WHERE e.plan_snapshot_id = p.plan_snapshot_id AND e.event_type = 'CANCELLED'
    )
    AND NOT EXISTS (
      SELECT 1 FROM plan_snapshots p2 
      WHERE p2.supersedes_plan_snapshot_id = p.plan_snapshot_id
    );
  ```
* **As-Of Ingestion Logic**:
  * When snapshot is received, if database clock `received_at_utc <= preparation_cutoff_utc`, classified as `EX_ANTE_DECLARED`.
  * If `received_at_utc > preparation_cutoff_utc`, classified as `POST_HOC_RECONSTRUCTION` (excluded from active execution or ex-ante wargame evaluation).
* **Acceptance Gate**:
  * Command: `pytest tests/test_plan_adapter.py`
  * Assertions: Prisma plan imported; plans received after cutoff stamped `POST_HOC_RECONSTRUCTION`; cancellation event appends to lifecycle ledger; `v_current_active_plan` view dynamically resolves current active plan.

---

### Milestone 0.3: Shadow Legacy Data Import, Dual-Hash Reconciliation & Rollback Fence
* **Target Paths**:
  * `scripts/trading_brain/migrations/migrate_legacy_dbs.py`
  * `scripts/trading_brain/db/wargame_db_bridge.py`
* **Sequencing Contract & Rollback Specification**:
  1. **Pre-Cutover Backup**: Creates online backup `data/wargaming/db/backups/pre_cutover_legacy_state.tar.gz`.
  2. **Cursor Fence**: Records max timestamps and row counts from legacy SQLite files (`system_wargames.sqlite`, `market_actuals.sqlite`, `mickey_ground_truth.sqlite`).
  3. **Shadow Staging Import**: Transforms records into canonical schema with dual-hash lineage:
     - `legacy_source_hash`: SHA-256 of raw legacy record.
     - `canonical_payload_hash`: SHA-256 of canonical normalized JSON (sorted keys, float tolerance $|a - b| \le 1\times 10^{-6}$).
  4. **Dual-Read Comparison Mode**: `wargame_db_bridge.py` runs in comparison mode for all historical queries to verify identical outputs.
  5. **Application-Level Writer Switch**: `generate_daily_wargame.py` and `reconcile_wargame.py` switch to canonical writes via `trading_brain.sqlite`.
  6. **Rollback Command**: `python -m scripts.trading_brain.migrations.migrate_legacy_dbs --rollback` verifies cursor fence and restores write routing to legacy DBs in <10 seconds without lost writes.
  7. **Legacy Retention**: Legacy files remain readable in place (no filesystem write locks that could disrupt background readers).
* **Acceptance Gate**:
  * Command: `python -m scripts.trading_brain.migrations.migrate_legacy_dbs --verify`
  * Assertions: 100% record match across historical dates; dual-hash checks pass; rollback command tested and verified.

---

### Milestone 0.4: Server-Enforced Pre-Market Forecast Registrar
* **Target Path**: `scripts/trading_brain/forecast/forecast_registrar.py`
* **Temporal Cutoff Gate**:
  * The registrar enforces the complete temporal contract:
    - `source_data_max_timestamp_utc <= effective_cutoff_utc` (no future bar data).
    - `received_at_utc`: Generated by database clock (`CURRENT_TIMESTAMP`).
    - `registration_deadline_utc`: `effective_cutoff_utc + model_input_contract.commit_grace_period` (model-specific certified grace window).
  * **Fail-Closed Rule**: If `received_at_utc > registration_deadline_utc`, any submission tagged `LIVE_PRODUCTION` is **REJECTED** with `ForecastCutoffExpiredError` or forced to `REPLAY_AUDIT`. Post-hoc live backfilling is physically impossible.
  * **SQL Constraint**:
    ```sql
    CONSTRAINT ck_live_cutoff_timing CHECK (
        forecast_mode <> 'LIVE_PRODUCTION' OR
        received_at_utc <= registration_deadline_utc
    )
    ```
* **Acceptance Gate**:
  * Command: `pytest tests/test_forecast_registrar.py`
  * Assertions: Registration before deadline succeeds as `LIVE_PRODUCTION`; registration after deadline fails closed; replay audits write `REPLAY_AUDIT` with `original_prediction_id`.

---

### Milestone 0.5: As-Of Signal Opportunity Logger (`STRATEGY_REGISTRY_V0`)
* **Target Paths**:
  * `scripts/trading_brain/signals/opportunity_logger.py`
  * `scripts/trading_brain/strategies/registry_v0.py`
* **Operating Scope**: Explicitly labeled `EXPERIMENTAL_CAPTURE_ONLY` (no live execution authority, no trade recommendations).
* **Strict As-Of Decision Time Contract**:
  * Evaluates strategy rules on bar-close:
    $$\text{bar\_end\_utc} \le \text{decision\_time\_utc}$$
    $$\text{bar\_available\_at\_utc} \le \text{decision\_time\_utc}$$
    $$\text{every feature\_input.available\_at\_utc} \le \text{decision\_time\_utc}$$
  * Zero future bar lookahead.
  * Deduplication key: `(session_date, ticker, strategy_id, bar_timestamp_utc)`.
  * Theoretical outcomes written post-hoc to `signal_outcomes`, strictly separated from ex-ante `signal_opportunities`.
* **Strategy V0 Deterministic Rule Definitions**:
  1. `STRAT_ALN_LPEU_V0`: London Protrusion Expansion Up breakout pullback; requires clean Asia/London session data; fails closed on missing sessions.
  2. `STRAT_FIRECRACKER_V0`: Overnight range compression (<35% DRO spent) opening drive.
  3. `STRAT_GOALPOST_BB_V0`: Broken-Broken Asia/London sweep fade toward opposite extreme.
  4. `STRAT_P12_MID_RETEST_V0`: P12 Midline equilibrium retest before 09:45 ET.
* **Acceptance Gate**:
  * Command: `pytest tests/test_opportunity_logger.py`
  * Golden Fixtures: Tested against 5 golden session datasets with independently verified expected-event ledgers (positive triggers, negative near-misses, duplicate suppression, and boundary bar-close cases).

---

### Milestone 0.6: Hardened NT8 Broker Ingestion & Reconciliation Adapter
* **Target Path**: `scripts/trading_brain/ingest/nt8_broker_adapter.py`
* **Functionality & Edge-Case Reconciliation**:
  * Ingests broker orders, fills, cancellations, partial executions, stop modifications, commissions, and slippage into `execution_events`.
  * Persists cursor state in `broker_ingest_state` across process restarts.
  * Reconciles position snapshots against reconstructed event state.
  * Captures broker-owned order ID replacements and late commission corrections via `corrects_event_id`.
  * **Unmatched Link Isolation**: Execution-to-opportunity matching uses deterministic criteria. If an execution cannot be matched unambiguously to a single `opportunity_id`, it is flagged `AMBIGUOUS_MATCH` and written to `unmatched_execution_links` for review rather than guessing.
* **Disentangled `intervention_events` Schema**:
  ```sql
  CREATE TABLE intervention_events (
      intervention_id TEXT PRIMARY KEY,
      session_date DATE NOT NULL,
      ticker TEXT NOT NULL,
      account_id TEXT NOT NULL,
      producer TEXT NOT NULL,                  -- 'NT8_RISKGUARD_CS', 'PYTHON_DEVIATION_ANNOTATOR', 'MANUAL'
      producer_version TEXT NOT NULL,
      authority_class TEXT NOT NULL,           -- 'HARD_LOCKOUT_ENFORCED', 'SOFT_FRICTION_PROMPTED', 'OBSERVED_DEVIATION_ANNOTATION'
      action_mode TEXT NOT NULL,               -- 'ACTING', 'SHADOW'
      rule_id TEXT NOT NULL,
      rule_version TEXT NOT NULL,
      observed_value REAL,
      threshold_value REAL,
      enforced BOOLEAN NOT NULL,
      override_requested BOOLEAN DEFAULT FALSE,
      override_accepted BOOLEAN DEFAULT FALSE,
      event_timestamp_utc TIMESTAMP NOT NULL,
      created_at_utc TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  );
  ```
* **Acceptance Gate**:
  * Command: `pytest tests/test_nt8_broker_adapter.py`
  * Fixtures: Verified against synthetic streams + captured provider traces (`Sim101`, `Provider31`) covering reconnects, out-of-order fills, null-order executions, stop modifications, partial fills, and ambiguous opportunity scenarios.

---

### Milestone 0.7: Measured Tape Actuals Extractor
* **Target Path**: `scripts/trading_brain/tape/tape_extractor.py`
* **Named Primary Sources**:
  * Session classification & HOD/LOD timestamps $\rightarrow$ `data/live/{ticker}_1m.parquet` live storage.
  * Settlement & official close $\rightarrow$ verified daily bar feed.
  * Historical backfills $\rightarrow$ deep parquet archive via `load_fused_data(require_historical=True)`.
* **Tape Row Schema & Lineage**:
  Captures `ingest_id`, `source_system`, `expected_bar_count`, `actual_bar_count`, `content_hash`, `quality_state` (`CLEAN`, `SUSPECT_TICKS`, `INCOMPLETE_BARS`), and `supersedes_actual_id`.
  Evaluates `LABEL_DAY_TYPE_V1` and `LABEL_EOD_CLASSIFICATION_V1`.
* **Acceptance Gate**:
  * Command: `pytest tests/test_tape_extractor.py`
  * Fixtures: Verified against 5 benchmark tape sessions (normal, early close, DST transition, contract roll, and missing bar session).

---

### Milestone 0.8: Scenario-Based Operational Verification Gate
* **Target Path**: `scripts/trading_brain/testing/operational_soak_gate.py`
* **Operational Acceptance Suite**:
  * Phase 0 is formally certified only when it passes:
    1. **Automated Scenario Test Suite**:
       - *Scenario A*: No-trade session (zero signals, zero fills $\rightarrow$ cleanly recorded).
       - *Scenario B*: Early close session (holiday schedule correctly handled).
       - *Scenario C*: DST transition session (UTC vs. ET window correctness).
       - *Scenario D*: Contract roll date (continuous vs. actual contract mapping).
       - *Scenario E*: Feed outage & broker reconnect (gap recovery and deduplication).
       - *Scenario F*: Database crash & recovery (WAL rollback and PRAGMA integrity pass).
    2. **Quantified Live Soak Metrics**:
       - 10 consecutive live trading sessions captured.
       - 0 unexplained data loss.
       - 0 duplicate canonical events.
       - 100% gap reconciliation or explicit quarantine in `unmatched_execution_links`.
       - Operator review time $<5$ minutes on $\ge 90\%$ of standard sessions.

---

## 3. Phase 1: Daily Process Delta & Mechanical Post-Mortem

### Objective
Create a deterministic, event-first 4-way reconciliation engine that produces a single concise, actionable EOD report in under 5 minutes of operator reading time without Goodhart-prone composite grading.

---

### Milestone 1.1: 4-Way Mechanical Reconciler
* **Target Path**: `scripts/trading_brain/evaluation/daily_process_delta.py`
* **The 4-Way Reconciliation Quadrant**:
  ```
  1. PRE-MARKET PLAN (v_current_active_plan + forecast_snapshots @ 08:45 ET)
                           ↕
  2. SIGNAL OPPORTUNITIES (All eligible mechanical triggers via registry_v0)
                           ↕
  3. EXECUTIONS & INTERVENTIONS (Actual fills, stops, RiskGuard telemetry)
                           ↕
  4. MEASURED TAPE OUTCOMES (16:15 ET HOD/LOD, Day Type, MFE/MAE)
  ```
* **Metrics Computed (Event-First, Policy-Driven)**:
  1. **Session Forecast Loss**: Computes proper-score realized loss for the single session (labeled "session forecast loss", reserving calibration/skill claims for accumulated samples).
  2. **Opportunity Realization Table**: Explicit counts of eligible signals: $N_{\text{total}}$, $N_{\text{executed}}$, $N_{\text{passed}}$, $N_{\text{missed}}$.
  3. **Execution Capture Delta**: Compares actual execution against the strategy's registered execution policy (e.g. registered scale-out targets from `strategies.execution_policy_json`).
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
  * Command: `pytest tests/test_process_delta_report.py`
  * Golden Assertions: Tested across 8 golden session archetypes (no-trade day, missing plan, abstained forecast, ambiguous execution link, RiskGuard event, incomplete tape, plan amendment, discretionary trade with no signal).

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
  * Compares executed orders against the active plan in `v_current_active_plan`.
  * Flags observable deviations (e.g. unapproved strategy, trading outside permitted window), logs an event in `intervention_events` with `authority_class = 'OBSERVED_DEVIATION_ANNOTATION'`, and emits visual/audio coaching alerts.

---

### Milestone 2.2: Cross-Repository C# RiskGuard Plan-Friction Addon
* **Target Path**: `C:\Users\vinay\nt8-riskguard\src\Rules\PlanFrictionRule.cs` (in `nt8-riskguard` repo).
* **Governance & Compilation Contract**:
  * Managed as a dedicated cross-repository milestone with its own isolated test suite.
  * Deployed and compiled via `nt_compile`.
* **Safety Contract**:
  * Synchronous pre-order evaluation in NinjaTrader 8.
  * Reads daily plan constraints pushed from Python at 08:45 ET.
  * **Fail-Safe Invariant**: If Python bridge is offline or plan context is missing, plan friction **defaults to disabled/shadow** and **NEVER blocks trades**.
  * **Exit Preservation**: Plan friction **NEVER intercepts or delays risk-reducing or protective exit orders**.

---

### Milestone 2.3: Blinded Deliberate-Practice Replay Engine
* **Target Path**: `scripts/trading_brain/practice/drill_engine.py`
* **Split Custody & Anti-Memorization Invariants**:
  * Assessment session IDs are strictly held out and cannot overlap training/calibration sets.
  * Dates, symbols, future bars, and original plans are blinded before answer lock.
  * **Answer Lock**: User commits to Bias (`BULLISH`, `BEARISH`, `NEUTRAL`), Setup / `NO_TRADE`, Invalidation Level, Entry Price, Stop (bps), and Target (bps). Lock timestamp is immutable.
  * Reveals subsequent bars and grades process adherence against the versioned strategy rule (not replay PnL).
  * Assessment sessions retire permanently once results influence drill selection.
  * Records the attempt in `drill_attempts`.
* **Acceptance Gate**:
  * Command: `pytest tests/test_drill_engine.py`
  * Assertions: Hidden dates/outcomes cannot be accessed before lock; answer lock is immutable; process score correctly evaluates strategy rules.

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
* **Acceptance Gate**:
  * Command: `pytest tests/test_calibration_engine.py`
  * Assertions: Verified against known mathematical array fixtures; baselines fitted inside each fold.

---

### Milestone 3.2: Multi-Fold Purged Walk-Forward Validator
* **Target Path**: `scripts/trading_brain/research/walk_forward_gate.py`
* **Multiplicity Procedure Specification**:
  * Pre-specified multiplicity procedures:
    - **Benjamini-Hochberg (BH)**: Selected under positive regression dependence.
    - **Benjamini-Yekutieli (BY)**: Selected under arbitrary dependence.
    - **Holm-Bonferroni**: Selected for strict family-wise error rate control.
  * Enforces **Purged Folds & Embargoes** to prevent lookahead and autocorrelation leakage.
  * Uses **Stationary Block Bootstrap** / Newey-West HAC standard errors for financial time-series dependence.
* **Acceptance Gate**:
  * Command: `pytest tests/test_walk_forward_gate.py`
  * Assertions: Purge/embargo gaps verified; complete research family accounted for.

---

### Milestone 3.3: Preregistered Shadow Validation Gate
* **Target Path**: `scripts/trading_brain/research/shadow_gate.py`
* **Execution Contract**:
  * Consumes a preregistered evaluation contract: primary proper score, prospective power ($1-\beta \ge 0.80$), task-specific MDE, and economic threshold after costs.
  * Evaluates 1-time sealed shadow data.
  * **Terminal States**: `PROMOTED`, `REJECTED`, `INCONCLUSIVE_WAITING`, `INVALID_TEST`.
  * **Fail-Closed Rule**: An inconclusive test is **NEVER** promoted. `INVALID_TEST` can never become `PROMOTED`.
* **Acceptance Gate**:
  * Command: `pytest tests/test_shadow_gate.py`
  * Assertions: Sealed holdout cannot be reopened after inspection; fail-closed behavior verified.

---

### Milestone 3.4: Decoupled Multi-Tier Promotion Engine
* **Target Path**: `scripts/trading_brain/research/promotion_orchestrator.py`
* **Four Independent Promotion Tiers**:
  1. **Tier 1 (Forecast Model)**: Evaluated on proper-score calibration and discrimination.
  2. **Tier 2 (Signal Model)**: Evaluated on opportunity expectancy and precision.
  3. **Tier 3 (Execution Policy)**: Evaluated on realized EV in R after commissions and slippage.
  4. **Tier 4 (Portfolio Deployment)**: Evaluated on portfolio drawdown, tail risk, turnover, capacity, and prop-firm constraints.
  *(Certification cannot flow between tiers: a strategy never inherits certification simply because an upstream forecast improved).*
* **Acceptance Gate**:
  * Command: `pytest tests/test_promotion_orchestrator.py`
  * Assertions: Tier independence verified; promotion requires explicit passing of tier-specific gate.

---

## 6. Phase 4: Typed Intake Catalog & Web Workspace

### Objective
Provide a unified, human-native intake interface and interactive web dashboard for daily wargaming, post-market review, and deliberate practice.

---

### Milestone 4.1: Universal Typed Intake Catalog (`information_items`)
* **Target Path**: `scripts/trading_brain/intake/catalog_router.py`
* **Functionality**:
  * Ingests the 9 information types with canonical envelope metadata (`information_id`, `evidence_class`, `time_orientation`, `available_at_utc`, `review_state`).
  * **Consumer As-Of Enforcement**: Intake accepts and tags all valid items (including post-hoc journals and EOD charts). Decision retrieval and forecast reconstruction consumers enforce `available_at_utc <= decision_cutoff_utc` at query time.

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

| Milestone ID | Action Item | Target Delivery | Prerequisite / Dependency |
| :---: | :--- | :--- | :--- |
| **M0.1** | **Database Schema & Immutability Triggers** (`schema.sql`, `test_trading_brain_db.py`) | Phase 0 Start | Implementation Plan Approved |
| **M0.2** | **Plan Snapshot & Lifecycle Ledger** (`plan_adapter.py`, `test_plan_adapter.py`) | Milestone 0.1 | M0.1 |
| **M0.3** | **Shadow Legacy DB Import, Reconciliation & Fence** (`migrate_legacy_dbs.py`) | Milestone 0.1 | M0.1 |
| **M0.4** | **Server-Enforced Forecast Registrar** (`forecast_registrar.py`, `test_forecast_registrar.py`) | Milestone 0.1 | M0.1 |
| **M0.5** | **As-Of Signal Opportunity Logger** (`opportunity_logger.py` + `registry_v0.py`) | Milestone 0.1 | M0.1 |
| **M0.6** | **Hardened NT8 Ingestion Adapter** (`nt8_broker_adapter.py`, `test_nt8_broker_adapter.py`) | Milestone 0.1 | M0.1 |
| **M0.7** | **Measured Tape Actuals Extractor** (`tape_extractor.py`, `test_tape_extractor.py`) | Milestone 0.1 | M0.1 |
| **M0.8** | **Operational Verification Gate** (Scenario suite + 10 live sessions soak) | Phase 0 Done | M0.1–M0.7 |
| **M1.0** | **Phase 1 Re-Approval Review** | Formal Sign-Off | M0.8 Passed |
