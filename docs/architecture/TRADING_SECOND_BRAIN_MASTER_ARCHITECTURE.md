# 🧠 Unified Trading Second Brain: Master Architecture & Design Specification

> **Document Version**: 2.0.0  
> **Status**: Approved Blueprint / Implementation Target  
> **Location**: `docs/architecture/TRADING_SECOND_BRAIN_MASTER_ARCHITECTURE.md`  
> **Scope**: End-to-End integration of Semantic Knowledge (PDFs/transcripts), Quantitative Market Engines (ALN, Candle Science, P12, Expected Moves), Pre-Market Wargaming, Personal Strategy Playbooks, Trade Journaling, Behavioral Habit Tracking, and Post-Market Diagnostic Reengineering.

---

## 1. Executive Summary & Vision

The **Trading Second Brain** is an institutional-grade, continuous learning and execution intelligence platform. It bridges the gap between **theoretical trading knowledge** (books, PDFs, video transcripts), **quantitative statistical modeling** (session dynamics, excursion percentiles, probability magnets), **pre-market scenario planning** (wargaming), **live trade execution & journaling**, and **post-market diagnostic reengineering**.

Rather than treating trading tools as disconnected scripts, the Second Brain operates as a **single, self-improving cognitive loop**:
1. **It Reads & Remembers**: Ingests your personal trading books, PDFs, and video transcripts into a semantic vector memory store.
2. **It Calculates & Plans**: Pre-calculates exact empirical levels (P12, ALN, Candle Science, Expected Moves) and models the 4-outcome decision tree before the market opens.
3. **It Logs & Correlates**: Records every trade you take (in Basis Points, MFE, MAE) and tracks your behavioral discipline (good habits vs. leaks).
4. **It Reengineers & Coaches**: Replays the session after market close, measures prediction accuracy, diagnoses trade execution against the morning plan, and updates the Brain's persistent memory with lessons learned.

---

## 2. High-Level System Topography

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
│ • 4,168+ Indexed Units       │            │ • NQStats ALN (LPEU, LPED, LEA, AEL)         │            │ • 4-Outcome Decision Tree    │
│ • PDFs (LumiTrader, ICTNotes,│            │ • Candle Science (P30, P50, P70 Boxes)       │            │   (SF, LF, LT, ST)           │
│   Flux Guide, Vinay_Models)  │            │ • P12 Gravity Well & Handshake Vector        │ ─────────> │ • 09:45 / 10:15 Cutoffs      │
│ • Video Transcripts (Mickey, │            │ • HTF Macro (Monthly Mid, NFP, Weekly EMA)   │            │ • Dynamic Target Boxes       │
│   Austin, TCM 2023-2025)     │            │ • Multi-Expiry Expected Moves (0DTE-Next Fri)│            │ • Interactive HTML Chart     │
│ • Strategy Playbooks & Rules │            │ • Session Budget (DRO Checkbook Spend %)     │            │ • `system_wargames.sqlite`   │
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
│ • User Trades (`user_trades`)│                                                                            │ • Mechanical Tape Actuals    │
│   - Entry/Exit time & price  │                                                                            │   (`market_actuals.sqlite`)  │
│   - Brackets in bps (CtQ)    │ ────────────────────────────────── Synthesizes ──────────────────────────> │ • 4-Way Confluence Check:    │
│   - MFE / MAE Excursions     │                                                                            │   Theory ↔ Plan ↔ Tape ↔ Trade│
│ • Habit Leaks (`user_habits`)│                                                                            │ • Behavioral Leak Detection  │
│   - Waited for 09:45 cutoff  │                                                                            │ • Cumulative Edge Refinement │
│   - FOMO / Moving Stop leaks │                                                                            │ • Memory Store Updates       │
└──────────────────────────────┘                                                                            └──────────────────────────────┘
```

---

## 3. Detailed Architecture: The 5 Pillars

### 📚 Pillar 1: Semantic Knowledge Base (`unified_knowledge.lancedb`)
* **Physical Location**: `data/knowledge/unified_knowledge.lancedb` (Table: `knowledge`)
* **Content Inventory**:
  * **Books & PDFs**: *LumiTrader Book, Vinay_Models, ICTNotes, Flux NY Guide, MMXM Traders Playbook*.
  * **Video Transcripts**: Complete transcribed archives of Mickey & Austin YouTube live sessions and TCM 2023–2025 series.
  * **Knowledge Units (4,168+ records)**: Categorized into `framework`, `setup`, `contextual`, `tip`, and `psychology`.
* **Access Bridge**: `scripts/knowledge_bridge/kb_context.py` via HTTP API (`http://127.0.0.1:8900`) or direct embedded LanceDB queries.
* **Function**: Injects authoritative, verbatim trade rules, setup invalidations, and psychological laws directly into pre-market planning and post-mortem reviews.

---

### ⚙️ Pillar 2: Quantitative Analytical Concept Engines (`scripts/concepts/`)
Decoupled, modular Python calculation engines implementing the `BaseConceptProvider` contract in `scripts/concepts/`:

| Concept Module | Script Path | Core Calculations & Institutional Axioms |
| :--- | :--- | :--- |
| **NQStats ALN Sessions** | `scripts/libs_py/nqstats/classifiers.py` | 4 overnight structural patterns (`LPEU`, `LPED`, `LEA`, `AEL`), `Held/Held` vs `Broken/Broken` volatility multiplier, and first-break high/low odds (>80%). |
| **Candle Science** | `scripts/candle_science/run_candle_science.py` | Empirical 3-candle sequence analysis ($C_1 \rightarrow C_2 \rightarrow C_3$) and MFE/MAE percentiles (`P30` baseline, `P50` median, `P70` reversal ceiling). |
| **P12 Scenarios & Handshakes** | `scripts/wargaming/p12_scenario_engine.py` | P12 Directional Vector ($>\text{Mid} \rightarrow \text{High } 81.7\%$), 88.5% Midline Equilibrium Gravity Well, 99.26% Goalpost sweep rule, and Agreement/Disagreement handshake vectors. |
| **HTF Macro Levels** | `scripts/wargaming/htf_macro_levels.py` | Prior Monthly Midpoint (50%), First-Friday NFP Benchmark Midpoint, and Weekly EMA(5) 52-week excursion distributions (`2%-3%` reversal magnet zones). |
| **Weekly Candle Outlook** | `scripts/wargaming/weekly_outlook_engine.py` | Day-of-Week Structural Cycle (Mon/Tue extreme formation vs Thu/Fri expansion) + Multi-Expiry Expected Move Matrix (0DTE through Next Friday). |
| **Session Budget (DRO)** | `scripts/wargaming/session_budget_engine.py` | Overnight range spending % relative to 10-day median daily range (DRO) $\rightarrow$ Classifies regime as *Coiled/Cheap (<75%)* vs *Overspent/Exhausted (>125%)*. |
| **Signature Setup Scanner** | `scripts/wargaming/signature_setup_scanner.py` | Scans for high-conviction named formations: 🧨 *Firecracker* (stacked levels), 🧽 *Spongebob* (extreme bound pin), 🥅 *Broken-Broken Goalpost*. |

---

### ⚔️ Pillar 3: Pre-Market Wargaming & Decision Synthesizer
* **Master Script**: `scripts/wargaming/render_wargame_chart.py` & `generate_daily_wargame.py`
* **Timing**: Executed between `08:45` and `09:15 EST` (after NY1 initial range forms at 08:30).
* **Core Outputs**:
  1. **4-Outcome Elimination Tree**: Models `Short False (32.8%)`, `Long False (33.3%)`, `Long True (17.2%)`, and `Short True (16.5%)` with pre-market breakout filtering.
  2. **Dynamic Target Boxes**: Exact price-time coordinates for LOD/HOD formations tailored to each outcome.
  3. **Pack Trading Brackets**: Standardized in Basis Points:
     * Minimum Risk Floor: `2 bps` | Maximum Risk Ceiling: `12-15 bps`
     * Target 1 ("Cover The Queen"): `+10 bps` (50% scale-out + Breakeven stop lock)
     * Target 2 (Runner): `+30 bps`
  4. **Interactive Lightweight Charts Report**: Self-contained HTML report with live HUD and overlays (`data/wargaming/reports/YYYY-MM-DD_NQ1_wargame.html`).
  5. **Persistence**: Forecast snapshot committed to `data/wargaming/db/system_wargames.sqlite`.

---

### 📝 Pillar 4: User Strategy Library, Trade Journaling & Habit Tracker

#### A. Strategy Playbook Registry (`docs/strategies/`)
* Standardized markdown playbooks documenting your personal setups:
  * Setup Name, Author/Domain, Trigger Conditions, Execution Rules, Timeframe, Invalidation Rules, Stop/Target rules in Basis Points.

#### B. Trade Journal Database (`data/wargaming/db/user_trade_journal.sqlite`)
* Tracks every execution taken by the user (manual entry or auto-synced from NinjaTrader/Tradovate):
```sql
CREATE TABLE user_trades (
    trade_id TEXT PRIMARY KEY,
    session_date DATE NOT NULL,
    ticker TEXT NOT NULL,
    entry_time TIMESTAMP NOT NULL,
    exit_time TIMESTAMP,
    direction TEXT NOT NULL,          -- 'LONG' / 'SHORT'
    strategy_tag TEXT NOT NULL,        -- 'ALN_LPEU', 'CANDLE_SCIENCE_P50', 'FIRECRACKER', etc.
    entry_price REAL NOT NULL,
    exit_price REAL NOT NULL,
    contracts INTEGER NOT NULL,
    stop_loss_bps REAL NOT NULL,
    target_1_bps REAL NOT NULL,
    target_2_bps REAL,
    realized_pnl_bps REAL NOT NULL,
    realized_pnl_dollars REAL,
    mfe_bps REAL,                     -- Maximum Favorable Excursion
    mae_bps REAL,                     -- Maximum Adverse Excursion
    r_multiple REAL,
    wargame_aligned BOOLEAN,          -- Was trade aligned with morning wargame scenario?
    notes TEXT,
    screenshot_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### C. Behavioral Habit & Leak Tracker (`data/wargaming/db/trader_habits.sqlite`)
* Tracks psychology, emotional state, and rule discipline:
```sql
CREATE TABLE daily_habit_scores (
    record_id TEXT PRIMARY KEY,
    session_date DATE NOT NULL,
    ticker TEXT NOT NULL,
    waited_for_0945_cutoff BOOLEAN,   -- Avoided early 09:30-09:45 opening trap
    respected_daily_loss_limit BOOLEAN,
    locked_cover_the_queen BOOLEAN,   -- Took 50% scale at +10 bps
    no_revenge_trading BOOLEAN,
    no_moved_stops BOOLEAN,           -- Never widened a stop during drawdown
    fomo_level INTEGER,               -- 1 (Calm) to 5 (Severe FOMO)
    execution_grade TEXT,             -- 'A', 'B', 'C', 'D', 'F'
    journal_reflection TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

### 🔬 Pillar 5: Post-Market Reengineering & Feedback Loop
* **Execution Time**: `16:15 EST` (after market close).
* **Master Script**: `scripts/wargaming/daily_post_mortem.py`
* **The 4-Way Confluence Diagnosis**:
  ```
  1. THEORY (What the PDF / Video rules stated)
                         ↕
  2. PLAN (What the 08:45 AM Wargame projected)
                         ↕
  3. TAPE (What the market actually printed: HOD/LOD, Day Type, Excursions)
                         ↕
  4. EXECUTION (What the user actually traded & felt)
  ```
* **Key Diagnostic Metrics Derived**:
  1. **Wargame Prediction Accuracy**: Did the day classify as the projected outcome? Did price reverse at the Candle Science P70 box? Did P12 Midline hold?
  2. **Execution Efficiency**: Comparison of User PnL vs Theoretical Max PnL from the Wargame plan.
  3. **Leak Cost Quantification**: Exact dollar/bps penalty caused by behavioral mistakes (e.g. trading before 09:45, moving stops, skipping +10 bps locks).
  4. **Memory Injection**: Writes diagnostic lessons back to the Second Brain memory store to adjust future conviction weights.

---

## 4. Storage Topography & File Organization

```
c:\Users\vinay\tvDownloadOHLC\
├── data/
│   ├── knowledge/
│   │   └── unified_knowledge.lancedb          <── LanceDB Semantic Vector Store (4,168+ units)
│   └── wargaming/
│       ├── db/
│       │   ├── system_wargames.sqlite         <── Automated Pre-Market Predictions
│       │   ├── market_actuals.sqlite          <── Mechanical 16:15 Tape Actuals
│       │   ├── mickey_ground_truth.sqlite     <── Transcript Intelligence
│       │   ├── user_trade_journal.sqlite      <── User Executed Trades
│       │   └── trader_habits.sqlite           <── Habit & Behavioral Leak Scores
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
│   ├── herman_prob/herman_probabilities_guide.md
│   └── strategies/                            <── User Personal Strategy Playbooks
│
├── scripts/
│   ├── concepts/                              <── Modular Analytical Engines
│   │   ├── base.py                            <── BaseConceptProvider Interface
│   │   ├── registry.py                        <── ConceptRegistry
│   │   ├── runner.py                          <── Universal Concept Runner CLI
│   │   └── providers.py                       <── Registered Concept Wrappers
│   ├── knowledge_bridge/                      <── LanceDB RAG Connector
│   ├── candle_science/                        <── 3-Candle Excursion Analytics
│   ├── range_probability/                     <── Range Matrix Store & Calculators
│   └── wargaming/                             <── Pre-Market Playbook & EOD Reengineering
│
└── .agent/skills/                             <── AI Agent Skills
    ├── candle_science/SKILL.md
    ├── htf_macro/SKILL.md
    ├── weekly_outlook/SKILL.md
    ├── pack_wargaming/SKILL.md
    └── sync-trading-brain/SKILL.md
```

---

## 5. Extensibility Protocol: How to Add New Modules

### Adding a New Knowledge Source (PDF, Book, or Video Series)
1. Drop the raw PDF or transcript into your ingest queue.
2. Ingest into `data/knowledge/unified_knowledge.lancedb` using the KB Bridge pipeline (`scripts/knowledge_bridge/`).
3. Add any domain-specific keyword triggers in `kb_context.py`.

### Adding a New Analytical Concept (e.g. Herman Probabilities, GEX)
1. Create the calculation engine in `scripts/<domain>/`.
2. Wrap it in `BaseConceptProvider` and register it in `scripts/concepts/providers.py`.
3. Create the reference manual in `docs/<domain>/`.
4. It will automatically participate in `python -m scripts.concepts.runner --all` and inject into the daily wargame chart.

### Adding a Personal Strategy Playbook
1. Write the playbook in `docs/strategies/<strategy_name>.md`.
2. Add its tag to `user_trade_journal.sqlite` (`strategy_tag`).
3. The post-mortem engine will automatically track your win rate, average MFE/MAE, and compliance with that strategy.
