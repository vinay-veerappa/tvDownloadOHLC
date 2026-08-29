# 🧠 Unified Trading Second Brain: Master Architecture & Design Specification

> **Document Version**: 2.1.0  
> **Status**: Canonical Architecture Blueprint & System Specification  
> **Location**: `docs/architecture/TRADING_SECOND_BRAIN_MASTER_ARCHITECTURE.md`  
> **Compliance**: Conforms strictly to ADR-001 (DST-safe UTC/ET Time Contract), ADR-004 (Institutional Windows), ADR-008 (Vectorized Performance), and `SELF_LEARNING_LAYER_DESIGN.md` (Human Approval Gate & Staging Queue).

---

## 1. Executive Summary & Vision

The **Trading Second Brain** is an institutional-grade, continuous learning and execution intelligence platform. It bridges the gap between **theoretical trading knowledge** (books, PDFs, video transcripts), **quantitative statistical modeling** (session dynamics, excursion percentiles, probability magnets), **pre-market scenario planning** (wargaming), **live trade execution & journaling**, and **post-market diagnostic reengineering**.

Rather than treating trading tools as disconnected scripts, the Second Brain operates as a **controlled, self-improving cognitive loop** governed by strict safety, provenance, and human consent boundaries:
1. **Reads & Semantic Memory**: Ingests your personal trading books, PDFs, and video transcripts via the LanceDB knowledge service into a semantic vector memory store.
2. **Calculates & Plans**: Pre-calculates exact empirical levels (P12, ALN, Candle Science, Expected Moves) and models the 4-outcome decision tree before market open using real market data.
3. **Logs & Correlates**: Records every execution and aggregate round-trip trade (in Basis Points, MFE, MAE) and tracks behavioral discipline (good habits vs. leaks).
4. **Reengineers & Proposes**: Replays the session after market close, measures prediction accuracy, diagnoses trade execution against the specific immutable morning prediction, and stages candidate lessons for human review.

---

## 2. Component Readiness & Implementation Status Matrix

To prevent conflation between operational capabilities and target designs, the table below defines the exact implementation status, file paths, and acceptance criteria for every module in the architecture:

| Component / Subsystem | Pillar | Status | File Path | Acceptance Criteria & Verification |
| :--- | :--- | :--- | :--- | :--- |
| **LanceDB Knowledge Base** | 1 (Knowledge) | `Implemented` | `data/knowledge/unified_knowledge.lancedb` | 4,168+ units indexed; queries served via `knowledge_ingest` on `http://127.0.0.1:8900`. |
| **Knowledge Bridge Connector** | 1 (Knowledge) | `Implemented` | `scripts/knowledge_bridge/kb_context.py` | HTTP client querying port 8900; gracefully degrades to empty context when server is offline. |
| **NQStats ALN Sessions** | 2 (Engines) | `Implemented` | `scripts/concepts/providers.py` (`ALNSessionsProvider`) | Live dynamic classification (`LPEU`, `LPED`, `LEA`, `AEL`) from fused 1m data + `SessionBoxEngine`. |
| **Candle Science Engine** | 2 (Engines) | `Implemented` | `scripts/candle_science/run_candle_science.py` | Empirical 3-candle sequence analysis ($C_1 \rightarrow C_2 \rightarrow C_3$) and MFE/MAE percentiles (`P30`, `P50`, `P70`). |
| **HTF Macro Levels Engine** | 2 (Engines) | `Implemented` | `scripts/wargaming/htf_macro_levels.py` | Monthly Mid (50%), First-Friday NFP Mid, Weekly EMA(5) 52-week excursion percentiles. |
| **Weekly Outlook Engine** | 2 (Engines) | `Implemented` | `scripts/wargaming/weekly_outlook_engine.py` | Mon/Tue extreme vs. Thu/Fri expansion cycle + Multi-Expiry Expected Moves (0DTE $\rightarrow$ Next Friday). |
| **P12 Scenario Engine** | 2 (Engines) | `Implemented` | `scripts/wargaming/p12_scenario_engine.py` | P12 Directional Vector, 88.5% Midline gravity, 99.26% Goalposts, Handshake vectors. |
| **Session Budget Engine** | 2 (Engines) | `Implemented` | `scripts/wargaming/session_budget_engine.py` | 10-day median range (DRO baseline) vs. overnight checkbook spend %. |
| **Signature Setup Scanner** | 2 (Engines) | `Implemented` | `scripts/wargaming/signature_setup_scanner.py` | Scans for Firecracker, Spongebob, and Broken-Broken Goalpost formations. |
| **Herman Probabilities** | 2 (Engines) | `Scaffold` | `scripts/concepts/providers.py` (`HermanProbabilitiesProvider`) | Labeled `STATUS_SCAFFOLD`; excluded from production `--all` until mathematical engine is built. |
| **Concept Registry & CLI** | 2 (Engines) | `Implemented` | `scripts/concepts/registry.py`, `runner.py` | Strict production vs. scaffold segregation; explicit failure surfacing on errors. |
| **Pre-Market Wargaming Synthesizer**| 3 (Wargaming) | `Implemented` | `scripts/wargaming/generate_daily_wargame.py` | Models 4-Outcome Decision Tree (`SF`, `LF`, `LT`, `ST`), dynamic target boxes, and pack brackets. |
| **Interactive Lightweight Chart** | 3 (Wargaming) | `Implemented` | `scripts/wargaming/render_wargame_chart.py` | Self-contained HTML with 60 FPS dual-axis sync loop and live HUD. |
| **3-Bank Wargame SQLite DBs** | 3 (Wargaming) | `Implemented` | `data/wargaming/db/{system_wargames,market_actuals,mickey_ground_truth}.sqlite` | Isolated databases managed via `scripts/wargaming/wargame_db.py`. |
| **3-Way Wargame Reconciler** | 5 (Post-Mortem)| `Implemented` | `scripts/wargaming/reconcile_wargame.py` | Reconciles System Wargame vs. Mickey Ground Truth vs. Tape Actuals; produces DPO pairs. |
| **User Trade Journal DB** | 4 (Journal) | `Planned` | `data/wargaming/db/user_trade_journal.sqlite` | 2-tier execution and round-trip lifecycle tables in UTC. |
| **Trader Habit & Leaks DB** | 4 (Journal) | `Planned` | `data/wargaming/db/trader_habits.sqlite` | Daily discipline scores and emotional state tracking in UTC. |
| **Unified 4-Way Daily Post-Mortem** | 5 (Post-Mortem)| `Planned` | `scripts/wargaming/daily_post_mortem.py` | Audits Theory (KB) $\leftrightarrow$ Plan (Wargame) $\leftrightarrow$ Tape (Actuals) $\leftrightarrow$ Execution (Trades). |
| **Staged Learning Approval Gate** | 5 (Post-Mortem)| `Planned` | `scripts/wargaming/learning_gate.py` | Staging queue for candidate lessons; requires human approval before memory promotion. |

---

## 3. High-Level System Architecture

```
                                  ┌──────────────────────────────────────────────────────────┐
                                  │               UNIFIED TRADING SECOND BRAIN               │
                                  └────────────────────────────┬─────────────────────────────┘
                                                               │
        ┌──────────────────────────────────────────────────────┼──────────────────────────────────────────────────────┐
        ▼                                                      ▼                                                      ▼
┌──────────────────────────────┐            ┌──────────────────────────────────────────────┐            ┌──────────────────────────────┐
│   PILLAR 1: KNOWLEDGE BASE   │            │        PILLAR 2: QUANTITATIVE ENGINES        │            │     PILLAR 3: PRE-MARKET     │
│  (LanceDB & Semantic Memory) │            │           (`scripts/concepts/`)              │            │           WARGAMING          │
├──────────────────────────────┤            ├──────────────────────────────────────────────┤            ├──────────────────────────────┤
│ • 4,168+ Indexed Units       │            │ • NQStats ALN (LPEU, LPED, LEA, AEL) [PROD]  │            │ • 4-Outcome Decision Tree    │
│ • PDFs (LumiTrader, ICTNotes,│            │ • Candle Science (P30, P50, P70 Boxes)[PROD] │            │   (SF, LF, LT, ST)           │
│   Flux Guide, Vinay_Models)  │            │ • P12 Gravity Well & Handshake Vector [PROD] │ ─────────> │ • 09:45 / 10:15 Cutoffs      │
│ • Video Transcripts (Mickey, │            │ • HTF Macro (Monthly Mid, NFP, EMA)   [PROD] │            │ • Dynamic Target Boxes       │
│   Austin, TCM 2023-2025)     │            │ • Multi-Expiry Expected Moves         [PROD] │            │ • Interactive HTML Chart     │
│ • Strategy Playbooks & Rules │            │ • Session Budget (DRO Checkbook %)    [PROD] │            │ • `system_wargames.sqlite`   │
└──────────────┬───────────────┘            └──────────────────────┬───────────────────────┘            └──────────────┬───────────────┘
               │                                                   │                                                   │
               └───────────────────────────────────────────────────┼───────────────────────────────────────────────────┘
                                                                   │
                                                                   ▼
        ┌──────────────────────────────────────────────────────────┴──────────────────────────────────────────────────────────┐
        ▼                                                                                                                     ▼
┌──────────────────────────────┐                                                                            ┌──────────────────────────────┐
│  PILLAR 4: TRADE JOURNALING  │                                                                            │  PILLAR 5: POST-MARKET       │
│   & HABIT TRACKER (SQLite)   │                                                                            │  REENGINEERING & FEEDBACK    │
├──────────────────────────────┤                                                                            ├──────────────────────────────┤
│ • `executions` (Fill Level)  │                                                                            │ • Mechanical Tape Actuals    │
│ • `trades` (Round-Trip Level)│                                                                            │   (`market_actuals.sqlite`)  │
│   - Stop/Target brackets(bps)│ ────────────────────────────────── Synthesizes ──────────────────────────> │ • 4-Way Confluence Check     │
│   - MFE / MAE Excursions     │                                                                            │ • Behavioral Leak Detection  │
│   - FK: `prediction_id`      │                                                                            │ • Staged Candidate Lessons   │
│ • `daily_habit_scores`       │                                                                            │ • Human Review Gate & Audit  │
└──────────────────────────────┘                                                                            └──────────────────────────────┘
```

---

## 4. Architectural Rules & Safety Constraints

### 🛡️ Rule 1: Human Consent Boundary & Staged Self-Learning
* **Strict Prohibition on Autonomous Writes**: As mandated by `SELF_LEARNING_LAYER_DESIGN.md`, no model, agent, or automated post-mortem script may autonomously write lessons directly into active production memory or modify live model conviction weights.
* **The 3-Step Staged Learning Protocol**:
  1. **Observation**: Mechanical tape facts and raw trade logs are saved as immutable records.
  2. **Candidate Generation**: The post-mortem engine analyzes discrepancies and drafts candidate lessons in a staging queue (`candidate_lessons` table).
  3. **Human Review & Promotion**: The user explicitly approves, edits, or rejects candidate lessons via a review interface or CLI command before they are promoted to active memory.

### 🛡️ Rule 2: Protection Against Self-Reinforcing Statistical Contamination
* **Decoupling of Evidence from Model Weights**: Statistical model weights and conviction matrices are versioned, immutable artifacts (`weights_v1.0.0.json`).
* **Minimum Sample Size & Holdout Validation**: A single session or short-term anomaly cannot alter conviction parameters. Weight re-calibrations require a minimum sample threshold ($N \ge 30$ verified sessions) and must pass out-of-sample walk-forward validation.
* **Provenance & Rollback**: Every calibrated parameter maintains full data lineage (exact session date range, sample count, ticker scope) and can be rolled back instantly.

### 🛡️ Rule 3: DST-Safe Time & Storage Contract
* **Persistence Convention**: All timestamps written to SQLite, Parquet, or JSON files MUST be stored in **ISO-8601 UTC with 'Z' suffix** (e.g. `2026-08-28T12:45:00Z`).
* **Business Logic & Session Windows**: All market session references, display strings, and rule cutoffs MUST use **ET (Eastern Time / `America/New_York`)** to handle Daylight Saving Time transitions automatically without hardcoding literal `EST`.

### 🛡️ Rule 4: Zero-Fabrication & Scaffold Segregation Policy
* **Production Integrity**: Master trading syntheses (`scripts.concepts.runner --all`, `generate_daily_wargame.py`) MUST execute ONLY production-grade concept providers backed by real market data.
* **Scaffold Isolation**: Any concept under development (e.g., `herman_probabilities`) MUST be explicitly declared as `STATUS_SCAFFOLD` and excluded from production runs until its mathematical engine is fully implemented and tested.
* **Loud Failures**: `ConceptRegistry.execute_all()` MUST NOT silently omit failed providers; any calculation error must produce an explicit `is_success=False` payload with full error diagnostics.

---

## 5. Detailed Pillar Specifications

### 📚 Pillar 1: Knowledge Base & Vector Memory
* **Service Owner**: `video2pdf/knowledge_ingest` (Producer repo).
* **Consumer Bridge**: `scripts/knowledge_bridge/kb_context.py`.
* **Runtime Contract**:
  * Knowledge queries are sent via HTTP POST to `http://127.0.0.1:8900/ask` and `/search`.
  * If the service is offline, the bridge logs a warning and degrades gracefully to an empty context block, ensuring zero downtime for live trading scripts.
* **Contents**: 4,168+ indexed units from books (*LumiTrader*, *Vinay_Models*, *ICTNotes*, *Flux Guide*, *MMXM*) and video transcripts (*Mickey & Austin YouTube live streams*, *TCM 2023–2025*).

---

### ⚙️ Pillar 2: Quantitative Concept Providers (`scripts/concepts/`)
All concept modules inherit from `BaseConceptProvider` ([`scripts/concepts/base.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/concepts/base.py)) and declare their lifecycle status (`STATUS_PRODUCTION` vs `STATUS_SCAFFOLD`):

```python
class BaseConceptProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str: pass

    @property
    @abstractmethod
    def description(self) -> str: pass

    @property
    def status(self) -> str: return STATUS_PRODUCTION

    @property
    def version(self) -> str: return "1.0.0"

    @property
    def is_production(self) -> bool: return self.status == STATUS_PRODUCTION

    @abstractmethod
    def compute(self, ticker="NQ1", target_date=None, cutoff_time="08:45", context=None) -> ConceptPayload: pass

    @abstractmethod
    def format_markdown(self, data: Dict[str, Any]) -> str: pass
```

---

### ⚔️ Pillar 3: Pre-Market Wargaming & Decision Tree
* **Execution Window**: `08:45 – 09:15 ET` (after the NY1 reference range forms at 08:30 ET).
* **Core Logic**:
  * Analyzes overnight structure relative to NY1 Range (`07:30–08:30 ET`).
  * Models the 4-Outcome Decision Tree: `Short False (32.8%)`, `Long False (33.3%)`, `Long True (17.2%)`, `Short True (16.5%)`.
  * Pre-market breakout filtering: Crossing NY1 High eliminates ST/SF; crossing NY1 Low eliminates LT/LF.
  * Injects outcome-specific target boxes and mode timing windows.
  * Writes the immutable forecast snapshot to `data/wargaming/db/system_wargames.sqlite` with a unique `prediction_id` (UUID).

---

### 📝 Pillar 4: 2-Tier Trade Journal & Habit Tracking Schemas

To accurately model open positions, partial fills, scale-outs (+10 bps Cover The Queen), commissions, slippage, and behavioral leaks, Pillar 4 implements a **2-tier execution/trade architecture** in `data/wargaming/db/user_trade_journal.sqlite` and `data/wargaming/db/trader_habits.sqlite`:

#### Tier 1: Executions / Fills Table (`executions`)
```sql
CREATE TABLE executions (
    execution_id TEXT PRIMARY KEY,           -- UUID
    trade_id TEXT NOT NULL,                  -- Foreign key to trades table
    session_date DATE NOT NULL,
    ticker TEXT NOT NULL,
    timestamp_utc TIMESTAMP NOT NULL,        -- ISO-8601 UTC
    action TEXT NOT NULL,                    -- 'BUY', 'SELL'
    quantity INTEGER NOT NULL,
    price REAL NOT NULL,
    commission_dollars REAL DEFAULT 0.0,
    slippage_bps REAL DEFAULT 0.0,
    order_type TEXT,                         -- 'MARKET', 'LIMIT', 'STOP'
    created_at_utc TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (trade_id) REFERENCES trades(trade_id)
);
```

#### Tier 2: Aggregate Round-Trip Trades Table (`trades`)
```sql
CREATE TABLE trades (
    trade_id TEXT PRIMARY KEY,               -- UUID
    session_date DATE NOT NULL,
    ticker TEXT NOT NULL,
    direction TEXT NOT NULL,                 -- 'LONG', 'SHORT'
    state TEXT NOT NULL,                     -- 'OPEN', 'PARTIALLY_CLOSED', 'CLOSED'
    entry_time_utc TIMESTAMP NOT NULL,       -- ISO-8601 UTC
    exit_time_utc TIMESTAMP,                 -- ISO-8601 UTC (NULL while OPEN)
    initial_quantity INTEGER NOT NULL,
    remaining_quantity INTEGER NOT NULL,
    avg_entry_price REAL NOT NULL,
    avg_exit_price REAL,                     -- NULL while OPEN
    stop_loss_bps REAL NOT NULL,             -- Basis points (e.g. 12.0)
    target_1_bps REAL NOT NULL,              -- Cover The Queen (+10.0 bps)
    target_2_bps REAL,                       -- Runner (+30.0 bps)
    realized_pnl_bps REAL,                   -- Realized PnL in Basis Points
    realized_pnl_dollars REAL,
    mfe_bps REAL,                            -- Maximum Favorable Excursion
    mae_bps REAL,                            -- Maximum Adverse Excursion
    r_multiple REAL,
    
    -- Provenance & Reproducibility Foreign Identifiers
    prediction_id TEXT NOT NULL,             -- FK to system_wargames.prediction_id
    wargame_cutoff_time TEXT NOT NULL,       -- E.g. "08:45"
    strategy_id TEXT NOT NULL,               -- FK to strategies.strategy_id
    notes TEXT,
    screenshot_path TEXT,
    created_at_utc TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (strategy_id) REFERENCES strategies(strategy_id)
);
```

#### Tier 3: Strategy Registry Table (`strategies`)
```sql
CREATE TABLE strategies (
    strategy_id TEXT PRIMARY KEY,            -- E.g. 'STRAT_ALN_LPEU_V1'
    name TEXT NOT NULL,
    version TEXT NOT NULL,                   -- E.g. '1.0.0'
    canonical_tag TEXT UNIQUE NOT NULL,      -- E.g. 'ALN_LPEU'
    rules_doc_path TEXT NOT NULL,            -- Path to markdown playbook
    min_risk_floor_bps REAL DEFAULT 2.0,
    max_risk_ceiling_bps REAL DEFAULT 15.0,
    created_at_utc TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### Tier 4: Trader Habits & Psychology Table (`daily_habit_scores`)
```sql
CREATE TABLE daily_habit_scores (
    record_id TEXT PRIMARY KEY,              -- UUID
    session_date DATE NOT NULL,
    ticker TEXT NOT NULL,
    waited_for_0945_cutoff BOOLEAN,          -- Waited for 09:45 ET before entry
    respected_daily_loss_limit BOOLEAN,
    locked_cover_the_queen BOOLEAN,          -- 50% scale at +10 bps
    no_revenge_trading BOOLEAN,
    no_moved_stops BOOLEAN,                  -- Never widened stops
    fomo_level INTEGER CHECK(fomo_level BETWEEN 1 AND 5),
    execution_grade TEXT,                    -- 'A', 'B', 'C', 'D', 'F'
    journal_reflection TEXT,
    created_at_utc TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

### 🔬 Pillar 5: Post-Market Reengineering & Diagnostic Feedback

#### Phase 1: Operational 3-Way Wargame Reconciler (`scripts/wargaming/reconcile_wargame.py`)
* **Current Operational State**: Reconciles the 3-bank database triad:
  1. `system_wargames.sqlite` (Pre-market AI prediction).
  2. `mickey_ground_truth.sqlite` (Mickey & Austin expert transcript benchmark).
  3. `market_actuals.sqlite` (16:15 ET mechanical tape facts).
* Generates Direct Policy Optimization (DPO) training pairs and directional accuracy scores.

#### Phase 2: Planned Unified 4-Way Daily Post-Mortem (`scripts/wargaming/daily_post_mortem.py`)
* **Target State**: Extends the 3-way reconciler by ingesting `user_trade_journal.sqlite` and `trader_habits.sqlite`:
  ```
  1. THEORY (What the PDF / Video rules stated)
                         ↕
  2. PLAN (What the 08:45 ET Wargame projected via prediction_id)
                         ↕
  3. TAPE (What the market actually printed: HOD/LOD, Day Type, MFE/MAE)
                         ↕
  4. EXECUTION (What the user actually traded & felt)
  ```
* **Output**: A daily diagnostic scorecard calculating:
  * **Wargame Prediction Accuracy %**
  * **Plan Adherence Score %**
  * **Quantified Dollar Cost of Behavioral Leaks** (e.g. trading before 09:45 ET).
  * **Staged Candidate Lessons** placed in `candidate_lessons` awaiting user review.

---

## 6. Storage Topography & Database Management

```
c:\Users\vinay\tvDownloadOHLC\
├── data/
│   ├── knowledge/
│   │   └── unified_knowledge.lancedb          <── LanceDB Semantic Vector Store (4,168+ units)
│   └── wargaming/
│       ├── db/
│       │   ├── system_wargames.sqlite         <── Automated Pre-Market Predictions [Implemented]
│       │   ├── market_actuals.sqlite          <── Mechanical Tape Actuals [Implemented]
│       │   ├── mickey_ground_truth.sqlite     <── Transcript Intelligence [Implemented]
│       │   ├── user_trade_journal.sqlite      <── Executions & Trades [Target]
│       │   └── trader_habits.sqlite           <── Habit & Behavioral Scores [Target]
│       └── reports/                           <── HTML Interactive Visual Charts [Implemented]
```

### 💾 Backup & Retention Policy
1. **Automated Daily Backups**: The SQLite database directory `data/wargaming/db/` is backed up daily to `data/wargaming/db/backups/YYYY-MM-DD_wargame_db.tar.gz`.
2. **Schema Migrations**: Schema updates are managed via versioned migration scripts in `scripts/wargaming/migrations/`.
3. **Integrity Checks**: Automated PRAGMA integrity checks (`PRAGMA integrity_check;`) run before and after every post-market reconciliation run.
