# 🧠 Unified Trading Second Brain: Institutional Evidence & Decision Protocol

> **Document Version**: 4.0.0 (Institutional Evidence & Decision Protocol)  
> **Status**: Canonical Architecture Blueprint & System Specification  
> **Location**: `docs/architecture/TRADING_SECOND_BRAIN_MASTER_ARCHITECTURE.md`  
> **Core Axiom**: *The system automates fact collection, measurement, and hypothesis discovery, but NEVER autonomously promotes hypotheses into live decision rules. Live models require registered hypotheses, multiplicity-controlled out-of-sample validation across multiple historical regimes, and explicit human governance.*

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
  • Constraint: Append-only immutable facts. CANNOT alter live trading weights autonomously.
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
│ • Transcripts & Playbooks    │ ───────> │ • Candle Science Excursions  │ ───────> │ • Hash, Timestamps, Models   │
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

---

## 4. Rigorous Deep-Dive Specifications

### 🎯 1. Outcome Ontology & MECE Label Functions
To prevent conflating distinct prediction tasks, the system establishes **Mutually Exclusive, Collectively Exhaustive (MECE) versioned label functions**:

#### A. The 4-Outcome Day-Type Task (`LABEL_DAY_TYPE_V1`)
* **Task Scope**: Predicts the primary directional archetype of the RTH session relative to NY1 Initial Range (`07:30–08:30 ET`).
* **Classes**:
  1. `SF` (Short False): Sweeps below NY1 Low before 10:15 ET $\rightarrow$ Reverses to close above NY1 Mid.
  2. `LF` (Long False): Sweeps above NY1 High before 10:15 ET $\rightarrow$ Reverses to close below NY1 Mid.
  3. `LT` (Long True): Defends NY1 Mid/Low $\rightarrow$ Expands to print HOD after 14:30 ET.
  4. `ST` (Short True): Rejects NY1 Mid/High $\rightarrow$ Expands to print LOD after 14:30 ET.
* **Censoring / Unclassified Policy**: If neither boundary is broken by 16:00 ET, classified as `ROTATIONAL_CHOP` (explicit non-event class).

#### B. The EOD Diagnostic Classification Task (`LABEL_EOD_CLASSIFICATION_V1`)
* **Task Scope**: Evaluates post-market 16:15 ET structure against historical 4,300-session distributions.
* **Classes**: `R1` (Rotational 1-Side), `R2` (Rotational 2-Side Expansion), `DNP` (Directional No Pullback), `DWP` (Directional With Pullback).

#### C. Target Box & Excursion Events
* `P30_HIT`, `P50_HIT`, `P70_HIT`, `P70_REVERSED`, `P12_MID_TOUCHED`. Evaluated strictly from tick / 1m high-low bounds.

---

### 📡 2. Signal Opportunity Ledger (`signal_opportunities`)
To decouple **strategy expectancy** from **discretionary trader selection**, the system mechanically logs every eligible signal:

```sql
CREATE TABLE signal_opportunities (
    opportunity_id TEXT PRIMARY KEY,          -- UUID v4
    session_date DATE NOT NULL,
    ticker TEXT NOT NULL,
    timestamp_utc TIMESTAMP NOT NULL,        -- Exact bar timestamp when signal became active
    strategy_id TEXT NOT NULL,               -- E.g. 'STRAT_ALN_LPEU_V1'
    model_version TEXT NOT NULL,
    direction TEXT NOT NULL,                 -- 'LONG', 'SHORT'
    trigger_price REAL NOT NULL,
    proposed_stop_bps REAL NOT NULL,
    proposed_target_1_bps REAL NOT NULL,     -- Cover The Queen (+10 bps)
    proposed_target_2_bps REAL,              -- Runner (+30 bps)
    
    -- Execution State
    was_executed BOOLEAN NOT NULL,           -- TRUE if user/bot entered trade, FALSE if passed/missed
    pass_reason TEXT,                        -- 'DISCRETIONARY_FILTER', 'MAX_RISK_REACHED', 'MISSED', 'OFFLINE'
    
    -- Theoretical Mechanical Outcome
    theoretical_mfe_bps REAL,                -- Realized MFE from signal price to EOD
    theoretical_mae_bps REAL,                -- Realized MAE from signal price to EOD
    theoretical_result TEXT,                 -- 'TP1_HIT', 'TP2_HIT', 'STOPPED_OUT', 'SCRATCH'
    created_at_utc TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (strategy_id) REFERENCES strategies(strategy_id)
);
```

---

### 🔮 3. Forecast Registry & Full Provenance (`forecast_snapshots`)
Every pre-market plan generates an **immutable forecast snapshot** before market open (`08:45–09:15 ET`):

```sql
CREATE TABLE forecast_snapshots (
    prediction_id TEXT PRIMARY KEY,          -- UUID v4
    session_date DATE NOT NULL,
    ticker TEXT NOT NULL,
    created_at_utc TIMESTAMP NOT NULL,       -- ISO-8601 UTC
    effective_cutoff_utc TIMESTAMP NOT NULL, -- E.g. 2026-08-28T12:45:00Z (08:45 ET)
    forecast_mode TEXT NOT NULL,             -- 'LIVE_PRODUCTION', 'REPLAY_AUDIT', 'SHADOW'
    
    -- Exact Reproducibility Manifest
    git_commit_hash TEXT NOT NULL,           -- Exact code version
    environment_hash TEXT NOT NULL,          -- Python & dependency lock hash
    config_hash TEXT NOT NULL,               -- SHA-256 of active wargame parameters
    data_manifest_hash TEXT NOT NULL,        -- SHA-256 of input Parquet / Live data
    source_data_max_timestamp_utc TIMESTAMP NOT NULL,
    
    -- Unambiguous High-Precision Forecasts
    spot_price REAL NOT NULL,
    p_short_false REAL NOT NULL,             -- Full precision floating point (e.g. 0.328491)
    p_long_false REAL NOT NULL,
    p_long_true REAL NOT NULL,
    p_short_true REAL NOT NULL,
    abstain_flag BOOLEAN DEFAULT FALSE,      -- TRUE if data quality or coverage triggers abstention
    abstain_reason TEXT,
    
    -- Snapshots
    feature_snapshot_json TEXT NOT NULL,
    active_setups_json TEXT NOT NULL,
    provider_manifest_json TEXT NOT NULL,    -- Detailed provider status, versions, freshness
    
    created_at_utc TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_forecast UNIQUE (session_date, ticker, effective_cutoff_utc, forecast_mode)
);
```

#### Replay and Reproducibility Rules:
1. **Live Forecast Immutability**: Live forecasts (`forecast_mode = 'LIVE_PRODUCTION'`) can **NEVER** be updated or deleted.
2. **Replay Audits**: Re-running a forecast creates an explicit `REPLAY_AUDIT` record with its own `prediction_id` and references the original live snapshot. Replays never overwrite live records.
3. **Deterministic Verification**: Given the recorded git commit, config hash, and data manifest hash, code must reproduce identical floating-point probabilities.

---

### 📑 4. Event Ledger & Broker State Envelope (`execution_events`)
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
    parent_order_id TEXT,                    -- Bracket parent ID
    
    -- Timestamps (DST-Safe ISO-8601 UTC)
    exchange_timestamp_utc TIMESTAMP,        -- Timestamp recorded by exchange
    broker_timestamp_utc TIMESTAMP,          -- Timestamp recorded by broker API
    received_timestamp_utc TIMESTAMP NOT NULL,-- Timestamp received locally
    
    -- Order Details
    action TEXT NOT NULL,                    -- 'BUY', 'SELL'
    order_type TEXT NOT NULL,                -- 'MARKET', 'LIMIT', 'STOP_MARKET', 'STOP_LIMIT'
    quantity INTEGER NOT NULL,
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
    FOREIGN KEY (opportunity_id) REFERENCES signal_opportunities(opportunity_id)
);
```

---

### 🔬 5. Evaluation Engine (Multiclass Calibration & Attribution)

#### A. Multiclass Brier Score & Log Loss
For $K = 4$ mutually exclusive day-type outcomes over $N$ evaluated sessions:

$$\text{Brier Score} = \frac{1}{N} \sum_{t=1}^N \sum_{k=1}^4 (p_{t,k} - y_{t,k})^2$$

$$\text{Log Loss} = -\frac{1}{N} \sum_{t=1}^N \sum_{k=1}^4 y_{t,k} \ln(p_{t,k})$$

where $y_{t,k} \in \{0, 1\}$ is the one-hot indicator of the mechanically evaluated outcome, and $p_{t,k}$ is the forecast probability.

#### B. Benchmark Incremental Value Requirement
A model is evaluated against three mandatory baselines:
1. **Unconditional Historical Base-Rate**: $p_k = \bar{y}_k$ over all prior history.
2. **Recency-Weighted Frequency**: Rolling 50-session frequency.
3. **Incumbent Production Model**: Previous certified version.
*A candidate model is eligible for promotion ONLY if it achieves a statistically significant reduction in Log Loss and Brier Score over all three baselines ($p < 0.01$).*

#### C. Observational vs. Causal Behavioral Reporting
* **Prohibited**: *"Trading before 09:45 ET cost $-\$1,420$."*
* **Required**: *"Pre-09:45 ET trades were associated with $-\$1,420$ lower realized P&L ($-\Delta 18.4\text{ bps}$) across $N=24$ sessions, conditional on recorded volatility and signal filters."*
* **Counterfactual Analysis**: Causal attribution is computed strictly by replaying the session's recorded orders against a deterministic execution policy (e.g. *What would PnL be if the identical signal was entered at 09:45:01 ET instead of 09:32:15 ET?*).

---

### 🛡️ 6. Promotion Gate: Multi-Fold Walk-Forward & Multiplicity Control

To eliminate data mining, p-hacking, and regime overfitting:

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                            ROLLING WALK-FORWARD VALIDATION DESIGN                                │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘

  FOLD 1: Train [2018–2020] ──> Calibrate [2021] ──> Out-of-Sample Test [2022] (Locked)
  FOLD 2: Train [2019–2021] ──> Calibrate [2022] ──> Out-of-Sample Test [2023] (Locked)
  FOLD 3: Train [2020–2022] ──> Calibrate [2023] ──> Out-of-Sample Test [2024] (Locked)
  FOLD 4: Train [2021–2023] ──> Calibrate [2024] ──> Out-of-Sample Test [2025] (Locked)
  
  SEALED FINAL SHADOW TEST: 2026 (1-Time Access Only. Zero re-tuning permitted)
```

#### Multiplicity & Statistical Rigor Requirements:
1. **Pre-Registration**: Feature definitions, label functions, and model architectures must be frozen and committed to git **BEFORE** accessing out-of-sample folds.
2. **False Discovery Rate (FDR) Control**: When screening multiple setups or regime splits, apply the **Benjamini-Hochberg procedure** at $\alpha = 0.05$.
3. **Dependence-Aware Uncertainty**: Confidence intervals and hypothesis tests on financial time-series MUST use **Stationary Block Bootstrap** (Politis & Romano, 1994) or **Newey-West HAC standard errors** to account for serial correlation and volatility clustering.
4. **Minimum Detectable Effect (MDE) & Power**: Sample size must satisfy prospective power requirements ($\beta \ge 0.80$) for an economically meaningful effect ($\Delta \ge 5\text{ bps}$ after costs).

---

### 🚪 7. Model Governance, Retirement & Kill-Switches

Models are living systems that decay as market microstructures evolve:

```
┌──────────────────────────────┐
│  LIVE PRODUCTION MONITORING  │
│  (Rolling 30-Day Evaluation) │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐       Calibration Error > 2.0x Baseline OR
│    DRIFT & LOSS DETECTION    │ ────> Max Drawdown Exceeds 95th Percentile
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

1. **Automatic Abstention (`NO_FORECAST` / `NO_TRADE`)**: Triggered if data freshness exceeds 120 seconds, more than 1 production provider fails, or market volatility enters an un-modeled tail regime ($> 4\sigma$).
2. **Champion / Challenger Shadow Deployment**: New models must run in live shadow mode for a minimum of 20 live sessions without execution authority before promotion review.
3. **Human Sign-Off Attestation**: Human approval confirms that all pre-registered criteria, FDR corrections, and shadow tests passed. Human approval **CANNOT** waive failed statistical safety gates.

---

## 5. Storage Architecture: Unified Relational Database

To ensure ACID transactions, foreign key integrity, and crash consistency, all relational tables are consolidated into a single database:
📍 **`data/wargaming/db/trading_brain.sqlite`**

```
c:\\Users\\vinay\\tvDownloadOHLC\\
├── data/
│   ├── knowledge/
│   │   └── unified_knowledge.lancedb          <── Layer 1: LanceDB Vector Store (4,168+ units)
│   └── wargaming/
│       ├── db/
│       │   ├── trading_brain.sqlite           <── Layer 2-4: Unified ACID Relational Database
│       │   │   ├── forecast_snapshots         (Immutable pre-market predictions)
│       │   │   ├── signal_opportunities       (All eligible signals, taken or passed)
│       │   │   ├── session_tape_actuals       (Mechanical tape facts with vendor provenance)
│       │   │   ├── execution_events           (Event-sourced fills, orders, stop modifications)
│       │   │   ├── behavioral_declarations    (Habit discipline and psychology logs)
│       │   │   ├── candidate_findings         (Staged hypotheses under FDR control)
│       │   │   ├── model_registry             (Versioned, certified model parameter sets)
│       │   │   └── strategies                 (Strategy definitions and risk constraints)
│       │   └── backups/                       (Automated daily snapshot backups)
│       └── reports/                           <── HTML Interactive Visual Charts
```

### Immutable Storage Enforcement Trigger:
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

---

## 6. Gated Component Implementation Status

| Component | Layer | Status | Target Path / Active Path | Acceptance & Certification Manifest |
| :--- | :--- | :--- | :--- | :--- |
| **LanceDB Knowledge Library** | 1 (Knowledge) | `Certified` | `data/knowledge/unified_knowledge.lancedb` | 4,168+ units indexed; HTTP queries served on port 8900 with graceful offline fallback. |
| **Candle Science Engine** | 2 (Engines) | `Certified` | `scripts/candle_science/run_candle_science.py` | 4,300-session empirical baseline; verified MFE/MAE percentiles in Basis Points. |
| **HTF Macro Levels Engine** | 2 (Engines) | `Certified` | `scripts/wargaming/htf_macro_levels.py` | Monthly Mid (50%), NFP Mid, Weekly EMA(5) 52-wk excursion percentiles. |
| **Weekly Outlook Engine** | 2 (Engines) | `Certified` | `scripts/wargaming/weekly_outlook_engine.py` | Mon/Tue extreme vs Thu/Fri expansion cycle + multi-expiry Expected Moves. |
| **P12 Scenario Engine** | 2 (Engines) | `Certified` | `scripts/wargaming/p12_scenario_engine.py` | P12 Directional Vector, 88.5% Midline gravity, 99.26% Goalposts, Handshake vectors. |
| **Session Budget Engine** | 2 (Engines) | `Certified` | `scripts/wargaming/session_budget_engine.py` | 10-day median range (DRO baseline) vs overnight checkbook spend %. |
| **Signature Setup Scanner** | 2 (Engines) | `Certified` | `scripts/wargaming/signature_setup_scanner.py` | Scans Firecracker, Spongebob, and Broken-Broken Goalpost setups. |
| **NQStats ALN Sessions** | 2 (Engines) | `Certified` | `scripts/concepts/providers.py` | Exact ADR-004 session slice parsing; fail-closed on missing session data; zero synthetic fallbacks. |
| **Herman Probabilities** | 2 (Engines) | `Scaffold` | `scripts/concepts/providers.py` (`[SCAFFOLD]`) | Explicitly isolated; excluded from production master synthesis until mathematical engine is built. |
| **Pre-Market Wargaming Synthesizer**| 3 (Forecasts)| `Certified` | `scripts/wargaming/generate_daily_wargame.py` | 4-Outcome Decision Tree (`SF`, `LF`, `LT`, `ST`), dynamic target boxes, pack brackets. |
| **Interactive Lightweight Chart UI**| 3 (Forecasts)| `Certified` | `scripts/wargaming/render_wargame_chart.py` | Self-contained HTML with 60 FPS dual-axis sync loop and live HUD. |
| **Unified Trading Brain SQLite DB** | 2-4 (Ledgers) | `Target` | `data/wargaming/db/trading_brain.sqlite` | Consolidated ACID relational database with immutability triggers. |
| **Signal Opportunity Logger** | 2 (Ledgers) | `Target` | `scripts/wargaming/signal_logger.py` | Mechanical logger for all eligible setup opportunities (taken and passed). |
| **Evaluation & Calibration Engine** | 5 (Evaluation)| `Target` | `scripts/wargaming/evaluation_engine.py` | Multiclass Brier score, log loss, R-expectancy, and observational attribution. |
| **Walk-Forward Promotion Gate** | 6 (Promotion) | `Target` | `scripts/wargaming/promotion_gate.py` | Multi-fold rolling walk-forward validator with Benjamini-Hochberg FDR control. |
