# 🛠️ Trading Second Brain: Master Implementation Plan

> **Document Version**: 5.2.0 (Approved Implementation Contract & Formally Hardened Specification)  
> **Status**: Canonical Phased Engineering Roadmap & Review Document  
> **Architecture Reference**: [`docs/architecture/TRADING_SECOND_BRAIN_MASTER_ARCHITECTURE.md`](file:///c:/Users/vinay/tvDownloadOHLC/docs/architecture/TRADING_SECOND_BRAIN_MASTER_ARCHITECTURE.md) (v4.3.0)  
> **Location**: `docs/architecture/TRADING_SECOND_BRAIN_IMPLEMENTATION_PLAN.md`  
> **Core Operating Principle**: *Construct the verified 21-table schema and immutable plan ledger first. Implement and verify canonical producers in shadow mode. Prove legacy reconciliation with transactional outbox replay and rollback fences before live cutover. Guarantee server-enforced cutoff gates, as-of decision time contracts, and mechanical post-mortem derivation before enabling downstream evaluation or research gates.*

---

## 1. Architectural Strategy & Phasing Roadmap

The implementation is structured into **five sequential, independently testable phases**. **Phase 0 is a self-contained, low-manual-input capture candidate** that must pass an operational scenario gate before Phase 1 commences:

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 5-PHASE ENGINEERING ROADMAP                                      │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘

  PHASE 0: LOW-MANUAL-INPUT CAPTURE SPINE & ACID DATABASE FOUNDATION [CANDIDATE SPINE]
  • M0.1: Canonical SQLite Schema & 36-Trigger Immutability Matrix (`trading_brain.sqlite` - 21 tables)
  • M0.2: Immutable Plan Snapshots, Revisions & Deterministic `get_plan_as_of` Resolver (Prisma adapter)
  • M0.3a: Shadow Legacy Data Import & Dual-Hash Checksum Verification
  • M0.4: Two-Phase Sealed Forecast Registrar (Asymmetric Cutoff Gate + Calendar Uniqueness)
  • M0.5: As-Of Signal Opportunity Logger (Frozen `STRATEGY_REGISTRY_V0` + Mechanical Dispositions)
  • M0.6: Hardened NT8 Ingestion (Lossless fills via `nt_fill_events` + durable interventions)
  • M0.7: Measured Tape Actuals Extractor (`live_storage_resolver.py` + explicit ingest manifest)
  • M0.3b: Transactional Outbox Projector, Verified Rollback Fence & Canonical Writer Cutover
  • M0.8: Operational Verification Gate -> `OPERATIONALLY_ACCEPTED_CAPTURE_V1` (6 scenarios + soak)
  
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
  • M2.2: Cross-Repository C# RiskGuard & MCP Plan Push Addon (`nt8-riskguard` + `nt8-mcp-bridge`)
  • M2.3: Blinded Deliberate-Practice Replay Engine (Hidden dates/outcomes, locked commitments, split custody)
  • M2.4: Recurring-Error Targeted Drill Generator (User-controlled practice curriculum from delta logs)
  
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

### Milestone 0.1: Canonical SQLite Schema & Complete Table Manifest (21 Tables)
* **Target Paths**:
  * `scripts/trading_brain/db/schema.sql`: Complete DDL for all 21 tables.
  * `scripts/trading_brain/db/init_db.py`: Initializer with WAL mode, busy timeout, and foreign key verification (`PRAGMA foreign_keys = ON`).
  * `scripts/trading_brain/db/connection.py`: Thread-safe context manager enforcing foreign key constraints on every connection.
  * `tests/test_trading_brain_db.py`: Schema and trigger test suite registered in `pytest`.
* **Database Location**: `data/wargaming/db/trading_brain.sqlite`.
* **Canonical 21-Table Schema Manifest**:

| Table Name | Schema Classification | Immutability Protection | Role & Description |
| :--- | :--- | :---: | :--- |
| **`information_items`** | Append-Only Evidence | 2 Triggers (UP/DEL) | Universal typed intake catalog envelope. |
| **`plan_snapshots`** | Append-Only Evidence | 2 Triggers (UP/DEL) | Immutable pre-market trading plan declarations. |
| **`plan_lifecycle_events`** | Append-Only Evidence | 2 Triggers (UP/DEL) | Plan state transitions (`SUBMITTED`, `SUPERSEDED`, `CANCELLED`). |
| **`plan_amendments`** | Append-Only Evidence | 2 Triggers (UP/DEL) | Append-only plan adjustments with supersession links. |
| **`forecast_snapshots`** | Append-Only Evidence | 2 Triggers (UP/DEL) | Immutable pre-market quantitative predictions. |
| **`signal_opportunities`** | Append-Only Evidence | 2 Triggers (UP/DEL) | As-of mechanically eligible setup triggers. |
| **`signal_disposition_events`** | Append-Only Evidence | 2 Triggers (UP/DEL) | Mechanically derived disposition events (`EXECUTED`, `PASSED`, `MISSED`, `OFFLINE`). |
| **`signal_outcomes`** | Append-Only Evidence | 2 Triggers (UP/DEL) | Versioned theoretical MFE/MAE outcomes evaluated post-hoc. |
| **`session_tape_actuals`** | Append-Only Evidence | 2 Triggers (UP/DEL) | Measured tape actuals with vendor provenance and quality state. |
| **`execution_events`** | Append-Only Evidence | 2 Triggers (UP/DEL) | Monotonic broker event stream (fills, partial exits, execution prices). |
| **`intervention_events`** | Append-Only Evidence | 2 Triggers (UP/DEL) | Disentangled guard lockouts, soft friction warnings, and annotations. |
| **`drill_attempts`** | Append-Only Evidence | 2 Triggers (UP/DEL) | Blinded deliberate practice attempts and locked user decisions. |
| **`behavioral_declarations`** | Append-Only Evidence | 2 Triggers (UP/DEL) | Subjective user reflections and habit declarations. |
| **`unmatched_link_events`** | Transition Ledger | 2 Triggers (UP/DEL) | Append-only review history for ambiguous opportunity links. |
| **`candidate_finding_events`**| Transition Ledger | 2 Triggers (UP/DEL) | Append-only review history for staged statistical hypotheses. |
| **`strategy_versions`** | Immutable Version Registry | 2 Triggers (UP/DEL) | Frozen strategy rules, parameter hashes, and execution policies. |
| **`model_versions`** | Immutable Version Registry | 2 Triggers (UP/DEL) | Frozen model weights, feature manifests, and calibration states. |
| **`forecast_run_inputs`** | Immutable Run Evidence | 2 Triggers (UP/DEL) | Immutable snapshot of sealed input references and checksums per run. |
| **`forecast_runs`** | Operational Staging | State Machine | Pre-commit forecast execution state machine (`CREATED` -> `INPUTS_SEALED` -> `COMMITTED`). |
| **`legacy_projection_outbox`** | Operational Staging | State Machine | Transactional outbox for asynchronous projection to legacy DBs. |
| **`broker_ingest_state`** | Operational State | Direct Schema | Cursor and pagination checkpoint state keyed by `(endpoint, account_id)`. |

* **Immutability Protection Count**: Exactly **18 tables** are protected by paired `BEFORE UPDATE` and `BEFORE DELETE` triggers, totaling **36 triggers**.
* **Review Queue Current-State Projections**:
  * `v_unmatched_links_open`: Evaluates current unresolved state from `unmatched_link_events`.
  * `v_candidate_findings_staged`: Evaluates active hypothesis pipeline from `candidate_finding_events`.
* **Trust Boundary & Clock Monotonicity**:
  * All evidence insertions route through Python service classes (`PlanAdapter`, `ForecastRegistrar`) omitting receipt timestamp columns to allow SQLite `CURRENT_TIMESTAMP` to bind server time.
  * Monotonic Clock Guard: Write services assert `received_at_utc >= max_observed_timestamp` to prevent time-travel on clock skew.
* **Ongoing Automated Backup Policy**:
  * Post-market automated SQLite Online Backup (`VACUUM INTO 'data/wargaming/db/backups/trading_brain_YYYYMMDD.sqlite'`) with `PRAGMA integrity_check`.
* **Acceptance Gate**:
  * Command: `pytest tests/test_trading_brain_db.py`
  * Assertions:
    - All 21 tables initialize cleanly with foreign keys enforced.
    - All 36 triggers exist and raise immediate SQLite exceptions on `UPDATE` or `DELETE`.
    - Partial unique index strictly enforces at most one `LIVE_PRODUCTION` forecast per `(session_date, ticker)`:
      ```sql
      CREATE UNIQUE INDEX uq_live_forecast_per_session 
      ON forecast_snapshots (session_date, ticker) 
      WHERE forecast_mode = 'LIVE_PRODUCTION';
      ```

---

### Milestone 0.2: Immutable Pre-Market Plan Snapshots & Deterministic `get_plan_as_of` Resolver
* **Target Path**: `scripts/trading_brain/plans/plan_adapter.py`
* **Schema**:
  ```sql
  CREATE TABLE plan_snapshots (
      plan_snapshot_id TEXT PRIMARY KEY,        -- UUID v4
      plan_family_id TEXT NOT NULL,             -- UUID grouping all revisions for (session_date, ticker)
      revision_seq INTEGER NOT NULL,            -- Monotonic 1-indexed revision sequence
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
      
      -- Provenance Timestamps
      received_at_utc TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
      provenance_class TEXT NOT NULL,           -- 'EX_ANTE_DECLARED' or 'POST_HOC_RECONSTRUCTION'
      created_at_utc TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (supersedes_plan_snapshot_id) REFERENCES plan_snapshots(plan_snapshot_id),
      CONSTRAINT ck_no_self_supersession CHECK (supersedes_plan_snapshot_id <> plan_snapshot_id),
      UNIQUE(plan_family_id, revision_seq)
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
      FOREIGN KEY (supersedes_amendment_id) REFERENCES plan_amendments(amendment_id),
      UNIQUE(plan_snapshot_id, amendment_seq)
  );
  ```
* **Deterministic As-Of Authority Algorithm (`get_plan_as_of`)**:
  ```python
  def get_plan_as_of(session_date: str, ticker: str, decision_time_utc: datetime) -> Optional[PlanContext]:
      """Deterministically resolves the authoritative plan as of a historical decision time.
      
      Algorithm:
      1. Query plan_snapshots where session_date = :date AND ticker = :ticker 
         AND received_at_utc <= :decision_time_utc AND provenance_class = 'EX_ANTE_DECLARED'.
      2. Filter out snapshots where a 'CANCELLED' or 'SUPERSEDED' event exists in plan_lifecycle_events 
         with recorded_at_utc <= :decision_time_utc.
      3. Filter out snapshots whose ID is referenced as supersedes_plan_snapshot_id by any newer 
         valid snapshot received by :decision_time_utc.
      4. Deterministic authority resolution:
         ORDER BY received_at_utc DESC, revision_seq DESC LIMIT 1.
      5. Attach all plan_amendments for this snapshot where received_at_utc <= :decision_time_utc 
         AND effective_at_utc <= :decision_time_utc ORDER BY amendment_seq ASC.
      6. Invariant: Post-hoc reconstructions can NEVER supersede an ex-ante plan.
      """
  ```
* **Acceptance Gate**:
  * Command: `pytest tests/test_plan_adapter.py`
  * Assertions:
    - Allows multiple ex-ante revisions before cutoff (e.g. 08:20 plan revised at 08:35).
    - `get_plan_as_of` at `08:30 ET` returns the 08:20 plan; at `08:40 ET` returns the 08:35 plan.
    - Post-hoc reconstruction received at 16:30 is tagged `POST_HOC_RECONSTRUCTION` and does not supersede the ex-ante plan.

---

### Milestone 0.3a: Shadow Legacy Data Import & Dual-Hash Checksum Verification
* **Target Path**: `scripts/trading_brain/migrations/import_legacy_shadow.py`
* **Sequencing Contract**:
  1. **SQLite Online Backup**: Creates verified backup of legacy databases via SQLite Online Backup API (`sqlite3_backup`) with `PRAGMA integrity_check`.
  2. **Shadow Staging Import**: Reads records from `system_wargames.sqlite`, `market_actuals.sqlite`, and `mickey_ground_truth.sqlite` into a staging schema in `trading_brain.sqlite`.
  3. **Three-Layer Validation**:
     - `legacy_source_hash`: SHA-256 of exact raw legacy row JSON (keys sorted).
     - `canonical_payload_hash`: SHA-256 of transformed canonical normalized JSON (keys sorted, ISO-8601 UTC strings).
     - Field-level numeric reconciliation: Floating-point tolerance $|a - b| \le 1\times 10^{-6}$ for probabilities; exact cents for price fields.
* **Acceptance Gate**:
  * Command: `python -m scripts.trading_brain.migrations.import_legacy_shadow --verify`
  * Assertions: 100% record match across historical dates; dual-hash checks pass.

---

### Milestone 0.4: Two-Phase Sealed Forecast Registrar (Asymmetric Cutoff Gate)
* **Target Paths**:
  * `scripts/utils/market_calendar.py`: Canonical Market Calendar computing DST-correct `08:45:00 ET` in UTC for any session date.
  * `scripts/trading_brain/forecast/forecast_registrar.py`: Forecast registrar.
* **Schema**:
  ```sql
  CREATE TABLE forecast_runs (
      forecast_run_id TEXT PRIMARY KEY,         -- UUID v4
      session_date DATE NOT NULL,
      ticker TEXT NOT NULL,
      model_version_id TEXT NOT NULL,
      effective_cutoff_utc TIMESTAMP NOT NULL,
      commit_grace_period_sec INTEGER NOT NULL, -- Pinned from model contract at run creation
      status TEXT NOT NULL,                     -- 'CREATED', 'INPUTS_SEALED', 'COMMITTED', 'FAILED', 'EXPIRED'
      started_at_utc TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
      inputs_sealed_at_utc TIMESTAMP,
      committed_at_utc TIMESTAMP,
      created_at_utc TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE forecast_run_inputs (
      input_id TEXT PRIMARY KEY,
      forecast_run_id TEXT NOT NULL,
      provider_name TEXT NOT NULL,
      data_type TEXT NOT NULL,
      max_timestamp_utc TIMESTAMP NOT NULL,
      content_hash TEXT NOT NULL,
      FOREIGN KEY (forecast_run_id) REFERENCES forecast_runs(forecast_run_id)
  );
  ```
* **Asymmetric Cutoff Gate Protocol**:
  1. **Phase 1: Pre-Cutoff Run Initiation (`create_forecast_run`)**:
     - Validates `effective_cutoff_utc` against `scripts/utils/market_calendar.py`.
     - Seals input bar manifests into `forecast_run_inputs`, records `inputs_sealed_at_utc`, and transitions status to `INPUTS_SEALED`.
     - Enforces: $\text{inputs\_sealed\_at\_utc} \le \text{cutoff}$ and $\text{every input max\_timestamp\_utc} \le \text{cutoff}$.
  2. **Phase 2: Commit Completion (`commit_forecast_run`)**:
     - Evaluates database clock `received_at_utc` against cutoff and grace boundaries:
       - **Strictly Pre-Cutoff** ($\text{received\_at\_utc} \le \text{cutoff}$): Written as **`LIVE_PRODUCTION`** (genuine ex-ante live forecast).
       - **Within Grace Window** ($\text{cutoff} < \text{received\_at\_utc} \le \text{cutoff} + \text{commit\_grace\_period\_sec}$): Demoted and written as **`FORECAST_LATE_RECEIVED`** (preserved for audit/debug, but stripped of live execution authority).
       - **Past Grace Window** ($\text{received\_at\_utc} > \text{cutoff} + \text{commit\_grace\_period\_sec}$): Deterministically rejected with `ForecastCutoffExpiredError` (or marked `REPLAY_AUDIT` if invoked in replay mode).
* **Acceptance Gate**:
  * Command: `pytest tests/test_forecast_registrar.py` + `pytest tests/test_market_calendar.py`
  * Assertions:
    - Pre-cutoff commit produces `LIVE_PRODUCTION`.
    - Within-grace commit produces `FORECAST_LATE_RECEIVED` (never `LIVE_PRODUCTION`).
    - Past-grace commit raises `ForecastCutoffExpiredError`.
    - Unique index `uq_live_forecast_per_session` rejects duplicate `LIVE_PRODUCTION` attempts for the same session.

---

### Milestone 0.5: As-Of Signal Opportunity Logger & Mechanical Disposition Derivation
* **Target Paths**:
  * `scripts/trading_brain/signals/opportunity_logger.py`
  * `scripts/trading_brain/strategies/artifacts/` (Machine-readable JSON strategy definitions)
* **Required Strategy JSON Artifact Schema**:
  ```json
  {
    "strategy_version_id": "STRAT_ALN_LPEU_V0_1",
    "strategy_family": "ALN_LPEU",
    "content_hash": "sha256:...",
    "ticker_scope": ["NQ1", "-NQ"],
    "required_providers": ["ALNSessionsProvider_v1"],
    "session_window_et": { "start": "09:30:00", "end": "15:45:00" },
    "trigger_expression": "london_expansion_up && pullback_to_session_poc",
    "decision_timing": "BAR_CLOSE",
    "entry_convention": "MARKET_AT_BAR_CLOSE",
    "signal_expiry_seconds": 900,
    "invalidation_expression": "close < asia_low",
    "max_signals_per_session": 1,
    "stop_loss_bps": 12.0,
    "target_1_bps": 10.0,
    "target_2_bps": 30.0,
    "outcome_horizon_et": "16:00:00",
    "intrabar_ambiguity_policy": "RECORD_AMBIGUOUS_EVALUATE_DUAL_BOUNDS",
    "cost_model_bps": 2.0,
    "missing_data_policy": "FAIL_CLOSED",
    "status": "EXPERIMENTAL_CAPTURE_ONLY"
  }
  ```
* **Mechanical Disposition Derivation**:
  * `signal_disposition_events` are **mechanically computed** by matching `execution_events` to `signal_opportunities` within declared tolerance windows:
    - `EXECUTED`: Execution order fills within setup validity window and matches price boundary ($\pm 2$ bps).
    - `PASSED`: Setup triggered while trader was active, but no execution event occurred before signal expiry.
    - `MISSED`: Setup triggered while platform was offline or RiskGuard was locked.
    - `OFFLINE`: Trigger occurred during unmonitored session.
  * Unmatched/ambiguous executions route directly to `unmatched_link_events`.
  * Human overrides permitted only as linked correction events in `signal_disposition_events` with `corrects_disposition_id`.
* **Acceptance Gate**:
  * Command: `pytest tests/test_opportunity_logger.py`
  * Golden Fixtures: Tested against 5 golden session datasets with verified expected-event ledgers.

---

### Milestone 0.6: Hardened NT8 Broker Ingestion & Durable State Reconciliation
* **Target Path**: `scripts/trading_brain/ingest/nt8_broker_adapter.py`
* **Durable Ingestion Channels**:
  * **Fills & Executions (Lossless within measured retention)**: Polled from `nt_fill_events` REST endpoint with persisted cursor checkpoints in `broker_ingest_state` keyed by `(endpoint, account_id)`. Ingests into `execution_events`. Reconciled against extracted broker trade history at session end.
  * **Interventions & Lockouts (Lossless)**: Tailer for durable `interventions.jsonl` log file + SSE live notification with gap recovery.
  * **Order & Position State (Periodic Snapshots)**: `nt_orders` and `nt_positions` polled at session boundaries to reconcile live account positions against reconstructed fills.
* **Expanded `intervention_events` Audit Schema**:
  ```sql
  CREATE TABLE intervention_events (
      intervention_id TEXT PRIMARY KEY,
      session_date DATE NOT NULL,
      ticker TEXT NOT NULL,
      account_id TEXT NOT NULL,
      trade_id TEXT,
      client_order_id TEXT,
      broker_order_id TEXT,
      source_event_id TEXT,
      corrects_intervention_id TEXT,
      plan_snapshot_id TEXT,
      plan_amendment_id TEXT,
      strategy_version_id TEXT,
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
      override_actor TEXT,
      override_acknowledged_at_utc TIMESTAMP,
      idempotency_key TEXT NOT NULL,
      event_timestamp_utc TIMESTAMP NOT NULL,
      created_at_utc TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (plan_snapshot_id) REFERENCES plan_snapshots(plan_snapshot_id),
      FOREIGN KEY (plan_amendment_id) REFERENCES plan_amendments(amendment_id),
      UNIQUE(producer, account_id, idempotency_key)
  );
  ```
* **Acceptance Gate**:
  * Command: `pytest tests/test_nt8_broker_adapter.py`
  * Fixtures: Verified against synthetic streams + captured provider traces (`Sim101`, `Provider31`).

---

### Milestone 0.7: Measured Tape Actuals Extractor
* **Target Paths**:
  * `scripts/utils/live_storage_resolver.py`: Explicit deliverable resolving live storage paths (`NQ1` -> `data/live/live_storage_-NQ.parquet`, `ES1` -> `data/live/live_storage_-ES.parquet`, `YM1`, `RTY1`, `GC1`, `CL1`).
  * `scripts/trading_brain/tape/tape_extractor.py`: Tape metrics extractor.
* **Explicit Close Authorities**:
  * `rth_close`: Last traded 1m bar close at 16:00:00 ET from live storage parquet.
  * `daily_bar_close`: Daily bar close from fused historical loader (`scripts/utils/fused_data_loader.py`).
  * `exchange_settlement`: Explicitly marked `NOT_AVAILABLE_IN_P0` (no official CME settlement feed currently exists in repository).
* **Tape Row Schema**: Captures `ingest_id`, `source_system`, `expected_bar_count`, `actual_bar_count`, `content_hash`, `quality_state` (`CLEAN`, `SUSPECT_TICKS`, `INCOMPLETE_BARS`), `LABEL_DAY_TYPE_V1`, and `LABEL_EOD_CLASSIFICATION_V1`.
* **Acceptance Gate**:
  * Command: `pytest tests/test_tape_extractor.py` + `pytest tests/test_live_storage_resolver.py`

---

### Milestone 0.3b: Transactional Outbox Projector, Verified Rollback Fence & Canonical Writer Cutover
* **Target Path**: `scripts/trading_brain/migrations/outbox_projector.py`
* **Sequencing Invariant**: Executed **only after** Milestones M0.4, M0.5, M0.6, and M0.7 are complete and verified in shadow mode.
* **Outbox Schema**:
  ```sql
  CREATE TABLE legacy_projection_outbox (
      outbox_id TEXT PRIMARY KEY,
      destination_db TEXT NOT NULL,             -- 'system_wargames', 'market_actuals', 'mickey_ground_truth'
      canonical_table TEXT NOT NULL,
      canonical_id TEXT NOT NULL,
      schema_version TEXT NOT NULL,
      payload_json TEXT NOT NULL,
      status TEXT NOT NULL,                     -- 'PENDING', 'PROJECTED', 'FAILED', 'DEAD_LETTER'
      attempt_count INTEGER DEFAULT 0,
      last_error TEXT,
      lease_token TEXT,
      lease_expires_at_utc TIMESTAMP,
      created_at_utc TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      projected_at_utc TIMESTAMP
  );
  ```
* **Rollback Protocol**:
  1. Writers paused via application flag `WARGAME_DB_TARGET=PAUSED`.
  2. Projector drains all `PENDING` outbox rows to legacy databases and verifies count.
  3. Router switches primary writer to legacy DBs via `WARGAME_DB_TARGET=LEGACY`.
  4. Result: Zero lost writes during the rollback window.
* **Acceptance Gate**:
  * Command: `pytest tests/test_outbox_rollback.py`
  * Assertions: Injects crashes before and after legacy writes; verifies exactly-once projection; executes rollback command and verifies 100% of rows exist in legacy DBs.

---

### Milestone 0.8: Operational Verification Gate -> `OPERATIONALLY_ACCEPTED_CAPTURE_V1`
* **Target Path**: `scripts/trading_brain/testing/operational_soak_gate.py`
* **Operational Acceptance Criteria**:
  * Phase 0 achieves `OPERATIONALLY_ACCEPTED_CAPTURE_V1` operational acceptance when it passes:
    1. **Automated Scenario Suite**: 6 scenario tests (no-trade, early close, DST transition, contract roll, feed outage & reconnect, crash & recovery).
    2. **Quantified Live Soak Metrics**: 10 consecutive live trading sessions captured with:
       - 0 unquarantined data loss.
       - 0 duplicate events.
       - <= 2 quarantined rows in `unmatched_link_events` requiring manual linkage across 10 sessions.
       - EOD Process Delta Report renders with 0 errors on 10/10 sessions.

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
  3. **Execution Capture Delta**: Compares actual execution against registered execution policy in `strategy_versions.execution_policy_json`.
  4. **Intervention Telemetry**: Factual counts of hard locks, soft friction overrides, and plan deviations.
* **Acceptance Gate**:
  * Command: `pytest tests/test_daily_process_delta.py`

---

### Milestone 1.2: One-Page Event-First Process Delta Report
* **Target Path**: `scripts/trading_brain/reports/render_process_delta.py`
* **Format**: Markdown (`data/wargaming/reports/daily_process_delta_YYYY-MM-DD.md`) + Terminal output.
* **Sections**: Session Identification, Plan & Forecast vs Realized Tape, Opportunity & Execution Ledger, RiskGuard Intervention Log, Quarantined Reflection Space (`behavioral_declarations`).
* **Acceptance Gate**:
  * Command: `pytest tests/test_process_delta_report.py` (Tested across 8 golden session archetypes).

---

### Milestone 1.3: Read-Only Memory Bridge (`agent_memory_bridge.py`)
* **Target Path**: `scripts/trading_brain/bridges/agent_memory_bridge.py`
* **Boundary Preserved**: `.agent/memory.db` owns development memories and skill proposals; `trading_brain.sqlite` is the sole trading ledger. Bridge provides a typed read-only interface.
* **Acceptance Gate**:
  * Command: `pytest tests/test_agent_memory_bridge.py`

---

## 4. Phase 2: Minute-Scale Feedback & Blinded Deliberate Practice

### Objective
Bridge the gap between pre-market analysis and live execution through real-time friction and high-repetition blinded simulation drills.

---

### Milestone 2.1: Python Post-Submission Deviation Annotator
* **Target Path**: `scripts/trading_brain/guard/deviation_annotator.py`
* **Functionality**: Consumes execution stream post-submission, compares against `get_plan_as_of`, logs `OBSERVED_DEVIATION_ANNOTATION` events in `intervention_events`.
* **Acceptance Gate**:
  * Command: `pytest tests/test_deviation_annotator.py` (Tested against 10 golden compliant and deviant execution traces).

---

### Milestone 2.2: Cross-Repository C# RiskGuard & MCP Plan Push Addon
* **Target Paths**:
  * `C:\Users\vinay\nt8-riskguard\addons\PlanFrictionRule.cs` (in `nt8-riskguard` repo).
  * `C:\Users\vinay\nt8-mcp-bridge\src\Rules\PlanPushHandler.cs` (in `nt8-mcp-bridge` repo).
  * `C:\Users\vinay\nt8-mcp-bridge\mcp\` (MCP tool definitions).
* **Operational Deployment Sequence**:
  1. Update vendored-core submodule tag in `nt8-mcp-bridge` and run `python deploy.py` to prevent stale submodule pin reverting live core.
  2. Verify CI status with `gh run list` in both repositories before deployment.
  3. Deploy to NinjaTrader Custom directory $\rightarrow$ compile via `nt_compile`.
  4. Note: New MCP tool `nt_riskguard_plan_push` becomes visible upon client/MCP server restart.
* **Safety Contract**:
  * Python pushes plan constraints via `nt_riskguard_plan_push` at 08:45 ET.
  * If bridge is down or plan is stale, plan friction **defaults to disabled/shadow** and **NEVER blocks trades**.
  * **Exit Preservation**: Plan friction **NEVER intercepts or delays risk-reducing or protective exit orders**.
* **Cross-Repository Acceptance Gate**:
  * Commands in `nt8-riskguard`:
    ```powershell
    dotnet build tests/RiskGuardTests.csproj
    dotnet run --project tests/RiskGuardTests.csproj --no-build
    python tools/check_no_stray_copies.py
    python tools/check_ci_runs_every_battery.py
    ```
  * Commands in `nt8-mcp-bridge`:
    ```powershell
    dotnet build tests/BridgeTests.csproj
    dotnet run --project tests/BridgeTests.csproj --no-build
    python tools/check_bridge_parses.py
    python tools/check_ci_runs_every_battery.py
    cd mcp && node --test
    ```
  * Verification: `nt_compile` compiles cleanly; test suite proves protective exits are never delayed.

---

### Milestone 2.3: Blinded Deliberate-Practice Replay Engine
* **Target Path**: `scripts/trading_brain/practice/drill_engine.py`
* **Split Custody & Anti-Memorization Invariants**:
  * Assessment session IDs cannot overlap training/calibration sets.
  * Dates, symbols, future bars, and original plans are blinded before answer lock.
  * User commits to Bias, Setup, Invalidation, Entry, Stop, and Target before bars are revealed.
  * Answer lock is immutable; assessment sessions retire after use.
* **Acceptance Gate**:
  * Command: `pytest tests/test_drill_engine.py`

---

### Milestone 2.4: Recurring-Error Targeted Drill Generator
* **Target Path**: `scripts/trading_brain/practice/drill_generator.py`
* **User-Controlled Curriculum**:
  * Scans `intervention_events` and `daily_process_delta` logs for recurring deviations (requires minimum recurrence evidence, e.g. >= 3 occurrences).
  * Requires user approval before scheduling drills.
  * Generates drills addressing the specific weakness along with near-miss/contrast examples.
  * Drills are tagged `PRACTICE_DRILL` and strictly quarantined from live statistical evidence.
* **Acceptance Gate**:
  * Command: `pytest tests/test_drill_generator.py`

---

## 5. Phase 3: Research Gates, Calibration & Multi-Tier Promotion

### Objective
Provide statistical machinery for discovering, testing, and promoting decision rules with strict separation between forecast models, signal models, execution policies, and portfolio deployment.

---

### Milestone 3.1: Multiclass Proper-Score Loss Engine
* **Target Path**: `scripts/trading_brain/research/calibration_engine.py`
* **Functionality**: Computes Multiclass Brier Score and Log Loss across all 5 classes vs 3 baselines (unconditional base rate, rolling 50-session frequency, incumbent champion).
* **Acceptance Gate**:
  * Command: `pytest tests/test_calibration_engine.py` (Tested against mathematical array fixtures).

---

### Milestone 3.2: Multi-Fold Purged Walk-Forward Validator
* **Target Path**: `scripts/trading_brain/research/walk_forward_gate.py`
* **Multiplicity Procedures**: Benjamini-Hochberg (BH) for positive dependence; Benjamini-Yekutieli (BY) for arbitrary dependence; Holm-Bonferroni for family-wise control. Purged folds & Stationary Block Bootstrap.
* **Acceptance Gate**:
  * Command: `pytest tests/test_walk_forward_gate.py`

---

### Milestone 3.3: Preregistered Shadow Validation Gate
* **Target Path**: `scripts/trading_brain/research/shadow_gate.py`
* **Execution Contract**: Task-specific MDE, power >= 0.80, 1-time sealed shadow data evaluation with custody access logging. Terminal states:
  - `PROMOTED`: Validated and passed all criteria.
  - `INCONCLUSIVE_WAITING`: Unpromoted; remains frozen while new data accumulates.
  - `REJECTED`: Permanently closed.
  - `INVALID_TEST`: Test execution flaw; cannot be promoted.
* **Acceptance Gate**:
  * Command: `pytest tests/test_shadow_gate.py`

---

### Milestone 3.4: Decoupled Multi-Tier Promotion Engine
* **Target Path**: `scripts/trading_brain/research/promotion_orchestrator.py`
* **Four Independent Promotion Tiers**:
  1. Tier 1 (Forecast Model): Calibration and discrimination.
  2. Tier 2 (Signal Model): Opportunity expectancy and precision.
  3. Tier 3 (Execution Policy): Realized EV in R after costs.
  4. Tier 4 (Portfolio Deployment): Drawdown, tail risk, capacity, and prop constraints.
* **Acceptance Gate**:
  * Command: `pytest tests/test_promotion_orchestrator.py`

---

## 6. Phase 4: Typed Intake Catalog & Web Workspace

### Objective
Provide a unified, human-native intake interface and interactive web dashboard for daily wargaming, post-market review, and deliberate practice.

---

### Milestone 4.1: Universal Typed Intake Catalog (`information_items`)
* **Target Path**: `scripts/trading_brain/intake/catalog_router.py`
* **Functionality**: Ingests the 9 information types. Decision retrieval queries enforce `available_at_utc <= decision_cutoff_utc`.
* **Acceptance Gate**:
  * Command: `pytest tests/test_catalog_router.py`

---

### Milestone 4.2: Web Dashboard UI Integration
* **Target Path**: `web/` (Next.js, Tailwind CSS, Shadcn/UI, Lightweight Charts)
* **Features**: Pre-Market Wargame Builder, Daily Process Delta Scorecard, Deliberate Practice Station, Model Governance Dashboard.
* **Acceptance Gate**:
  * Commands in `web/`:
    ```bash
    npm run test:contracts
    npm run lint
    npm run build
    npx playwright test
    ```

---

## 7. Immediate Next Steps, Estimates & Dependency Matrix

| Milestone ID | Action Item | Estimated Effort | Target Delivery | Prerequisite / Dependency |
| :---: | :--- | :---: | :--- | :--- |
| **M0.1** | **Canonical SQLite Schema & 36-Trigger Matrix** (`schema.sql`, `test_trading_brain_db.py`) | 1.0 Day | Phase 0 Start | Implementation Plan Approved |
| **M0.2** | **Plan Snapshot Ledger & `get_plan_as_of`** (`plan_adapter.py`, `test_plan_adapter.py`) | 1.0 Day | Milestone 0.1 | M0.1 |
| **M0.3a**| **Shadow Legacy Import & Dual-Hash Check** (`import_legacy_shadow.py`) | 0.5 Day | Milestone 0.1 | M0.1 |
| **M0.4** | **Two-Phase Sealed Forecast Registrar** (`forecast_registrar.py`, `market_calendar.py`) | 1.5 Days | Milestone 0.1 | M0.1, `market_calendar.py` |
| **M0.5** | **As-Of Signal Opportunity Logger** (`opportunity_logger.py` + V0 JSON artifacts) | 1.5 Days | Milestone 0.1 | M0.1, Frozen Strategy V0 |
| **M0.6** | **Hardened NT8 Ingestion & Cursor Tailer** (`nt8_broker_adapter.py`, `test_nt8_broker_adapter.py`) | 1.5 Days | Milestone 0.1 | M0.1, Durable Ingest Surface |
| **M0.7** | **Tape Extractor & Live Storage Resolver** (`tape_extractor.py`, `live_storage_resolver.py`) | 1.0 Day | Milestone 0.1 | M0.1 |
| **M0.3b**| **Outbox Projector, Writer Cutover & Rollback Fence** (`outbox_projector.py`) | 1.0 Day | Milestone 0.7 | M0.1, M0.2, M0.3a, M0.4, M0.5, M0.6, M0.7 |
| **M0.8** | **Operational Verification Gate** (`OPERATIONALLY_ACCEPTED_CAPTURE_V1` - Scenario suite + soak) | 10 Sessions | Phase 0 Done | M0.3b Passed |
| **M1.0** | **Phase 1 Re-Approval Review** | Formal Gate | Formal Sign-Off | M0.8 Passed |
