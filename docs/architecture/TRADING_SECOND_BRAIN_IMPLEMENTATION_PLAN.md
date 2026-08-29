# 🛠️ Trading Second Brain: Master Implementation Plan

> **Document Version**: 4.0.0 (Execution-Hardened Specification & Preregistered Contract)  
> **Status**: Canonical Phased Engineering Roadmap & Review Document  
> **Architecture Reference**: [`docs/architecture/TRADING_SECOND_BRAIN_MASTER_ARCHITECTURE.md`](file:///c:/Users/vinay/tvDownloadOHLC/docs/architecture/TRADING_SECOND_BRAIN_MASTER_ARCHITECTURE.md) (v4.3.0)  
> **Location**: `docs/architecture/TRADING_SECOND_BRAIN_IMPLEMENTATION_PLAN.md`  
> **Core Operating Principle**: *Construct the verified 18-table schema and immutable plan ledger first. Prove legacy reconciliation in shadow dual-write mode with rollback fences. Guarantee server-enforced cutoff gates, as-of decision time contracts, and under 5 minutes of daily operator review before enabling downstream evaluation or research gates.*

---

## 1. Architectural Strategy & Phasing Roadmap

The implementation is structured into **five sequential, independently testable phases**. **Phase 0 is a self-contained, low-manual-input capture candidate** that must pass an operational scenario gate before Phase 1 commences:

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 5-PHASE ENGINEERING ROADMAP                                      │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘

  PHASE 0: LOW-MANUAL-INPUT CAPTURE SPINE & ACID DATABASE FOUNDATION [CANDIDATE SPINE]
  • M0.1: Canonical SQLite Schema & 15-Trigger Immutability Matrix (`trading_brain.sqlite` - 18 tables)
  • M0.2: Immutable Plan Snapshot, Lifecycle Events & `get_plan_as_of` Resolver (Prisma adapter)
  • M0.3: Shadow Legacy Data Import, Dual-Hash Reconciliation & Dual-Write Rollback Fence
  • M0.4: Server-Enforced Forecast Snapshot Registrar (Database-generated `received_at_utc`)
  • M0.5: As-Of Signal Opportunity Logger (Frozen `STRATEGY_REGISTRY_V0` + decision_time_utc)
  • M0.6: Hardened NT8 Ingestion & Durable State Reconciliation (`broker_ingest_state`, cursor tailer)
  • M0.7: Measured Tape Actuals Extractor (`live_storage_resolver.py` + explicit ingest manifest)
  • M0.8: Operational Verification Gate -> `OPERATIONALLY_ACCEPTED_CAPTURE_V1` (6 scenarios + 10 soak)
  
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
  • M2.2: Cross-Repository C# RiskGuard Plan-Friction Addon (`nt8-riskguard/addons/` milestone)
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

### Milestone 0.1: Canonical SQLite Schema & Complete Table Manifest (18 Tables)
* **Target Paths**:
  * `scripts/trading_brain/db/schema.sql`: Complete DDL for all 18 tables.
  * `scripts/trading_brain/db/init_db.py`: Initializer with WAL mode, busy timeout, and foreign key verification (`PRAGMA foreign_keys = ON`).
  * `scripts/trading_brain/db/connection.py`: Thread-safe context manager enforcing foreign key constraints on every connection.
  * `tests/test_trading_brain_db.py`: Schema and trigger test suite registered in `pytest`.
* **Database Location**: `data/wargaming/db/trading_brain.sqlite`.
* **Canonical 18-Table Schema Manifest**:

| Table Name | Schema Classification | Immutability Protection | Role & Description |
| :--- | :--- | :---: | :--- |
| **`information_items`** | Append-Only Evidence | `UPDATE/DELETE Triggers` | Universal typed intake catalog envelope. |
| **`plan_snapshots`** | Append-Only Evidence | `UPDATE/DELETE Triggers` | Immutable pre-market trading plan declarations. |
| **`plan_lifecycle_events`** | Append-Only Evidence | `UPDATE/DELETE Triggers` | Plan state transitions (`SUBMITTED`, `SUPERSEDED`, `CANCELLED`). |
| **`plan_amendments`** | Append-Only Evidence | `UPDATE/DELETE Triggers` | Append-only plan adjustments with supersession links. |
| **`forecast_snapshots`** | Append-Only Evidence | `UPDATE/DELETE Triggers` | Immutable pre-market quantitative predictions. |
| **`signal_opportunities`** | Append-Only Evidence | `UPDATE/DELETE Triggers` | As-of mechanically eligible setup triggers. |
| **`signal_disposition_events`** | Append-Only Evidence | `UPDATE/DELETE Triggers` | User/system disposition events (`EXECUTED`, `PASSED`, `MISSED`, `OFFLINE`). |
| **`signal_outcomes`** | Append-Only Evidence | `UPDATE/DELETE Triggers` | Versioned theoretical MFE/MAE outcomes evaluated post-hoc. |
| **`session_tape_actuals`** | Append-Only Evidence | `UPDATE/DELETE Triggers` | Measured tape actuals with vendor provenance and quality state. |
| **`execution_events`** | Append-Only Evidence | `UPDATE/DELETE Triggers` | Monotonic broker event stream (orders, fills, partial exits, stop moves). |
| **`intervention_events`** | Append-Only Evidence | `UPDATE/DELETE Triggers` | Disentangled guard lockouts, soft friction warnings, and annotations. |
| **`drill_attempts`** | Append-Only Evidence | `UPDATE/DELETE Triggers` | Blinded deliberate practice attempts and locked user decisions. |
| **`behavioral_declarations`** | Append-Only Evidence | `UPDATE/DELETE Triggers` | Subjective user reflections and habit declarations. |
| **`unmatched_link_events`** | Transition Ledger | `UPDATE/DELETE Triggers` | Append-only review history for ambiguous opportunity links. |
| **`candidate_finding_events`**| Transition Ledger | `UPDATE/DELETE Triggers` | Append-only review history for staged statistical hypotheses. |
| **`strategies`** | Mutable Registry | Direct Schema | Strategy metadata, rules doc links, and risk constraints. |
| **`model_registry`** | Mutable Registry | Direct Schema | Versioned model parameter hashes and champion/challenger state. |
| **`broker_ingest_state`** | Operational State | Direct Schema | Cursor and pagination checkpoint state for broker adapters. |

* **Acceptance Gate**:
  * Command: `pytest tests/test_trading_brain_db.py`
  * Assertions:
    - All 18 tables initialize cleanly with foreign keys enforced.
    - `UPDATE` and `DELETE` on all 15 append-only tables (13 evidence + 2 transition ledgers) raise immediate SQLite exceptions.
    - Partial unique index permits exactly one `LIVE_PRODUCTION` forecast per `(session_date, ticker, effective_cutoff_utc)`.
    - Partial unique index permits exactly one `EX_ANTE_DECLARED` plan snapshot per `(session_date, ticker, preparation_cutoff_utc)`.

---

### Milestone 0.2: Immutable Pre-Market Plan Snapshot, Lifecycle Events & `get_plan_as_of` Resolver
* **Target Path**: `scripts/trading_brain/plans/plan_adapter.py`
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
      effective_at_utc TIMESTAMP NOT NULL,      -- User-declared intended start
      received_at_utc TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, -- Trusted server receipt
      reason_code TEXT NOT NULL,                -- 'MACRO_NEWS', 'REGIME_CHANGE', 'DISCIPLINE_PAUSE'
      amendment_text TEXT NOT NULL,
      amended_bias TEXT,
      amended_risk_bps REAL,
      FOREIGN KEY (plan_snapshot_id) REFERENCES plan_snapshots(plan_snapshot_id),
      FOREIGN KEY (supersedes_amendment_id) REFERENCES plan_amendments(amendment_id)
  );
  ```
* **As-Of Plan Resolver (`get_plan_as_of`)**:
  ```python
  def get_plan_as_of(session_date: str, ticker: str, decision_time_utc: datetime) -> Optional[PlanContext]:
      # Deterministically resolves the authoritative plan as of a historical decision time.
      # Invariants:
      # 1. Considers only plan_snapshots where received_at_utc <= decision_time_utc AND provenance_class = 'EX_ANTE_DECLARED'.
      # 2. Considers only plan_lifecycle_events where recorded_at_utc <= decision_time_utc.
      # 3. Considers only plan_amendments where received_at_utc <= decision_time_utc AND effective_at_utc <= decision_time_utc.
      # 4. Post-hoc reconstructions can NEVER supersede an ex-ante plan.
      pass
  ```
* **Acceptance Gate**:
  * Command: `pytest tests/test_plan_adapter.py`
  * Assertions:
    - Plans received after cutoff stamped `POST_HOC_RECONSTRUCTION`.
    - `get_plan_as_of` at `08:44 ET` returns original plan even if cancelled or amended at `16:00 ET`.
    - Post-hoc reconstruction does not supersede ex-ante plan in `get_plan_as_of`.

---

### Milestone 0.3: Shadow Legacy Data Import, Dual-Hash Reconciliation & Dual-Write Rollback Fence
* **Target Paths**:
  * `scripts/trading_brain/migrations/migrate_legacy_dbs.py`
  * `scripts/trading_brain/db/wargame_db_bridge.py`
* **Sequencing Contract & Rollback Specification**:
  1. **Pre-Cutover Backup**: Creates online backup `data/wargaming/db/backups/pre_cutover_legacy_state.tar.gz`.
  2. **Cursor Fence**: Records max timestamps and row counts from legacy SQLite files (`system_wargames.sqlite`, `market_actuals.sqlite`, `mickey_ground_truth.sqlite`).
  3. **Shadow Staging Import**: Transforms records into canonical schema with dual-hash lineage:
     - `legacy_source_hash`: SHA-256 of exact raw legacy row JSON (keys sorted).
     - `canonical_payload_hash`: SHA-256 of transformed canonical normalized JSON (keys sorted, ISO-8601 UTC strings).
     - Field-level numeric reconciliation: Floating-point tolerance $|a - b| \le 1\times 10^{-6}$ for probabilities; exact cents for price fields.
  4. **Dual-Write Shadow Mode (Phase 0.3b)**: `wargame_db_bridge.py` writes canonically to `trading_brain.sqlite` AND synchronously copies rows to legacy DBs in shadow mode during the soak period.
  5. **Rollback Command**: `python -m scripts.trading_brain.migrations.migrate_legacy_dbs --rollback` verifies cursor fence and restores primary write routing to legacy DBs in <10 seconds without lost writes.
  6. **Legacy Retention**: Legacy files remain readable in place (no filesystem write locks that could disrupt background readers).
* **Acceptance Gate**:
  * Command: `python -m scripts.trading_brain.migrations.migrate_legacy_dbs --verify`
  * Assertions: 100% record match across historical dates; dual-hash checks pass; rollback command tested with post-cutover shadow writes verified.

---

### Milestone 0.4: Server-Enforced Pre-Market Forecast Snapshot Registrar
* **Target Path**: `scripts/trading_brain/forecast/forecast_registrar.py`
* **Sealed Input & Temporal Gate**:
  * The registrar enforces the complete 4-point temporal contract:
    1. $\text{input\_manifest\_sealed\_at\_utc} \le \text{effective\_cutoff\_utc}$
    2. $\text{every input.available\_at\_utc} \le \text{effective\_cutoff\_utc}$
    3. $\text{forecast\_started\_at\_utc} \le \text{effective\_cutoff\_utc}$
    4. $\text{received\_at\_utc} \le \text{effective\_cutoff\_utc} + \text{model\_input\_contract.commit\_grace\_period}$
  * **Fail-Closed Rule**: If any of the 4 conditions fail, any submission tagged `LIVE_PRODUCTION` is **REJECTED** with `ForecastCutoffExpiredError` or forced to `REPLAY_AUDIT`. Post-hoc live backfilling is physically impossible.
  * **Database-Generated Timestamp**: `received_at_utc` is generated strictly by SQLite database clock (`CURRENT_TIMESTAMP`).
* **Acceptance Gate**:
  * Command: `pytest tests/test_forecast_registrar.py`
  * Assertions: Registration before deadline succeeds as `LIVE_PRODUCTION`; late job initiation or late input sealing fails closed; replay audits write `REPLAY_AUDIT` with `original_prediction_id`.

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
  * For 1m bars where both stop and target are touched, writes `AMBIGUOUS_INTRABAR_ORDER` rather than guessing; backtest evaluates conservative stop-loss assumption.
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

### Milestone 0.6: Hardened NT8 Broker Ingestion & Durable State Reconciliation
* **Target Path**: `scripts/trading_brain/ingest/nt8_broker_adapter.py`
* **Authoritative Endpoints & Durable Ingestion**:
  * Orders & Fills: `nt_orders` and `nt_fill_events` REST polling with persisted cursor checkpoints in `broker_ingest_state`.
  * Interventions: Durable `interventions.jsonl` log file tailer + SSE for live event notification. On SSE disconnect, repairs gaps by polling `interventions.jsonl` from last persisted cursor.
  * Position Snapshot Reconciliation: Reconciles live account position against reconstructed execution state at session boundary.
  * **Unmatched Link Isolation**: Execution-to-opportunity matching uses deterministic criteria. If an execution cannot be matched unambiguously to a single `opportunity_id`, it is flagged `AMBIGUOUS_MATCH` and written to `unmatched_link_events` for review.
* **Disentangled `intervention_events` Schema**:
  ```sql
  CREATE TABLE intervention_events (
      intervention_id TEXT PRIMARY KEY,
      session_date DATE NOT NULL,
      ticker TEXT NOT NULL,
      account_id TEXT NOT NULL,
      trade_id TEXT,
      client_order_id TEXT,
      broker_order_id TEXT,
      plan_snapshot_id TEXT,
      strategy_id TEXT,
      strategy_version TEXT,
      guard_config_hash TEXT,
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
      idempotency_key TEXT NOT NULL UNIQUE,
      event_timestamp_utc TIMESTAMP NOT NULL,
      created_at_utc TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  );
  ```
* **Acceptance Gate**:
  * Command: `pytest tests/test_nt8_broker_adapter.py`
  * Fixtures: Verified against synthetic streams + captured provider traces (`Sim101`, `Provider31`) covering reconnects, log rotation, out-of-order fills, null-order executions, stop modifications, partial fills, and ambiguous opportunity scenarios.

---

### Milestone 0.7: Measured Tape Actuals Extractor
* **Target Path**: `scripts/trading_brain/tape/tape_extractor.py`
* **Canonical Sources & Lineage**:
  * Live Session Storage: Resolved via `scripts/utils/live_storage_resolver.py` (`data/live/live_storage_-NQ.parquet`, `data/live/live_storage_-ES.parquet`).
  * Settlement & Close: Verified daily bar feed with settlement timestamp.
  * Historical Backfills: Deep parquet archive via `load_fused_data(require_historical=True)`.
* **Tape Row Schema & Lineage**:
  Captures `ingest_id`, `source_system`, `expected_bar_count`, `actual_bar_count`, `content_hash`, `quality_state` (`CLEAN`, `SUSPECT_TICKS`, `INCOMPLETE_BARS`), and `supersedes_actual_id`.
  Evaluates `LABEL_DAY_TYPE_V1` and `LABEL_EOD_CLASSIFICATION_V1`.
* **Acceptance Gate**:
  * Command: `pytest tests/test_tape_extractor.py`
  * Fixtures: Verified against 5 benchmark tape sessions (normal, early close, DST transition, contract roll, and missing bar session).

---

### Milestone 0.8: Operational Verification Gate -> `OPERATIONALLY_ACCEPTED_CAPTURE_V1`
* **Target Path**: `scripts/trading_brain/testing/operational_soak_gate.py`
* **Operational Acceptance Suite**:
  * Phase 0 achieves `OPERATIONALLY_ACCEPTED_CAPTURE_V1` certification only when it passes:
    1. **Automated Scenario Test Suite**:
       - *Scenario A*: No-trade session (zero signals, zero fills -> cleanly recorded).
       - *Scenario B*: Early close session (holiday schedule correctly handled).
       - *Scenario C*: DST transition session (UTC vs. ET window correctness).
       - *Scenario D*: Contract roll date (continuous vs. actual contract mapping).
       - *Scenario E*: Feed outage & broker reconnect (gap recovery and deduplication).
       - *Scenario F*: Database crash & recovery (WAL rollback and PRAGMA integrity pass).
    2. **Quantified Live Soak Metrics**:
       - 10 consecutive live trading sessions captured.
       - 0 unexplained data loss.
       - 0 duplicate canonical events.
       - 100% gap reconciliation or explicit quarantine in `unmatched_link_events`.
       - Operator review time < 5 minutes on >= 90% of standard sessions.

---

## 3. Phase 1: Daily Process Delta & Mechanical Post-Mortem

### Objective
Create a deterministic, event-first 4-way reconciliation engine that produces a single concise, actionable EOD report in under 5 minutes of operator reading time without Goodhart-prone composite grading.

---

### Milestone 1.1: 4-Way Mechanical Reconciler
* **Target Path**: `scripts/trading_brain/evaluation/daily_process_delta.py`
* **The 4-Way Reconciliation Quadrant**:
  ```
  1. PRE-MARKET PLAN (get_plan_as_of + forecast_snapshots @ 08:45 ET)
                           ↕
  2. SIGNAL OPPORTUNITIES (All eligible mechanical triggers via registry_v0)
                           ↕
  3. EXECUTIONS & INTERVENTIONS (Actual fills, stops, RiskGuard telemetry)
                           ↕
  4. MEASURED TAPE OUTCOMES (16:15 ET HOD/LOD, Day Type, MFE/MAE)
  ```
* **Metrics Computed (Event-First, Policy-Driven)**:
  1. **Session Forecast Loss**: Computes proper-score realized loss for the single session (labeled "session forecast loss", reserving calibration/skill claims for accumulated samples).
  2. **Opportunity Realization Table**: Explicit counts of eligible signals: N_total, N_executed, N_passed, N_missed.
  3. **Execution Capture Delta**: Compares actual execution against the strategy's registered execution policy (e.g. registered scale-out targets from `strategies.execution_policy_json`).
  4. **Intervention Telemetry**: Factual counts of hard locks, soft friction overrides, and plan deviations.
* **Acceptance Gate**:
  * Command: `pytest tests/test_daily_process_delta.py`
  * Assertions: Correctly reconciles all 4 quadrants across synthetic and live sessions without crashing on missing quadrant inputs.

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
* **Acceptance Gate**:
  * Command: `pytest tests/test_agent_memory_bridge.py`
  * Assertions: Queries return verified trading statistics from `trading_brain.sqlite`; zero writes or schema mutations to `.agent/memory.db`.

---

## 4. Phase 2: Minute-Scale Feedback & Blinded Deliberate Practice

### Objective
Bridge the gap between pre-market analysis and live execution through real-time friction and high-repetition blinded simulation drills.

---

### Milestone 2.1: Python Post-Submission Deviation Annotator
* **Target Path**: `scripts/trading_brain/guard/deviation_annotator.py`
* **Functionality**:
  * Asynchronously consumes the execution stream via MCP post-submission.
  * Compares executed orders against the active plan in `get_plan_as_of`.
  * Flags observable deviations (e.g. unapproved strategy, trading outside permitted window), logs an event in `intervention_events` with `authority_class = 'OBSERVED_DEVIATION_ANNOTATION'`, and emits visual/audio coaching alerts.
* **Acceptance Gate**:
  * Command: `pytest tests/test_deviation_annotator.py`
  * Assertions: Accurately flags deviations; zero false positives on plan-compliant orders.

---

### Milestone 2.2: Cross-Repository C# RiskGuard Plan-Friction Addon
* **Target Path**: `C:\Users\vinay\nt8-riskguard\addons\PlanFrictionRule.cs` (in `nt8-riskguard` repo).
* **Governance & Compilation Contract**:
  * Managed as a dedicated cross-repository milestone with its own isolated test suite.
  * Test command in `nt8-riskguard`:
    ```powershell
    dotnet build tests/RiskGuardTests.csproj
    dotnet run --project tests/RiskGuardTests.csproj --no-build
    python tools/check_no_stray_copies.py
    ```
  * Deployed and compiled via `nt_compile`.
* **Safety Contract**:
  * Synchronous pre-order evaluation in NinjaTrader 8.
  * Reads daily plan constraints pushed from Python at 08:45 ET.
  * **Fail-Safe Invariant**: If Python bridge is offline or plan context is missing, plan friction **defaults to disabled/shadow** and **NEVER blocks trades**.
  * **Exit Preservation**: Plan friction **NEVER intercepts or delays risk-reducing or protective exit orders**.
* **Acceptance Gate**:
  * Command: `dotnet test tests/RiskGuardTests.csproj` + `nt_compile`
  * Assertions: Proves risk-reducing exit orders are never delayed; missing plan context defaults to shadow mode.

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
  * Consumes a preregistered evaluation contract: primary proper score, prospective power (1 - beta >= 0.80), task-specific MDE, and economic threshold after costs.
  * Evaluates 1-time sealed shadow data with dedicated custody manifest and access logging.
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
* **Acceptance Gate**:
  * Command: `pytest tests/test_catalog_router.py`
  * Assertions: Correctly tags 9 information types; consumer queries filter post-hoc items from ex-ante windows.

---

### Milestone 4.2: Web Dashboard UI Integration
* **Target Path**: `web/` (Next.js, Tailwind CSS, Shadcn/UI, Lightweight Charts)
* **Features**:
  1. **Pre-Market Wargame & Plan Builder**: Scenario cards and plan snapshot authoring.
  2. **Daily Process Delta Scorecard**: Visual 4-way post-mortem comparison.
  3. **Deliberate Practice Replay Station**: Browser-based blinded chart drill simulator.
  4. **Model Governance & Promotion Dashboard**: Calibration curves, walk-forward folds, and shadow evaluation state.
* **Acceptance Gate**:
  * Command: `npm test` in `web/` + visual component smoke tests.

---

## 7. Immediate Next Steps & Review Checkpoints

| Milestone ID | Action Item | Target Delivery | Prerequisite / Dependency |
| :---: | :--- | :--- | :--- |
| **M0.1** | **Canonical SQLite Schema & 15-Trigger Immutability Matrix** (`schema.sql`, `test_trading_brain_db.py`) | Phase 0 Start | Implementation Plan Approved |
| **M0.2** | **Plan Snapshot, Lifecycle Ledger & `get_plan_as_of`** (`plan_adapter.py`, `test_plan_adapter.py`) | Milestone 0.1 | M0.1 |
| **M0.3** | **Shadow Legacy Import, Dual-Hash Check & Dual-Write Fence** (`migrate_legacy_dbs.py`) | Milestone 0.1 | M0.1 |
| **M0.4** | **Server-Enforced Forecast Snapshot Registrar** (`forecast_registrar.py`, `test_forecast_registrar.py`) | Milestone 0.1 | M0.1 |
| **M0.5** | **As-Of Signal Opportunity Logger** (`opportunity_logger.py` + `registry_v0.py`) | Milestone 0.1 | M0.1, Frozen Strategy V0 |
| **M0.6** | **Hardened NT8 Broker Ingestion & Cursor Tailer** (`nt8_broker_adapter.py`, `test_nt8_broker_adapter.py`) | Milestone 0.1 | M0.1, Durable Ingest Surface |
| **M0.7** | **Measured Tape Actuals Extractor** (`tape_extractor.py`, `test_tape_extractor.py`) | Milestone 0.1 | M0.1, `live_storage_resolver.py` |
| **M0.8** | **Operational Verification Gate** (`OPERATIONALLY_ACCEPTED_CAPTURE_V1` - Scenario suite + soak) | Phase 0 Done | M0.1–M0.7, Tested Rollback |
| **M1.0** | **Phase 1 Re-Approval Review** | Formal Sign-Off | M0.8 Passed |
