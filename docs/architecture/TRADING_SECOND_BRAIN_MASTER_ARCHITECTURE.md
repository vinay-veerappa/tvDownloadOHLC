# 🧠 Unified Trading Second Brain: Institutional Evidence & Decision Protocol

> **Document Version**: 4.2.0 (Institutional Evidence, Intake & Decision Protocol)
> **Status**: Canonical Architecture Blueprint & System Specification  
> **Location**: `docs/architecture/TRADING_SECOND_BRAIN_MASTER_ARCHITECTURE.md`  
> **Core Axiom**: *The system automates observation collection, measurement, and candidate generation, but NEVER autonomously promotes hypotheses into live decision rules. Live models require registered hypotheses, multiplicity-controlled out-of-sample validation across multiple historical regimes, and explicit human governance.*

---

## 1. Executive Summary & Epistemological Foundation

The **Trading Second Brain** is an institutional-grade, **evidence-controlled learning and execution platform**. It establishes a mathematically sound boundary between theoretical doctrine, empirical market measurements, algorithmic hypotheses, execution event streams, and live production decision rules.

### The 4 Core Epistemological Truths:
1. **Knowledge $\ne$ Truth**: Books, PDFs, and video transcripts (*Mickey, Austin, ICT, LumiTrader*) are **qualitative doctrine and hypothesis generators**, not empirical truth.
2. **Market Data is a Measured Observation**: Stored OHLCV tape records are versioned observations subject to quality flags, vendor revisions, contract rolls, and adjustment policies.
3. **Observational Correlation $\ne$ Causal Attribution**: Trader P&L correlations (e.g. trading before 09:45 ET) are observational associations. They cannot be reported as causal "costs" without deterministic counterfactual replays or matched opportunity controls.
4. **Self-Learning live models without out-of-sample validation are destructive**: Repeatedly inspecting a holdout converts it into training data. Live decision rules must pass rolling walk-forward folds, multiplicity corrections, and benchmark comparisons before promotion.

---

## 2. The Four Evidence Layers (Strict Separation of Concerns)

To prevent self-reinforcing statistical contamination and feedback loops, the system enforces a strict boundary across four distinct evidence layers:

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 THE FOUR EVIDENCE LAYERS                                         │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
  
  LAYER 1: KNOWLEDGE & DOCTRINE (Hypothesis Sources)
  • Ingested Books, PDFs (LumiTrader, ICTNotes, Flux Guide), Transcripts (Mickey, Austin, TCM)
  • Role: Qualitative explanations, setup concepts, and hypothesis proposals.
  • Constraint: Purely descriptive context. CANNOT alter live features, probabilities, or sizing.
  • Affect Live Trading: ❌ NO.
  
                                  │
                                  ▼
  LAYER 2: OBSERVATIONS & EVENT LEDGERS (Empirical Records)
  • Signal Opportunities Ledger (`signal_opportunities` — every eligible setup, taken or missed)
  • Immutable Forecast Snapshots (`forecast_snapshots` — sha256, timestamps, full-precision probs)
  • Measured Tape Observations (`session_tape_actuals` — vendor provenance, quality state)
  • Execution Event Ledger (`execution_events` — fills, partial exits, stop modifications, slippage)
  • Behavioral Declarations (`behavioral_declarations` — emotional state, rule compliance)
  • Constraint: Append-only records with provenance and correction events. CANNOT alter live trading weights autonomously.
  • Affect Live Trading: ❌ NO.
  
                                  │
                                  ▼
  LAYER 3: CANDIDATE FINDINGS (Pre-Registered Hypotheses)
  • Mechanically derived hypotheses generated under pre-registered feature/outcome definitions.
  • Stored with sample size ($n$), point estimates, dependence-aware confidence intervals, and effect size.
  • Quarantined from active trading models until rolling out-of-sample validation passes.
  • Affect Live Trading: ❌ NO.
  
                                  │
                                  ▼
  LAYER 4: PROMOTED DECISION MODELS (Certified Production Rules)
  • Multiplicity-corrected models that beat unconditional and simple conditional baselines out-of-sample.
  • Validated across rolling chronological walk-forward folds + 1-time sealed shadow holdout.
  • Versioned immutable parameter artifacts (`models/model_v4_1.json`).
  • Subject to continuous drift monitoring, drawdown limits, automatic demotion, and manual kill-switches.
  • Affect Live Trading: ✅ YES.
```

---

## 3. The 6-Component Evidence Architecture

```
┌──────────────────────────────┐          ┌──────────────────────────────┐          ┌──────────────────────────────┐
│     1. KNOWLEDGE LIBRARY     │          │ 2. FEATURE & CONCEPT ENGINE  │          │     3. FORECAST REGISTRY     │
│   (LanceDB Semantic Store)   │          │    (`scripts/concepts/`)     │          │  (`forecast_snapshots` DB)   │
├──────────────────────────────┤          ├──────────────────────────────┤          ├──────────────────────────────┤
│ • Versioned PDF & Book Units │          │ • NQStats ALN Dynamics       │          │ • Immutable Forecast Snapshot│
│ • Transcripts & Playbooks    │ -research>│ • Candle Science Excursions  │ ───────> │ • Hash, Timestamps, Models   │
│ • Keyword Semantic Search    │          │ • P12 Directional Vectors    │          │ • Missing Provider Tracking  │
│ • Purely Descriptive Context │          │ • Session Budget (DRO %)     │          │ • Unambiguous Probabilities  │
└──────────────────────────────┘          └──────────────────────────────┘          └──────────────┬───────────────┘
                                                                                                   │
  ┌────────────────────────────────────────────────────────────────────────────────────────────────┘
  ▼
┌──────────────────────────────┐          ┌──────────────────────────────┐          ┌──────────────────────────────┐
│       4. EVENT LEDGER        │          │    5. EVALUATION ENGINE      │          │     6. PROMOTION GATE        │
│    (Orders, Fills, Tape)     │          │    (Mechanical Scoring)      │          │ (Walk-Forward & Approval)    │
├──────────────────────────────┤          ├──────────────────────────────┤          ├──────────────────────────────┤
│ • Signal Opportunities       │          │ • Multiclass Brier Scoring   │          │ • Pre-Registered Hypotheses  │
│ • Tape Actuals & Provenance  │ ───────> │ • Strategy Expectancy in R   │ ───────> │ • Multi-Fold Walk-Forward    │
│ • Execution Event Stream     │          │ • Execution Attribution      │          │ • FDR / Multiplicity Control │
│ • Behavioral Declarations    │          │ • Observational Association  │          │ • Human Governance & Audit   │
└──────────────────────────────┘          └──────────────────────────────┘          └──────────────────────────────┘
```

The Knowledge Library arrow is a research-time hypothesis-proposal path only. Live feature computation cannot query doctrine, accept LLM-authored values, or change probabilities or sizing from retrieved text. A doctrinal proposal reaches runtime only after it becomes deterministic code and passes the promotion protocol.

---

## 4. Rigorous Deep-Dive Specifications

### 🎯 Outcome Ontology & MECE Label Functions
To prevent conflating distinct prediction tasks, the system establishes versioned executable label functions. A label is not valid merely because it has a written description: the implementation, precedence rules, input window, missing-data behavior, and tests are part of the label version.

#### A. The 5-Outcome Day-Type Task (`LABEL_DAY_TYPE_V1`)
* **Task Scope**: Predicts the primary directional archetype of the RTH session relative to NY1 Initial Range (`07:30–08:30 ET`).
* **Classes**:
  1. `SF` (Short False): Sweeps below NY1 Low before 10:15 ET $\rightarrow$ Reverses to close above NY1 Mid.
  2. `LF` (Long False): Sweeps above NY1 High before 10:15 ET $\rightarrow$ Reverses to close below NY1 Mid.
  3. `LT` (Long True): Defends NY1 Mid/Low $\rightarrow$ Expands to print HOD after 14:30 ET.
  4. `ST` (Short True): Rejects NY1 Mid/High $\rightarrow$ Expands to print LOD after 14:30 ET.
  5. `ROTATIONAL_CHOP`: No directional class qualifies by 16:00 ET.
* **MECE Requirement**: `LABEL_DAY_TYPE_V1` must define deterministic precedence for sessions satisfying both sweep conditions or both true/false descriptions. Exactly one of the five labels must be returned for every complete session; incomplete sessions return `DATA_INCOMPLETE`, which is excluded from scoring rather than treated as a market class.

#### B. The EOD Diagnostic Classification Task (`LABEL_EOD_CLASSIFICATION_V1`)
* **Task Scope**: Evaluates post-market 16:15 ET structure against historical 4,300-session distributions.
* **Classes**: `R1` (Rotational 1-Side), `R2` (Rotational 2-Side Expansion), `DNP` (Directional No Pullback), `DWP` (Directional With Pullback).

#### C. Target Box & Excursion Events
* `P30_HIT`, `P50_HIT`, `P70_HIT`, `P70_REVERSED`, `P12_MID_TOUCHED`. Evaluated strictly from tick / 1m high-low bounds.

#### D. Instrument, Session, and Data-Revision Contract
Every label and feature declares:

1. **Instrument identity**: root, actual contract or continuous series, roll rule, and back-adjustment policy. Results from a back-adjusted continuous series are not execution prices.
2. **Logical session date**: the futures trading day beginning at 18:00 `America/New_York`, with RTH windows calculated in `America/New_York` and persisted timestamps in UTC.
3. **As-of availability**: a feature may consume only records whose `available_at_utc` is at or before the forecast cutoff, not records merely stamped with an earlier market time.
4. **Data revision**: vendor, ingest ID, content hash, completeness state, and superseded revision. Corrected tape creates a new revision and triggers a new evaluation; it never rewrites the evaluation originally observed.
5. **Corporate/calendar inputs**: economic-event and trading-calendar records are versioned as-of snapshots so later corrections cannot leak into historical forecasts.

These fields are mandatory parts of the data manifest. Tests must include contract-roll dates, DST transitions, early closes, missing bars, duplicate bars, and late-arriving corrections.

---

### 📡 Signal Opportunity Ledger (`signal_opportunities`)
To decouple **strategy expectancy** from **discretionary trader selection**, the system mechanically logs every eligible signal. Ex-ante opportunity facts, later execution decisions, and post-hoc outcomes are separate append-only records; the original opportunity is never updated after the signal timestamp.

```sql
CREATE TABLE signal_opportunities (
    opportunity_id TEXT PRIMARY KEY,          -- UUID v4
    prediction_id TEXT,                       -- Forecast in force when the signal fired
    session_date DATE NOT NULL,
    ticker TEXT NOT NULL,
    timestamp_utc TIMESTAMP NOT NULL,        -- Exact bar timestamp when signal became active
    strategy_id TEXT NOT NULL,               -- E.g. 'STRAT_ALN_LPEU_V1'
    model_version TEXT NOT NULL,
    eligibility_rule_version TEXT NOT NULL,
    direction TEXT NOT NULL,                 -- 'LONG', 'SHORT'
    trigger_price REAL NOT NULL,
    proposed_stop_bps REAL NOT NULL,
    proposed_target_1_bps REAL NOT NULL,     -- Cover The Queen (+10 bps)
    proposed_target_2_bps REAL,              -- Runner (+30 bps)
    feature_snapshot_json TEXT NOT NULL,
    created_at_utc TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (strategy_id) REFERENCES strategies(strategy_id),
    FOREIGN KEY (prediction_id) REFERENCES forecast_snapshots(prediction_id)
);

CREATE TABLE signal_disposition_events (
    disposition_id TEXT PRIMARY KEY,
    opportunity_id TEXT NOT NULL,
    recorded_at_utc TIMESTAMP NOT NULL,
    disposition TEXT NOT NULL,               -- 'EXECUTED', 'PASSED', 'MISSED', 'OFFLINE'
    reason_code TEXT,
    FOREIGN KEY (opportunity_id) REFERENCES signal_opportunities(opportunity_id)
);

CREATE TABLE signal_outcomes (
    outcome_id TEXT PRIMARY KEY,
    opportunity_id TEXT NOT NULL,
    policy_version TEXT NOT NULL,             -- Defines horizon, fill ordering, stop/target rules
    data_manifest_hash TEXT NOT NULL,
    theoretical_mfe_bps REAL,
    theoretical_mae_bps REAL,
    theoretical_result TEXT,
    evaluated_at_utc TIMESTAMP NOT NULL,
    FOREIGN KEY (opportunity_id) REFERENCES signal_opportunities(opportunity_id),
    UNIQUE (opportunity_id, policy_version, data_manifest_hash)
);
```

---

### 🔮 Forecast Registry & Full Provenance (`forecast_snapshots`)
Every pre-market plan generates an **immutable forecast snapshot** before market open (`08:45–09:15 ET`):

```sql
CREATE TABLE forecast_snapshots (
    prediction_id TEXT PRIMARY KEY,          -- UUID v4
    session_date DATE NOT NULL,
    ticker TEXT NOT NULL,
    created_at_utc TIMESTAMP NOT NULL,       -- ISO-8601 UTC
    effective_cutoff_utc TIMESTAMP NOT NULL, -- E.g. 2026-08-28T12:45:00Z (08:45 ET)
    forecast_mode TEXT NOT NULL,             -- 'LIVE_PRODUCTION', 'REPLAY_AUDIT', 'SHADOW'
    original_prediction_id TEXT,             -- Required for REPLAY_AUDIT
    run_id TEXT NOT NULL,                    -- Distinguishes repeated audit/shadow runs
    label_function_version TEXT NOT NULL,
    
    -- Exact Reproducibility Manifest
    git_commit_hash TEXT NOT NULL,           -- Exact code version
    environment_hash TEXT NOT NULL,          -- Python & dependency lock hash
    config_hash TEXT NOT NULL,               -- SHA-256 of active wargame parameters
    data_manifest_hash TEXT NOT NULL,        -- SHA-256 of input Parquet / Live data
    source_data_max_timestamp_utc TIMESTAMP NOT NULL,
    
    -- Unambiguous High-Precision Forecasts
    spot_price REAL NOT NULL,
    p_short_false REAL,                      -- NULL when abstaining
    p_long_false REAL,
    p_long_true REAL,
    p_short_true REAL,
    p_rotational_chop REAL,
    abstain_flag BOOLEAN NOT NULL DEFAULT FALSE,
    abstain_reason TEXT,
    
    -- Snapshots
    feature_snapshot_json TEXT NOT NULL,
    active_setups_json TEXT NOT NULL,
    provider_manifest_json TEXT NOT NULL,    -- Detailed provider status, versions, freshness

    FOREIGN KEY (original_prediction_id) REFERENCES forecast_snapshots(prediction_id),
    CONSTRAINT uq_forecast_run UNIQUE (session_date, ticker, effective_cutoff_utc, forecast_mode, run_id),
    CONSTRAINT ck_replay_parent CHECK (forecast_mode <> 'REPLAY_AUDIT' OR original_prediction_id IS NOT NULL),
    CONSTRAINT ck_forecast_mode CHECK (forecast_mode IN ('LIVE_PRODUCTION', 'REPLAY_AUDIT', 'SHADOW')),
    CONSTRAINT ck_abstention_payload CHECK (
        (abstain_flag = 1 AND abstain_reason IS NOT NULL AND
         p_short_false IS NULL AND p_long_false IS NULL AND p_long_true IS NULL AND
         p_short_true IS NULL AND p_rotational_chop IS NULL)
        OR
        (abstain_flag = 0 AND abstain_reason IS NULL AND
         p_short_false BETWEEN 0 AND 1 AND p_long_false BETWEEN 0 AND 1 AND
         p_long_true BETWEEN 0 AND 1 AND p_short_true BETWEEN 0 AND 1 AND
         p_rotational_chop BETWEEN 0 AND 1 AND
         ABS(p_short_false + p_long_false + p_long_true + p_short_true + p_rotational_chop - 1.0) <= 1e-9)
    )
);
```

Only one `LIVE_PRODUCTION` forecast may be authoritative for a ticker and cutoff. Enforce that invariant with a partial unique index over live rows; replay and shadow rows remain repeatable through `run_id`. An abstention stores no probabilities, preventing a degraded run from looking like a valid forecast.

```sql
CREATE UNIQUE INDEX uq_live_forecast
ON forecast_snapshots(session_date, ticker, effective_cutoff_utc)
WHERE forecast_mode = 'LIVE_PRODUCTION';
```

#### Replay and Reproducibility Rules:
1. **Live Forecast Immutability**: Live forecasts (`forecast_mode = 'LIVE_PRODUCTION'`) can **NEVER** be updated or deleted.
2. **Replay Audits**: Re-running a forecast creates an explicit `REPLAY_AUDIT` record with its own `prediction_id` and references the original live snapshot. Replays never overwrite live records.
3. **Deterministic Verification**: Given the recorded code artifact, environment, configuration, provider manifest, and immutable input manifest, the same supported runtime must reproduce the canonical serialized forecast byte-for-byte. Cross-runtime numerical comparisons use a documented tolerance rather than assuming universal floating-point identity.

---

### 📑 Event Ledger & Broker State Envelope (`execution_events`)
The event ledger captures orders, fills, cancellations, stop modifications, and position reconciliations with full broker state correlation:

```sql
CREATE TABLE execution_events (
    event_id TEXT PRIMARY KEY,               -- UUID v4
    trade_id TEXT NOT NULL,                  -- Local correlation ID grouping lifecycle
    opportunity_id TEXT,                     -- FK to signal_opportunities (NULL if discretionary)
    session_date DATE NOT NULL,
    ticker TEXT NOT NULL,
    account_id TEXT NOT NULL,                -- E.g. 'Sim101', 'APEX-12948'
    broker_name TEXT NOT NULL,               -- 'NinjaTrader', 'Tradovate', 'Schwab'
    
    -- Event Identification & Ordering
    event_seq INTEGER NOT NULL,              -- Monotonic sequence within trade_id
    event_type TEXT NOT NULL,                -- 'ORDER_SUBMITTED', 'FILL', 'CANCEL_ACK', 'REPLACE_ACK', 'STOP_MODIFIED', 'REJECTED'
    client_order_id TEXT NOT NULL,           -- Stable client-generated UUID
    broker_order_id TEXT,                    -- Broker-assigned ID
    broker_execution_id TEXT,                -- Provider fill/execution identifier
    parent_order_id TEXT,                    -- Bracket parent ID
    idempotency_key TEXT NOT NULL,            -- Stable ingest deduplication key
    corrects_event_id TEXT,                  -- Append-only correction/supersession link
    
    -- Timestamps (DST-Safe ISO-8601 UTC)
    exchange_timestamp_utc TIMESTAMP,        -- Timestamp recorded by exchange
    broker_timestamp_utc TIMESTAMP,          -- Timestamp recorded by broker API
    received_timestamp_utc TIMESTAMP NOT NULL,-- Timestamp received locally
    
    -- Order Details
    payload_schema_version TEXT NOT NULL,     -- Type-specific event payload contract
    action TEXT,                             -- 'BUY', 'SELL'; nullable when event has no side
    order_type TEXT,                         -- Nullable for reconciliation/correction events
    quantity INTEGER,                        -- Original order quantity when applicable
    limit_price REAL,
    stop_price REAL,
    fill_price REAL,                         -- NULL for non-fill events
    fill_quantity INTEGER,                   -- Partial fill quantity
    commission_dollars REAL DEFAULT 0.0,
    slippage_bps REAL DEFAULT 0.0,
    
    -- Attribution Tags
    order_role TEXT,                         -- 'ENTRY', 'SCALE_1_QUEEN', 'RUNNER', 'STOP_LOSS'
    raw_broker_payload TEXT,
    created_at_utc TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (opportunity_id) REFERENCES signal_opportunities(opportunity_id),
    FOREIGN KEY (corrects_event_id) REFERENCES execution_events(event_id),
    UNIQUE (account_id, idempotency_key),
    UNIQUE (trade_id, event_seq)
);
```

SQLite connections must execute `PRAGMA foreign_keys = ON`; schema migrations and integrity tests verify this rather than assuming declared foreign keys are active. Broker corrections append a new event referencing `corrects_event_id`; they never rewrite the received event. Type-specific validation keyed by `(event_type, payload_schema_version)` defines which nullable envelope fields are required, so cancellation, rejection, correction, and position-reconciliation events are representable without fabricated prices or quantities.

#### Tape Observation Revisions

`session_tape_actuals` is append-only and keyed by a generated revision ID, not by date alone. It stores `(logical_session_date, ticker, contract_id, session_definition_version, vendor, adjustment_policy, data_manifest_hash, quality_state, observed_at_utc, supersedes_actual_id)`. A partial unique index permits only one current revision for that exact observation scope. Evaluations reference the specific tape revision they scored, so a vendor correction cannot silently change historical metrics.

---

### 🔬 Evaluation Engine (Multiclass Calibration & Attribution)

#### A. Multiclass Brier Score & Log Loss
For $K = 5$ mutually exclusive day-type outcomes over $N$ complete, eligible sessions:

$$\text{Brier Score} = \frac{1}{N} \sum_{t=1}^N \sum_{k=1}^5 (p_{t,k} - y_{t,k})^2$$

$$\text{Log Loss} = -\frac{1}{N} \sum_{t=1}^N \sum_{k=1}^5 y_{t,k} \ln(p_{t,k})$$

where $y_{t,k} \in \{0, 1\}$ is the one-hot indicator of the mechanically evaluated outcome, and $p_{t,k}$ is the forecast probability.

#### B. Benchmark Incremental Value Requirement
A model is evaluated against three mandatory baselines:
1. **Unconditional Historical Base-Rate**: $p_k = \bar{y}_k$ over all prior history.
2. **Recency-Weighted Frequency**: Rolling 50-session frequency.
3. **Incumbent Production Model**: Previous certified version, when one exists.

The pre-registration specifies one primary scoring metric and its minimum practically meaningful improvement. Secondary metrics are guardrails, not extra opportunities to declare success. Promotion requires a positive dependence-aware confidence bound for paired loss improvement over every applicable baseline after multiplicity correction, no material degradation on guardrails, and positive executable utility after costs. A universal unpaired `$p < 0.01$` rule is prohibited.

#### C. Observational vs. Causal Behavioral Reporting
* **Prohibited**: *"Trading before 09:45 ET cost $-\$1,420$."*
* **Required**: *"Pre-09:45 ET trades were associated with $-\$1,420$ lower realized P&L ($-\Delta 18.4\text{ bps}$) across $N=24$ sessions, conditional on recorded volatility and signal filters."*
* **Policy Replay**: Deterministic replay may estimate a policy-specific counterfactual only when the alternative action was feasible and the fill model, latency, spread, and ordering assumptions are recorded. Replay remains a model-based estimate, not proof of causality.

---

### 🛡️ Promotion Gate: Multi-Fold Walk-Forward & Multiplicity Control

To reduce data mining, p-hacking, and regime overfitting:

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                            ROLLING WALK-FORWARD VALIDATION DESIGN                                │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘

  EXAMPLE FOLD 1: Train [T0–T3] ──> Calibrate [T4] ──> Test [T5]
  EXAMPLE FOLD 2: Train [T1–T4] ──> Calibrate [T5] ──> Test [T6]
  EXAMPLE FOLD 3: Train [T2–T5] ──> Calibrate [T6] ──> Test [T7]

  SEALED FINAL SHADOW TEST: Future observations beginning only after the
  hypothesis, code, analysis plan, and holdout boundary are registered.
```

The dates above are relative examples, not permission to relabel previously inspected history as unseen. In particular, 2026 data already analyzed anywhere in this repository is not a sealed holdout. Fold lengths, purge gaps, embargoes, and retraining cadence are selected from the prediction horizon and dependence structure before testing.

#### Multiplicity & Statistical Rigor Requirements:
1. **Pre-Registration**: Feature definitions, label functions, and model architectures must be frozen and committed to git **BEFORE** accessing out-of-sample folds.
2. **False Discovery Rate (FDR) Control**: Before screening, define the complete research family containing every setup, regime split, target, horizon, instrument, and model variant being considered. Apply Benjamini-Hochberg at $\alpha = 0.05$ only where its dependence assumptions are defensible; otherwise use a valid dependent-test procedure or stricter family-wise control. Unreported failed variants remain part of the family.
3. **Dependence-Aware Uncertainty**: Confidence intervals and tests on financial time-series MUST use a pre-specified dependence-aware method appropriate to the statistic, such as stationary block bootstrap or Newey-West HAC standard errors. The block-length or lag-selection rule is fixed before evaluation.
4. **Minimum Detectable Effect (MDE) & Power**: Sample size must satisfy prospective power requirements ($1-\beta \ge 0.80$) for a task-specific economically meaningful effect after costs. The effect unit is bps or R for strategy utility and proper-score improvement for forecasts; no universal 5 bps threshold applies to every task.
5. **Sealed Holdout Custody**: The final holdout is evaluated once by a separate command that emits a signed result artifact. A failed candidate cannot be tuned and resubmitted against the same holdout; the next candidate waits for a new untouched period.
6. **Leakage Control**: Overlapping labels, feature lookbacks, and trade horizons require purged folds and an embargo at least as long as the maximum information overlap. Scalers, thresholds, feature selection, calibration, and missing-data decisions are fitted inside each training fold only.
7. **Portfolio Utility**: A profitable standalone signal is not automatically deployable. Promotion also evaluates incremental portfolio drawdown, tail loss, exposure concentration, turnover, liquidity/capacity, commissions, slippage, and applicable prop-firm constraints using the repository's canonical risk simulator.

---

### 🚪 Model Governance, Retirement & Kill-Switches

Models are living systems that decay as market microstructures evolve:

```
┌──────────────────────────────┐
│  LIVE PRODUCTION MONITORING  │
│ (Model-Specific Live Window) │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐       Certified statistical drift boundary OR
│    DRIFT & LOSS DETECTION    │ ────> Hard account/risk limit breach
└──────────────┬───────────────┘       
               │
               ▼
┌──────────────────────────────┐
│     AUTOMATIC DEMOTION       │ ────> Reverts to Shadow Mode / Enforces Abstention
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│    MANUAL KILL-SWITCH &      │ ────> User audit & rollback to certified fallback
│      ROLLBACK AUDIT          │
└──────────────────────────────┘
```

1. **Automatic Abstention (`NO_FORECAST` / `NO_TRADE`)**: Each certified model carries a machine-readable input contract defining required providers, per-source freshness limits, coverage, quality states, and out-of-distribution boundaries. Any required-input violation fails closed. Universal thresholds such as 120 seconds, one failed provider, or `4\sigma` are prohibited unless validated for that model and session.
2. **Champion / Challenger Shadow Deployment**: New models run without execution authority until the pre-registered operational checks and prospective sample requirement are met. Twenty sessions may be an operational smoke test, but it is not statistical evidence of safety or edge.
3. **Human Sign-Off Attestation**: Human approval confirms that all pre-registered criteria, FDR corrections, and shadow tests passed. Human approval **CANNOT** waive failed statistical safety gates.

---

## 5. Information Intake, Ingestion, and Meaning Preservation

The system accepts information in many forms, but it must not treat every input as the same kind of evidence. A statistic, strategy rule, morning plan, journal reflection, chart screenshot, broker fill, and live GEX level have different ownership, lifetime, and authority. The intake layer preserves those distinctions before anything is indexed, summarized, compared, or learned from.

### Intake Principles

1. **Capture naturally, normalize deliberately**: The user may provide free-form text, annotated charts, screenshots, PDFs, tables, voice transcripts, or structured forms. The system preserves the original artifact and then proposes structured fields; it does not force the user to speak in database syntax.
2. **Raw source before interpretation**: Every parsed record points to an immutable source artifact or authoritative producer record. OCR, vision output, summaries, extracted statistics, and LLM interpretations are derived assertions, never replacements for the source.
3. **Type before route**: Every input receives an information type, author, event time, ingestion time, effective horizon, instrument/session scope, provenance, and review state before reaching an evidence layer.
4. **No silent promotion**: User-provided rules, external statistics, image interpretations, and extracted claims enter as doctrine, declarations, plans, or candidate findings. They do not become measured facts or production model parameters merely because they are structured.
5. **As-of correctness**: Time-sensitive information is selected by what was available at the decision cutoff. A later value, edited plan, revised calendar, or post-session annotation cannot enter a historical forecast replay as if it were known earlier.
6. **One owner, references elsewhere**: Existing systems remain authoritative. The intake catalog stores a stable reference and content hash rather than duplicating mutable copies of Prisma journals, GEX snapshots, Parquet bars, LanceDB units, or broker events.

### Information Type Matrix

| Information Type | Examples | Native Authority | Evidence Classification | Lifetime | Required Treatment |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **General statistics** | Session probabilities, MFE/MAE distributions, day-of-week tables | Reproducible analysis artifact + data manifest | Candidate finding unless certified | Valid until data/definition revision | Store population, sample window, $N$, units, label version, method, uncertainty, code/data hashes, and limitations. A copied percentage without this metadata is doctrine, not a statistic. |
| **Trading strategy definitions** | Entry trigger, invalidation, stop, target, sizing, no-trade filters | Versioned strategy registry and playbook | Doctrine until executable and validated; promoted model after certification | Versioned, never edited in place | Separate descriptive rationale from executable rules. New edits create a strategy version and require new validation; results never transfer silently between versions. |
| **Knowledge material** | Books, PDFs, transcripts, teaching notes | `video2pdf/knowledge_ingest` + LanceDB source manifest | Doctrine / hypothesis source | Long-lived, source-versioned | Preserve author, title, page/time span, quotation boundaries, license, and source hash. Retrieval may explain or propose; it cannot directly set live values. |
| **Daily trading plans** | Premarket bias, if-then scenarios, invalidations, intended risk | Forecast/plan registry | Ex-ante declaration | Valid for named session and cutoff | Preserve verbatim plan plus structured scenarios. Freeze the version used at the cutoff; later edits are amendments with timestamps, not replacements. Distinguish user-authored, model-generated, and jointly edited text. |
| **Weekly outlooks** | Macro thesis, expected weekly path, key events and levels | Weekly briefing/outlook record | Time-bounded ex-ante declaration | ISO week or explicit start/end | Record publication cutoff, instruments, event calendar snapshot, assumptions, invalidations, and expiry. Daily plans may reference the outlook version but do not copy it as fact. |
| **Trade and behavior journals** | Reasons for entry, emotion, execution review, lesson, weekly review | Prisma `Trade`/`Journal`/`TradeEvent` or append-only journal record | Post-hoc declaration / subjective observation | Permanent with amendments | Preserve the user's exact words. Extract tags and claims separately with confidence and approval state. Do not convert hindsight narratives into ex-ante strategy evidence. |
| **Charts and images** | Annotated post-day chart, weekly review collage, broker screenshot | Content-addressed artifact store + journal link | Visual evidence / user annotation | Permanent, versioned | Store original bytes, hash, capture time, symbol, timeframe, visible range, timezone, source platform, and annotation author. OCR/vision output is a reviewable derived assertion; absent metadata makes the image explanatory only. |
| **Dynamic calculated values** | GEX, gamma flip, call/put walls, expected moves, IV, VWAP, live session ranges | Existing producer tables/files such as `GexSnapshot`, `MacroSnapshot`, RTD/Schwab adapters, and deterministic feature providers | Time-stamped measured or derived observation | Explicit TTL and market-session scope | Store source chain, formula/provider version, underlying snapshot IDs, calculation timestamp, available-at timestamp, expiry, units, instrument mapping, quality, and fallback path. Never write transient values into long-term memory as timeless facts. |
| **Execution and market events** | Orders, fills, cancels, bars, HOD/LOD | Broker/event ledger and versioned market-data stores | Measured observation | Permanent with correction events | Ingest idempotently, preserve provider IDs and receive times, and append corrections. These records are not accepted from narrative extraction when an authoritative machine source exists. |

### Two Intake Lanes

#### A. Human-Native Capture Lane

This lane adapts to how the user communicates:

```text
Free-form text / Markdown / form / voice transcript / chart image / document
        |
        v
Preserve original artifact and context
        |
        v
Classify information type and time orientation (ex-ante, intraday, post-hoc)
        |
        v
Propose structured assertions, tags, links, levels, and strategy references
        |
        v
User review when extraction changes meaning or could influence evaluation
        |
        v
Route to plan, journal, strategy, doctrine, visual-evidence, or candidate store
```

The system should accept familiar phrases such as “my plan for NQ today,” “weekly outlook,” “post-day review,” or “this chart shows where I ignored the invalidation.” It may infer a draft type from context, but it asks for clarification when instrument, session date, whether the content is a plan or hindsight, or the intended strategy version is ambiguous.

The original text or media remains canonical for what the user communicated. Structured extraction records include `extractor_type`, `extractor_version`, `extracted_at_utc`, confidence, source spans or image regions, and one of `PROPOSED`, `USER_CONFIRMED`, `USER_CORRECTED`, or `REJECTED`. Corrections create a new assertion and retain the rejected interpretation for audit.

#### Practical User Submission Patterns

No rigid template is required. These optional fields reduce clarification while preserving normal language:

| User Intent | Minimum Context | Useful Optional Context |
| :--- | :--- | :--- |
| **Share a statistic** | Statistic/value, source or how it was calculated | Instrument, date range, sample size, conditions, units, uncertainty, whether it is published or personally computed |
| **Add or revise a strategy** | Strategy name and actual entry/exit logic | Version/change reason, timeframe, session, invalidation, sizing, costs, no-trade filters, examples, current validation status |
| **Create today's plan** | Session date, instrument, scenarios and invalidations | Preparation cutoff, active strategy versions, key levels with source/timestamp, intended risk, event risks, what would cause `NO_TRADE` |
| **Create a weekly outlook** | Week/start date, instruments, thesis and invalidation | Scheduled events, expected moves with snapshot IDs, scenarios, key levels, risk posture, expiry |
| **Record a post-day/week journal** | Session/week, instrument, verbatim reflection | Trade IDs, plan version, chart attachments, rule adherence, emotions, surprises, lessons proposed for review |
| **Attach a chart/image** | What the image represents and session/instrument | Capture time, platform, timeframe, visible range, timezone, annotations to preserve, claims the user wants checked |
| **Supply a dynamic value** | Metric name, value, instrument, timestamp, source | Units, expiry/DTE, calculation method, underlying snapshot, freshness, fallback used, confidence/quality |

Examples that remain valid natural-language input:

```text
Plan for NQ, 2026-08-31, written at 08:42 ET:
My primary scenario is a failed move below London low back to P12 mid.
No trade if the 08:30 data is incomplete or price accepts below the invalidation.
Risk 4 bps. Attached chart contains my marked levels.
```

```text
Post-day journal for ES, 2026-08-31:
I followed the morning plan on trade T-104 but widened the second stop.
The attached 5m chart was captured at 16:20 ET. My arrows are annotations,
not mechanically verified entries. Please extract proposed habit tags for review.
```

```text
External statistic: source URL/document X says P12 mid is touched 88.5% of days.
I do not know the sample window or definition. Store this as doctrine and flag
the missing statistical metadata; do not treat 88.5% as a certified probability.
```

When required context is absent, intake stores a draft without decision authority and asks only for fields that change routing or temporal meaning. It does not invent a date, instrument, source, cutoff, strategy version, or whether an observation was known before the decision.

#### B. Systematic Source-Adapter Lane

Machine-readable sources use explicit adapters rather than generic document ingestion:

```text
Broker / OHLCV / Schwab / TOS RTD / Prisma / Parquet / calendar / analysis output
        |
        v
Source-specific authentication, parsing, schema validation, and deduplication
        |
        v
Unit, ticker, contract, timezone, and as-of normalization
        |
        v
Freshness, completeness, reconciliation, and quality checks
        |
        v
Authoritative producer record + typed intake catalog reference
```

Each adapter fails closed on an unknown schema, unit, contract mapping, timestamp convention, or required field. Fallbacks are explicit lineage steps, not silent substitutions. For example, an expected move derived from a Schwab option chain and one displayed by TOS are separate observations with separate methods; disagreement is retained and surfaced rather than averaged without a certified rule.

### Canonical Intake Envelope

Every accepted item receives a small common envelope while its type-specific payload remains in the owning store:

```sql
CREATE TABLE information_items (
    information_id TEXT PRIMARY KEY,
    information_type TEXT NOT NULL,
    source_kind TEXT NOT NULL,                -- 'USER', 'BROKER', 'MARKET_DATA', 'DOCUMENT', 'MODEL', 'ANALYSIS'
    source_system TEXT NOT NULL,
    source_record_id TEXT,                    -- Stable ID in the authoritative producer
    source_uri TEXT,                          -- File/object/HTTP identifier; never treated as proof by itself
    content_hash TEXT NOT NULL,
    author_id TEXT,
    instrument_scope_json TEXT,
    session_date DATE,
    event_time_utc TIMESTAMP,
    available_at_utc TIMESTAMP NOT NULL,
    ingested_at_utc TIMESTAMP NOT NULL,
    valid_from_utc TIMESTAMP,
    valid_until_utc TIMESTAMP,
    time_orientation TEXT NOT NULL,           -- 'EX_ANTE', 'INTRADAY', 'POST_HOC', 'TIMELESS_DOCTRINE'
    evidence_class TEXT NOT NULL,             -- 'DOCTRINE', 'DECLARATION', 'MEASURED', 'DERIVED', 'CANDIDATE'
    review_state TEXT NOT NULL,
    quality_state TEXT NOT NULL,
    supersedes_information_id TEXT,
    metadata_json TEXT NOT NULL,
    FOREIGN KEY (supersedes_information_id) REFERENCES information_items(information_id),
    UNIQUE (source_system, source_record_id, content_hash)
);
```

`content_hash` protects identity, not truth. `evidence_class` expresses epistemic status, while `review_state` expresses whether a human checked an interpretation; neither substitutes for validation. Type-specific schemas remain mandatory and are selected by `(information_type, schema_version)` in `metadata_json`.

### Plans, Journals, and Images: Preventing Hindsight Leakage

Plans and journals may discuss the same session but serve opposite temporal roles:

1. A **plan** is ex-ante only if its source version and `available_at_utc` precede the decision cutoff.
2. An **intraday amendment** may govern decisions after its timestamp but cannot rewrite the morning plan.
3. A **post-day or post-week journal** may evaluate the plan and executions but cannot be used as an input feature for that same historical decision.
4. A **chart image** captured after the session is post-hoc even if it displays earlier bars. Its capture time and visible range are distinct from the market timestamps shown.
5. Image annotations such as “liquidity sweep,” “bad entry,” or “should have held” remain user or model assertions until linked to deterministic definitions or confirmed by the user.
6. Backtests and model training enforce `available_at_utc <= decision_cutoff_utc` across every joined information item.

### Dynamic Values: Snapshot, TTL, and Lineage

GEX, expected moves, IV-derived levels, live ranges, and similar values are perishable snapshots, not durable knowledge. Every dynamic observation must carry:

- The underlying chain, quote, bar, or provider snapshot identifiers.
- Calculation method and code/config version.
- Futures-to-index/ETF mapping and price-scale transform, where applicable.
- Units and price basis.
- `calculated_at_utc`, `available_at_utc`, and model-specific `valid_until_utc`.
- Market phase and session scope.
- Freshness and completeness status.
- Primary source and every fallback used.
- Reconciliation status when independent sources disagree.

Narratives and plans reference dynamic snapshot IDs. They do not copy a value without its timestamp and source. Once expired, a value remains available for audit but is excluded from new decisions. Long-term memory may store a validated method or relationship involving GEX or expected moves, never an old level as if it were current.

### Routing and Retrieval Rules

1. **Doctrine retrieval** searches books, transcripts, and playbooks and clearly cites the source. It does not search journals as authoritative trading rules by default.
2. **Decision retrieval** uses only certified model artifacts and eligible as-of observations. User plans may constrain execution only when explicitly selected as the active plan.
3. **Journal retrieval** is private, session-scoped, and distinguishes the user's words from extracted summaries.
4. **Research retrieval** may combine doctrine, observations, and confirmed journal tags to generate candidates, but its output stays in Layer 3.
5. **Visual retrieval** returns the original chart plus extraction overlays and source regions so the interpretation can be checked.
6. **Conflicting sources** are not collapsed. The response reports source, timestamp, method, and disagreement, then applies only a pre-certified precedence rule if a decision requires one value.
7. **Unknown type or provenance** is quarantined in `NEEDS_CLASSIFICATION`; it is searchable for review but excluded from evaluation and live decisions.

### Consent, Privacy, and Retention

Trade journals, behavioral notes, account identifiers, broker payloads, and screenshots may contain sensitive information. Intake therefore requires source-specific retention rules, access controls, export/delete procedures where legally and operationally permitted, and redaction before content is sent to external OCR, vision, embedding, or LLM services. Append-only evidence requirements do not justify retaining secrets or unnecessary personal data; redaction and cryptographic erasure policies must be designed before ingestion.

---

## 6. Storage Architecture: Unified Relational Database

To ensure ACID transactions, foreign key integrity, and crash consistency, the new trading-brain evidence ledgers and intake catalog are consolidated into a single database:
📍 **`data/wargaming/db/trading_brain.sqlite`**

```
c:\\Users\\vinay\\tvDownloadOHLC\\
├── data/
│   ├── knowledge/
│   │   └── unified_knowledge.lancedb          <── Layer 1: LanceDB Vector Store (4,168+ units)
│   └── wargaming/
│       ├── db/
│       │   ├── trading_brain.sqlite           <── Intake Catalog + Layer 2-4 Evidence Ledgers
│       │   │   ├── information_items           (Typed intake catalog and source references)
│       │   │   ├── forecast_snapshots         (Immutable pre-market predictions)
│       │   │   ├── signal_opportunities       (All eligible signals, taken or passed)
│       │   │   ├── signal_disposition_events  (Executed, passed, missed, or offline)
│       │   │   ├── signal_outcomes             (Versioned post-hoc policy outcomes)
│       │   │   ├── session_tape_actuals       (Mechanical tape facts with vendor provenance)
│       │   │   ├── execution_events           (Event-sourced fills, orders, stop modifications)
│       │   │   ├── behavioral_declarations    (Habit discipline and psychology logs)
│       │   │   ├── candidate_findings         (Staged hypotheses under FDR control)
│       │   │   ├── model_registry             (Versioned, certified model parameter sets)
│       │   │   └── strategies                 (Strategy definitions and risk constraints)
│       │   └── backups/                       (Automated daily snapshot backups)
│       └── reports/                           <── HTML Interactive Visual Charts
```

### Append-Only Storage, Corrections, and Operations

Immutability applies to every evidence ledger, not only forecasts. `information_items`, `forecast_snapshots`, `signal_opportunities`, `signal_disposition_events`, `signal_outcomes`, raw tape revisions, execution events, and governance attestations reject `UPDATE` and `DELETE`. Corrections are new rows linked to the record they supersede. Derived caches may be rebuilt and are not evidence ledgers.

Representative enforcement for forecasts:
```sql
-- SQLite Trigger preventing mutation of live forecast records
CREATE TRIGGER prevent_forecast_update
BEFORE UPDATE ON forecast_snapshots
BEGIN
    SELECT RAISE(FAIL, 'CRITICAL: forecast_snapshots is an immutable ledger. Updates are strictly prohibited.');
END;

CREATE TRIGGER prevent_forecast_delete
BEFORE DELETE ON forecast_snapshots
BEGIN
    SELECT RAISE(FAIL, 'CRITICAL: forecast_snapshots is an immutable ledger. Deletions are strictly prohibited.');
END;
```

The database layer additionally requires:

1. Schema migrations with a monotonically increasing `schema_version`; startup refuses unknown or partially applied versions.
2. `PRAGMA foreign_keys = ON`, WAL mode, a bounded busy timeout, and explicit transactions for multi-table writes.
3. Daily SQLite online backups plus periodic restore drills and `PRAGMA integrity_check` verification.
4. Restricted access to raw broker payloads and behavioral notes, with retention and redaction rules defined before ingestion.
5. Audit events for model activation, demotion, rollback, holdout access, and human attestation.

---

## 7. Gated Component Implementation Status

| Component | Layer | Status | Target Path / Active Path | Acceptance & Certification Manifest |
| :--- | :--- | :--- | :--- | :--- |
| **LanceDB Knowledge Library** | 1 (Knowledge) | `Available, Uncertified` | `data/knowledge/unified_knowledge.lancedb` | Producer service and indexed store exist; inventory, source-version, and retrieval-quality certification remain separate work. |
| **Candle Science Engine** | 2 (Engines) | `Implemented, Uncertified` | `scripts/candle_science/run_candle_science.py` | Calculation exists; certification requires a reproducible acceptance manifest and independent baseline verification. |
| **HTF Macro Levels Engine** | 2 (Engines) | `Implemented, Uncertified` | `scripts/wargaming/htf_macro_levels.py` | Calculation exists; provider freshness, parity, and acceptance evidence are not recorded here. |
| **Weekly Outlook Engine** | 2 (Engines) | `Implemented, Uncertified` | `scripts/wargaming/weekly_outlook_engine.py` | Calculation exists; expected-move provenance and walk-forward utility remain uncertified. |
| **P12 Scenario Engine** | 2 (Engines) | `Implemented, Uncertified` | `scripts/wargaming/p12_scenario_engine.py` | Calculation exists; published percentages are hypotheses until reproduced with versioned labels and data. |
| **Session Budget Engine** | 2 (Engines) | `Implemented, Uncertified` | `scripts/wargaming/session_budget_engine.py` | Calculation exists; threshold and regime utility remain uncertified. |
| **Signature Setup Scanner** | 2 (Engines) | `Implemented, Uncertified` | `scripts/wargaming/signature_setup_scanner.py` | Scanner exists; setup definitions and outcome validity remain uncertified. |
| **NQStats ALN Sessions** | 2 (Engines) | `Implemented, Known Gap` | `scripts/concepts/providers.py` | Live slicing exists, but missing session fields still receive synthetic spot-offset fallbacks; must fail closed before certification. |
| **Herman Probabilities** | 2 (Engines) | `Scaffold` | `scripts/concepts/providers.py` (`[SCAFFOLD]`) | Explicitly isolated; excluded from production master synthesis until mathematical engine is built. |
| **Pre-Market Wargaming Synthesizer**| 3 (Forecasts)| `Implemented, Legacy Contract` | `scripts/wargaming/generate_daily_wargame.py` | Current four-outcome output predates the five-class ontology and immutable forecast registry; migration required. |
| **Interactive Lightweight Chart UI**| 3 (Forecasts)| `Implemented, Uncertified` | `scripts/wargaming/render_wargame_chart.py` | Renderer exists; performance and forecast-contract acceptance evidence are not recorded here. |
| **Unified Trading Brain SQLite DB** | 2-4 (Ledgers) | `Target` | `data/wargaming/db/trading_brain.sqlite` | Consolidated ACID relational database with immutability triggers. |
| **Typed Intake Catalog & Router** | 1-4 (Intake) | `Target` | `scripts/trading_brain/intake/` | Common envelope, source adapters, type validation, as-of routing, review states, and provenance without duplicating authoritative stores. |
| **Human-Native Journal/Plan Intake** | 1-4 (Intake) | `Target` | `web/` + `scripts/trading_brain/intake/` | Preserves original user text/media and stages reviewable structured assertions with hindsight boundaries. |
| **Chart/Image Artifact Intake** | 1-4 (Intake) | `Partial` | `scripts/trader/chart_agent/`, `data/vision/` | Chart generation and vision exist; content-addressed originals, extraction provenance, user confirmation, privacy, and journal linkage remain target work. |
| **Dynamic Market Snapshot Adapters** | 2 (Observations) | `Partial` | `scripts/streaming/options/`, Prisma `GexSnapshot`/`MacroSnapshot` | Producers exist; common TTL, lineage, fallback, reconciliation, and intake-envelope contracts remain target work. |
| **Signal Opportunity Logger** | 2 (Ledgers) | `Target` | `scripts/wargaming/signal_logger.py` | Mechanical logger for all eligible setup opportunities (taken and passed). |
| **Evaluation & Calibration Engine** | 5 (Evaluation)| `Target` | `scripts/wargaming/evaluation_engine.py` | Multiclass Brier score, log loss, R-expectancy, and observational attribution. |
| **Walk-Forward Promotion Gate** | 6 (Promotion) | `Target` | `scripts/wargaming/promotion_gate.py` | Multi-fold rolling validator with preregistration, leakage controls, dependence-aware inference, and valid multiplicity control. |
