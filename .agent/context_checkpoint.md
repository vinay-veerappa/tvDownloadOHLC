# Context Checkpoint: Modular Wargaming, Concept Providers & Institutional Second Brain
*Timestamp: 2026-08-28T19:06:00-07:00*
*Git Commit: 38ddfe7a (pushed to origin/main)*

---

## 1. Executive Summary
Successfully modularized the Mickey & Austin Pre-Market Wargaming pipeline into 6 testable standalone engines with dedicated agent skills, eliminated the legacy `src/` directory to unify all Python packages under `scripts/`, implemented provider lifecycle states (`STATUS_PRODUCTION` vs `STATUS_SCAFFOLD`) with fail-closed live data feeds, and established the canonical **Version 4.0.0: Institutional Evidence & Decision Protocol** architecture document resolving all 25 audit findings.

---

## 2. Key Files & State

### A. Analytical Engines & Concept Providers (`scripts/`)
- [`scripts/candle_science/run_candle_science.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/candle_science/run_candle_science.py): 3-Candle sequence analysis & MFE/MAE percentiles (`P30`, `P50`, `P70`).
- [`scripts/wargaming/htf_macro_levels.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/wargaming/htf_macro_levels.py): Monthly Mid (50%), First-Friday NFP Mid, Weekly EMA(5) 52-week excursions.
- [`scripts/wargaming/weekly_outlook_engine.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/wargaming/weekly_outlook_engine.py): Day-of-Week Cycle (Mon/Tue vs Thu/Fri) + Multi-Expiry Expected Moves (0DTE $\rightarrow$ Next Friday).
- [`scripts/wargaming/p12_scenario_engine.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/wargaming/p12_scenario_engine.py): P12 Directional Vector, 88.5% Midline gravity well, 99.26% Goalposts, Handshake vectors.
- [`scripts/wargaming/session_budget_engine.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/wargaming/session_budget_engine.py): 10-day median range (DRO) vs overnight checkbook spend %.
- [`scripts/wargaming/signature_setup_scanner.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/wargaming/signature_setup_scanner.py): Firecracker, Spongebob, and Broken-Broken Goalpost detection.
- [`scripts/concepts/base.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/concepts/base.py): BaseConceptProvider interface with lifecycle states (`STATUS_PRODUCTION`, `STATUS_SCAFFOLD`, `STATUS_EXPERIMENTAL`) and failure diagnostics.
- [`scripts/concepts/registry.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/concepts/registry.py): Central registry enforcing scaffold isolation during production runs and loud error reporting.
- [`scripts/concepts/providers.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/concepts/providers.py): Real live ALN session parsing (exact ADR-004 slices, fail-closed on missing data, zero synthetic fallbacks).
- [`scripts/concepts/runner.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/concepts/runner.py): Universal CLI for independent concept runs (`--concept`) or production master synthesis (`--all`).

### B. Master Wargaming & UI Visualizer
- [`scripts/wargaming/generate_daily_wargame.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/wargaming/generate_daily_wargame.py): 4-Outcome Decision Tree, dynamic target boxes, pack brackets.
- [`scripts/wargaming/render_wargame_chart.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/wargaming/render_wargame_chart.py): Self-contained Lightweight Charts HTML report with live HUD and overlays.

### C. Architecture Documentation
- [`docs/architecture/TRADING_SECOND_BRAIN_MASTER_ARCHITECTURE.md`](file:///c:/Users/vinay/tvDownloadOHLC/docs/architecture/TRADING_SECOND_BRAIN_MASTER_ARCHITECTURE.md): Version 4.0.0 Institutional Evidence & Decision Protocol (4 Evidence Layers, Signal Opportunity Ledger, Multiclass Brier Scoring, Benjamini-Hochberg FDR Multiplicity Control, Rolling Walk-Forward Folds, 1-Time Sealed Shadow Test, Unified Relational SQLite DB with Immutability Triggers).

---

## 3. Critical Decisions & Invariants
1. **Four Strict Evidence Layers**: Knowledge/Doctrine (Hypotheses) $\ne$ Measured Tape Observations $\ne$ Pre-Registered Candidate Findings $\ne$ Promoted Production Decision Models.
2. **Zero Synthetic Fallbacks & Fail-Closed Session Logic**: No provider may substitute dummy/hardcoded levels (`spot + 20`). Missing data triggers explicit loud errors or abstention (`NO_FORECAST` / `NO_TRADE`).
3. **No Autonomous Memory Writes to Decision Rules**: Candidate lessons must be staged in `candidate_lessons`; live decision model promotion requires rolling walk-forward validation and human governance.
4. **All Python Packages Under `scripts/`**: Removed legacy `src/` directory. All core packages live in `scripts/<domain>/`.
5. **DST-Safe Time Contract (ADR-001)**: UTC storage with 'Z' suffix (`timestamp_utc`) in databases; ET (`America/New_York`) for all session windows and business logic.

---

## 4. Current Blockers & Unresolved Items
- None. All 25 audit findings have been resolved in code, tested with `pytest`, verified via CLI, and pushed to `origin/main`.

---

## 5. Next Actions
1. **Implement Unified Relational SQLite Schema (`data/wargaming/db/trading_brain.sqlite`)**:
   - Create tables: `forecast_snapshots`, `signal_opportunities`, `session_tape_actuals`, `execution_events`, `behavioral_declarations`, `candidate_findings`, `strategies`, and immutability triggers.
2. **Build Signal Opportunity Logger (`scripts/wargaming/signal_logger.py`)**:
   - Mechanically log every eligible strategy trigger (taken or passed) to enable true strategy expectancy evaluation.
3. **Build Multi-Pillar Evaluation & Post-Mortem Engine (`scripts/wargaming/evaluation_engine.py`)**:
   - Compute Multiclass Brier score, R-expectancy, execution capture efficiency, and observational habit associations.
