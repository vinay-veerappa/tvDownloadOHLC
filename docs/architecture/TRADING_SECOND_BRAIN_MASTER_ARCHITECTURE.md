# 🧠 Unified Trading Second Brain: Evidence-Controlled Learning Architecture

> **Document Version**: 3.0.0 (Evidence-Controlled Learning System)  
> **Status**: Canonical Architecture Blueprint & System Specification  
> **Location**: `docs/architecture/TRADING_SECOND_BRAIN_MASTER_ARCHITECTURE.md`  
> **Core Principle**: *The system may learn observations automatically, but it promotes decision rules only after statistical out-of-sample validation and explicit human approval.*

---

## 1. Executive Summary & Core Philosophy

The **Trading Second Brain** is an institutional-grade, **evidence-controlled learning system**. It bridges the gap between:
1. **Doctrine & Knowledge Sources** (trading books, PDFs, expert video transcripts).
2. **Deterministic Quantitative Features** (session boundaries, excursion percentiles, probability models).
3. **Immutable Pre-Market Forecasts** (unambiguous, timestamped hypothesis snapshots).
4. **Event & Execution Ledgers** (mechanical tape facts, fills, stop modifications, behavioral declarations).
5. **Mechanical Evaluation & Attribution** (scoring calibration, expectancy, execution quality, and behavioral leaks).
6. **Staged Promotion & Walk-Forward Validation** (walk-forward holdouts, benchmark comparisons, human sign-off).

---

## 2. The Four Evidence Layers (Strict Separation of Concerns)

To prevent self-reinforcing statistical contamination and confirmation bias, the system enforces a strict boundary across four distinct evidence layers:

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 THE FOUR EVIDENCE LAYERS                                         │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
  
  LAYER 1: KNOWLEDGE & DOCTRINE (Hypotheses)
  • Ingested Books, PDFs (LumiTrader, ICTNotes, Flux Guide), Transcripts (Mickey, Austin, TCM)
  • Authoritative doctrine and conceptual models. CANNOT influence live trading directly.
  • Status: Hypothesis Repository. Affect Live Trading: ❌ NO.
  
                                  │
                                  ▼
  LAYER 2: OBSERVATIONS & EVENT LEDGER (Empirical Facts)
  • Immutable Forecast Snapshots (`forecast_registry`)
  • Mechanical Tape Actuals (`market_actuals`)
  • Execution Event Ledger (`order_events`, `fills`, `stop_modifications`)
  • Behavioral Declarations (`habit_declarations`)
  • Status: Immutable Raw Observations. Affect Live Trading: ❌ NO.
  
                                  │
                                  ▼
  LAYER 3: CANDIDATE FINDINGS (Staged Statistical Discoveries)
  • Mechanically derived hypotheses segmented by regime (e.g. DRO spend, day-of-week).
  • Stored with sample size ($n$), successes ($k$), 95% Wilson confidence intervals, and effect size.
  • Quarantined from active trading models.
  • Status: Unvalidated Candidate. Affect Live Trading: ❌ NO.
  
                                  │
                                  ▼
  LAYER 4: PROMOTED DECISION MODELS (Validated Rules & Calibrated Weights)
  • Walk-forward validated models that beat unconditional baselines out-of-sample.
  • Versioned immutable parameter artifacts (`models/model_v2_1.json`).
  • Requires explicit human approval and carries instant rollback capability.
  • Status: Active Decision System. Affect Live Trading: ✅ YES.
```

---

## 3. The 6-Component Architecture

```
┌──────────────────────────────┐          ┌──────────────────────────────┐          ┌──────────────────────────────┐
│     1. KNOWLEDGE LIBRARY     │          │ 2. FEATURE & CONCEPT ENGINE  │          │     3. FORECAST REGISTRY     │
│   (LanceDB Semantic Store)   │          │    (`scripts/concepts/`)     │          │   (`forecast_registry.db`)   │
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
│ • Tape Actuals (`actuals.db`)│          │ • Brier Score & Calibration  │          │ • Staged Candidate Findings  │
│ • Fill Events & Slippage     │ ───────> │ • Strategy Expectancy in R   │ ───────> │ • Chronological Holdouts     │
│ • Stop/Target Modifications  │          │ • Execution Attribution      │          │ • Baseline Benchmark Check   │
│ • Behavioral Declarations    │          │ • Behavioral Leak Penalties  │          │ • Explicit Human Sign-Off    │
└──────────────────────────────┘          └──────────────────────────────┘          └──────────────────────────────┘
```

---

## 4. Deep Component Specifications

### 📚 1. Knowledge Library (Doctrine & Explanations)
* **Storage**: `data/knowledge/unified_knowledge.lancedb` (Table: `knowledge`).
* **Role**: Source of **hypotheses, trading concepts, and qualitative explanations**.
* **Rule**: Transcripts and books are **NOT** ground truth. They are recorded doctrines. Market tape actuals represent empirical truth.
* **Service Access**: Owned and served by `video2pdf/knowledge_ingest` on `http://127.0.0.1:8900`. Degrades gracefully to empty context when offline.

---

### ⚙️ 2. Feature & Concept Engine (`scripts/concepts/`)
* **Contract**: All quantitative modules inherit from `BaseConceptProvider` ([`scripts/concepts/base.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/concepts/base.py)).
* **Lifecycle Segregation**:
  * `STATUS_PRODUCTION`: Verified calculation engines backed by live market feeds (`candle_science`, `htf_macro`, `weekly_outlook`, `p12_scenarios`, `session_budget`, `signature_setups`, `aln_sessions`).
  * `STATUS_SCAFFOLD`: Development prototypes (`herman_probabilities`). Excluded from master production syntheses.
* **Zero-Fabrication Policy**: Providers compute from real tape data or return explicit error payloads (`is_success=False`). No fake dummy values are permitted in production runs.

---

### 🔮 3. Forecast Registry (`forecast_registry.sqlite`)
Every pre-market plan generates an **immutable forecast snapshot** before market open (`08:45–09:15 ET`). A forecast cannot be modified or re-generated post-hoc.

#### Immutable Snapshot Schema:
```sql
CREATE TABLE forecast_snapshots (
    prediction_id TEXT PRIMARY KEY,          -- UUID v4
    created_at_utc TIMESTAMP NOT NULL,       -- ISO-8601 UTC
    effective_cutoff_utc TIMESTAMP NOT NULL, -- E.g. 2026-08-28T12:45:00Z (08:45 ET)
    session_date DATE NOT NULL,
    ticker TEXT NOT NULL,
    model_version TEXT NOT NULL,             -- E.g. "wargame_v2.1.0"
    config_hash TEXT NOT NULL,               -- SHA-256 hash of active parameters
    
    -- Feature & Context Snapshot
    spot_price REAL NOT NULL,
    feature_snapshot_json TEXT NOT NULL,     -- Complete dictionary of extracted levels
    source_data_timestamps_json TEXT NOT NULL,-- Max timestamp of underlying 1m/1d data
    
    -- Unambiguous Probabilistic Forecasts
    probabilities_json TEXT NOT NULL,        -- {"SF": 0.328, "LF": 0.333, "LT": 0.172, "ST": 0.165}
    expected_excursions_json TEXT NOT NULL,  -- {"bullish_p50": 29707.0, "bearish_p50": 29267.0}
    active_setups_json TEXT NOT NULL,        -- Detected setups list
    missing_providers_json TEXT NOT NULL,    -- Explicit list of any omitted/failed providers
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

### 📑 4. Event Ledger (Tape Facts, Orders, Fills, Behavior)
Rather than a fragile single-row trade table, the system uses an **immutable event ledger**:

#### A. Mechanical Tape Actuals (`market_actuals.sqlite`)
* Captured mechanically at `16:15 ET` directly from 1m and tick tape data:
```sql
CREATE TABLE session_tape_actuals (
    actual_id TEXT PRIMARY KEY,
    session_date DATE NOT NULL UNIQUE,
    ticker TEXT NOT NULL,
    open_price REAL NOT NULL,
    high_price REAL NOT NULL,
    low_price REAL NOT NULL,
    close_price REAL NOT NULL,
    hod_timestamp_utc TIMESTAMP NOT NULL,
    lod_timestamp_utc TIMESTAMP NOT NULL,
    day_type_eod TEXT NOT NULL,              -- 'R1', 'R2', 'DNP', 'DWP'
    mfe_long_bps REAL NOT NULL,              -- Realized long excursion from open
    mfe_short_bps REAL NOT NULL,             -- Realized short excursion from open
    p12_mid_touched BOOLEAN NOT NULL,
    p12_high_touched BOOLEAN NOT NULL,
    p12_low_touched BOOLEAN NOT NULL,
    created_at_utc TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### B. Execution & Order Event Ledger (`execution_events.sqlite`)
```sql
CREATE TABLE execution_events (
    event_id TEXT PRIMARY KEY,               -- UUID
    trade_id TEXT NOT NULL,                  -- Groups fills into round-trips
    session_date DATE NOT NULL,
    ticker TEXT NOT NULL,
    timestamp_utc TIMESTAMP NOT NULL,        -- ISO-8601 UTC
    event_type TEXT NOT NULL,                -- 'ORDER_SUBMITTED', 'FILL', 'CANCEL', 'STOP_MODIFIED'
    action TEXT NOT NULL,                    -- 'BUY', 'SELL'
    quantity INTEGER NOT NULL,
    price REAL NOT NULL,
    commission_dollars REAL DEFAULT 0.0,
    slippage_bps REAL DEFAULT 0.0,
    order_role TEXT,                         -- 'ENTRY', 'SCALE_1_QUEEN', 'RUNNER', 'STOP_LOSS'
    raw_broker_payload TEXT,
    created_at_utc TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### C. Behavioral Declarations & Habit Scores (`trader_habits.sqlite`)
```sql
CREATE TABLE behavioral_declarations (
    declaration_id TEXT PRIMARY KEY,
    session_date DATE NOT NULL,
    ticker TEXT NOT NULL,
    waited_for_0945_cutoff BOOLEAN NOT NULL, -- Discipline check
    respected_daily_loss_limit BOOLEAN NOT NULL,
    locked_cover_the_queen BOOLEAN NOT NULL, -- Took 50% scale at +10 bps
    no_moved_stops BOOLEAN NOT NULL,         -- Never widened stops
    no_revenge_trading BOOLEAN NOT NULL,
    fomo_level INTEGER CHECK(fomo_level BETWEEN 1 AND 5),
    execution_grade TEXT,                    -- 'A', 'B', 'C', 'D', 'F'
    notes TEXT,
    created_at_utc TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

### 🔬 5. Evaluation Engine (Mechanical Scoring & Attribution)

Evaluation is 100% deterministic code. An LLM may summarize the output, but it **never determines the evaluation facts**:

#### The 4 Orthogonal Learning Vectors:
1. **Forecasting Calibration**:
   * **Brier Score**: $	ext{BS} = rac{1}{N} \sum_{t=1}^N (f_t - o_t)^2$
   * **Log Loss / Cross-Entropy** across the 4 outcomes (`SF`, `LF`, `LT`, `ST`).
   * **Reliability Diagrams**: Observed frequency vs. predicted probability buckets (e.g. do 80% predictions hit 80% of the time?).
2. **Strategy Expectancy**:
   * Expected Value in R-multiples after commissions and slippage ($	ext{EV}_R$).
   * Maximum Adverse Excursion (MAE) survival curves.
3. **Execution Quality**:
   * Slippage vs. benchmark price.
   * Target capture efficiency ($rac{	ext{Realized PnL}}{	ext{Theoretical MFE}}$).
4. **Behavioral Attribution**:
   * Quantified cost of rule violations (e.g., *Trading before 09:45 ET cost $-\$1,420$ over 30 sessions*).

---

### 🛡️ 6. Promotion Gate & Walk-Forward Validation

To prevent short-term noise or regime shifts from corrupting trading rules:

```
                               ┌──────────────────────────────────────────────┐
                               │       CANDIDATE DISCOVERY (In-Sample)        │
                               │           Chronological: 2022–2024           │
                               └──────────────────────┬───────────────────────┘
                                                      │
                                                      ▼
                               ┌──────────────────────────────────────────────┐
                               │       CALIBRATION & REGIME TUNING            │
                               │           Chronological: 2025                │
                               └──────────────────────┬───────────────────────┘
                                                      │
                                                      ▼
                               ┌──────────────────────────────────────────────┐
                               │       SHADOW VALIDATION (Out-of-Sample)      │
                               │           Chronological: 2026                │
                               └──────────────────────┬───────────────────────┘
                                                      │
                                                      ▼
                               ┌──────────────────────────────────────────────┐
                               │       BENCHMARK & SIGNIFICANCE TEST          │
                               │  Must beat unconditional frequency (p < .05) │
                               │  Must maintain sample size N >= 30           │
                               └──────────────────────┬───────────────────────┘
                                                      │
                                                      ▼
                               ┌──────────────────────────────────────────────┐
                               │       HUMAN APPROVAL GATE (Explicit)         │
                               │  User signs off -> Promoted to Model v2.2    │
                               └──────────────────────────────────────────────┘
```

#### Uncertainty & Provenance Stored with Every Claim:
Never store a bare percentage like `88.5%`. Every quantitative claim stores its complete metadata:
```json
{
  "level_name": "P12_MIDLINE_RETEST",
  "successes": 177,
  "observations": 200,
  "point_estimate": 0.885,
  "wilson_95_ci": [0.834, 0.922],
  "instrument": "NQ",
  "sample_window": "2023-01-01 to 2026-08-28",
  "regime_filter": "Overnight_Spend < 75%",
  "benchmark_unconditional": 0.742,
  "p_value_vs_baseline": 0.002,
  "model_version": "v2.1.0",
  "data_version": "fused_parquet_v3"
}
```

---

## 5. Storage Topography & File Conventions

```
c:\Users\vinay\tvDownloadOHLC\
├── data/
│   ├── knowledge/
│   │   └── unified_knowledge.lancedb          <── Layer 1: Knowledge & Doctrine Library (4,168+ units)
│   └── wargaming/
│       ├── db/
│       │   ├── forecast_registry.sqlite       <── Layer 2: Immutable Forecast Snapshots
│       │   ├── market_actuals.sqlite          <── Layer 2: Mechanical Tape Actuals
│       │   ├── execution_events.sqlite        <── Layer 2: Order & Fill Event Ledger
│       │   ├── trader_habits.sqlite           <── Layer 2: Behavioral Declarations
│       │   └── candidate_findings.sqlite      <── Layer 3: Staged Candidate Hypotheses
│       └── reports/                           <── HTML Interactive Visual Charts
│
├── docs/
│   ├── architecture/
│   │   ├── TRADING_SECOND_BRAIN_MASTER_ARCHITECTURE.md  <── This Master Specification
│   │   ├── ADR_modular_concept_provider_architecture.md
│   │   └── KB_BRIDGE.md
│   ├── candle_science/candle_science_master_guide.md
│   ├── htf_macro/htf_macro_levels_guide.md
│   ├── weekly_outlook/weekly_candle_and_expected_moves.md
│   ├── aln/aln_session_dynamics_guide.md
│   └── strategies/                            <── Layer 1: Strategy Playbooks
│
├── scripts/
│   ├── concepts/                              <── Layer 2: Deterministic Concept Providers
│   │   ├── base.py                            <── BaseConceptProvider & Lifecycle States
│   │   ├── registry.py                        <── ConceptRegistry & Scaffold Isolation
│   │   ├── runner.py                          <── Universal Concept Runner CLI
│   │   └── providers.py                       <── Registered Concept Engines
│   ├── knowledge_bridge/                      <── LanceDB RAG Connector
│   └── wargaming/                             <── Wargaming & Reengineering Engines
│
└── .agent/skills/                             <── AI Agent Skills
```

---

## 6. Implementation Status Matrix

| Component | Layer | Status | Target Path / Active Path |
| :--- | :--- | :--- | :--- |
| **LanceDB Knowledge Library** | 1 (Knowledge) | `Implemented` | `data/knowledge/unified_knowledge.lancedb` |
| **Concept Providers (7 Modules)** | 2 (Engines) | `Implemented` | `scripts/concepts/providers.py` |
| **Herman Probabilities** | 2 (Engines) | `Scaffold` | `scripts/concepts/providers.py` (`[SCAFFOLD]`) |
| **Pre-Market Wargaming Synthesizer**| 3 (Forecasts)| `Implemented` | `scripts/wargaming/generate_daily_wargame.py` |
| **Interactive Lightweight Chart UI**| 3 (Forecasts)| `Implemented` | `scripts/wargaming/render_wargame_chart.py` |
| **3-Way Tape Reconciler** | 5 (Evaluation)| `Implemented` | `scripts/wargaming/reconcile_wargame.py` |
| **Forecast Registry DB** | 3 (Forecasts)| `Target` | `data/wargaming/db/forecast_registry.sqlite` |
| **Execution Event Ledger DB** | 4 (Events) | `Target` | `data/wargaming/db/execution_events.sqlite` |
| **Candidate Findings Staging DB** | 5 (Evaluation)| `Target` | `data/wargaming/db/candidate_findings.sqlite` |
| **Walk-Forward Promotion Gate** | 6 (Promotion) | `Target` | `scripts/wargaming/promotion_gate.py` |
