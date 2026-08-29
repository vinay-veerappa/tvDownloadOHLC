# 🛠️ Trading Second Brain: Master Implementation Plan

> **Document Version**: 6.0.0 (Execution Progress & Remaining Backlog Contract)  
> **Last Updated**: August 29, 2026  
> **Status**: Canonical Engineering Roadmap, Implementation Status & Delivery Tracker  
> **Architecture Reference**: [`docs/architecture/TRADING_SECOND_BRAIN_MASTER_ARCHITECTURE.md`](file:///c:/Users/vinay/tvDownloadOHLC/docs/architecture/TRADING_SECOND_BRAIN_MASTER_ARCHITECTURE.md) (v4.3.0)  
> **Current Engine Health**: **45/45 Unit & Integration Tests Passing in 7.18s** (100% Green Battery)  
> **Core Operating Principle**: *Construct the verified 22-table schema and immutable plan ledger first. Implement and verify canonical producers in shadow mode. Prove legacy reconciliation with transactional outbox replay and rollback fences before live cutover. Guarantee server-enforced cutoff gates, as-of decision time contracts, and mechanical post-mortem derivation before enabling downstream evaluation or research gates.*

---

## 1. Executive Status & Phased Delivery Scorecard

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                             ENGINEERING PROGRESS & DELIVERY STATUS                               │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘

  PHASE 0: LOW-MANUAL-INPUT CAPTURE SPINE & ACID DATABASE FOUNDATION [STATUS: ✅ COMPLETE]
  ├── M0.1: Canonical SQLite Schema (22 Tables, 19 Protected Append-Only, 38 Triggers, 4 Views)      -> ✅ COMPLETED
  ├── M0.2: Immutable Plan Snapshots, Revisions & Deterministic get_plan_as_of Resolver (Prisma)    -> ✅ COMPLETED
  ├── M0.3a: Shadow Legacy Data Import & Dual-Hash Checksum Verification (Zero Fabrication)          -> ✅ COMPLETED
  ├── M0.4: Two-Phase Sealed Forecast Registrar (Asymmetric Cutoff Gate + 5-Class Probability Sums)  -> ✅ COMPLETED
  ├── M0.5: As-Of Signal Opportunity Logger (Frozen STRATEGY_REGISTRY_V0 + 4-State Dispositions)     -> ✅ COMPLETED
  ├── M0.6: Hardened NT8 Ingestion (Lossless fills via nt_fill_events + cursor resumption)           -> ✅ COMPLETED
  ├── M0.7: Measured Tape Actuals Extractor (Live 1m Parquet Resolver + 100% Day-Type Parity)        -> ✅ COMPLETED
  ├── M0.3b: Transactional Outbox Projector, Verified Rollback Fence & Canonical Writer Cutover      -> ✅ COMPLETED
  └── M0.8: Operational Verification Gate (OPERATIONALLY_ACCEPTED_CAPTURE_V1 - 6 Scenarios)         -> ✅ COMPLETED

  PHASE 1: DAILY PROCESS DELTA & POST-MORTEM ENGINE [STATUS: ✅ COMPLETE]
  ├── M1.1: 4-Way Mechanical Reconciler (daily_process_delta.py + Single-Session Proper Scores)       -> ✅ COMPLETED
  ├── M1.2: One-Page Event-First EOD Process Delta Report (Disk-persisting Markdown & JSON reports)  -> ✅ COMPLETED
  └── M1.3: Read-Only Memory Bridge (agent_memory_bridge.py — preserves .agent/memory.db boundary)   -> ✅ COMPLETED

  PHASE 2: MINUTE-SCALE FEEDBACK & BLINDED DELIBERATE PRACTICE [STATUS: 🟡 PARTIALLY COMPLETE]
  ├── M2.1: Python Post-Submission Deviation Annotator (OBSERVED_DEVIATION_ANNOTATION logging)       -> ✅ COMPLETED
  ├── M2.3: Blinded Deliberate-Practice Replay Engine (Real 1m Session Replay, Locked Commitments)   -> ✅ COMPLETED
  ├── M2.4: Recurring-Error Targeted Drill Generator (Intervention Recurrence Mining >= 3)          -> ✅ COMPLETED
  └── M2.2: Cross-Repository C# RiskGuard & MCP Plan Push Addon (nt8-riskguard + nt8-mcp-bridge)    -> ⏳ PENDING (Cross-Repo C#)

  PHASE 3: RESEARCH GATES, CALIBRATION & MULTI-TIER PROMOTION [STATUS: ✅ COMPLETE]
  ├── M3.1: Multiclass Proper-Score Loss Engine (Multiclass Brier & Log Loss vs. 3 Baselines + ECE) -> ✅ COMPLETED
  ├── M3.2: Multi-Fold Purged Walk-Forward Validator (BH FDR, BY FDR, Holm-Bonferroni FWER)         -> ✅ COMPLETED
  ├── M3.3: Preregistered Shadow Validation Gate (Mandatory Preregistration, Power >= 0.80, Lock)    -> ✅ COMPLETED
  └── M3.4: Decoupled Multi-Tier Promotion Engine (Forecast != Signal != Policy != Portfolio)        -> ✅ COMPLETED

  PHASE 4: TYPED INTAKE CATALOG & WEB WORKSPACE [STATUS: 🟡 PARTIALLY COMPLETE]
  ├── M4.1: Universal Typed Intake Catalog Router (9 Evidence Classes + As-Of Boundary Queries)      -> ✅ COMPLETED
  └── M4.2: Visual Next.js / Tailwind / Shadcn UI Wargaming, Process Delta & Practice Dashboard      -> ⏳ PENDING (Web UI)
```

---

## 2. Inventory: What Has Been Implemented

Every completed milestone includes production-grade source implementations anchored to `REPO_ROOT` and unit/integration test suites passing in `pytest`:

### Phase 0: Low-Manual-Input Capture Spine & ACID Database Foundation
1. **Milestone 0.1: Canonical Relational Schema & Immutability Triggers**
   - **Implemented Files**: [`scripts/trading_brain/db/schema.sql`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/trading_brain/db/schema.sql), [`scripts/trading_brain/db/connection.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/trading_brain/db/connection.py), [`scripts/trading_brain/db/init_db.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/trading_brain/db/init_db.py).
   - **Delivered Capabilities**: 22 tables (19 protected append-only tables, 3 operational state tables, 38 immutability triggers, 4 deterministic views). Enforces WAL journal mode, busy timeouts (60s), foreign key constraints, and monotonic timestamps.
   - **Verification**: [`tests/test_trading_brain_db.py`](file:///c:/Users/vinay/tvDownloadOHLC/tests/test_trading_brain_db.py) (4 tests passing).

2. **Milestone 0.2: Immutable Pre-Market Plan Snapshots & Authority Resolver**
   - **Implemented Files**: [`scripts/trading_brain/plans/plan_adapter.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/trading_brain/plans/plan_adapter.py).
   - **Delivered Capabilities**: Calendar-derived cutoff gate (08:45:00 ET $\rightarrow$ UTC), monotonic revision sequencing (`UNIQUE(session_date, ticker, revision_seq)`), intraday plan amendments, and deterministic `get_plan_as_of` query authority.
   - **Verification**: [`tests/test_plan_adapter.py`](file:///c:/Users/vinay/tvDownloadOHLC/tests/test_plan_adapter.py) (4 tests passing).

3. **Milestone 0.3a: Zero-Fabrication Shadow Legacy Importer**
   - **Implemented Files**: [`scripts/trading_brain/migrations/import_legacy_shadow.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/trading_brain/migrations/import_legacy_shadow.py).
   - **Delivered Capabilities**: Imports 100% of historical wargames with `abstain_flag = 1` and `prob_* = NULL` (`LEGACY_PREDICTION_NO_PROBABILITIES`), converts cutoffs via DST-aware calendar, and performs real read-back dual-hash checksum verification.
   - **Verification**: [`tests/test_import_legacy_shadow.py`](file:///c:/Users/vinay/tvDownloadOHLC/tests/test_import_legacy_shadow.py) (1 test passing).

4. **Milestone 0.3b: Transactional Outbox Projector & Rollback Router**
   - **Implemented Files**: [`scripts/trading_brain/migrations/outbox_projector.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/trading_brain/migrations/outbox_projector.py).
   - **Delivered Capabilities**: Asynchronous outbox projection with lease tokens, dead-letter retry queues, and `WARGAME_DB_TARGET=PAUSED` router to fence writes during maintenance.
   - **Verification**: [`tests/test_outbox_projector.py`](file:///c:/Users/vinay/tvDownloadOHLC/tests/test_outbox_projector.py) (2 tests passing).

5. **Milestone 0.4: Two-Phase Sealed Forecast Registrar**
   - **Implemented Files**: [`scripts/trading_brain/forecast/forecast_registrar.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/trading_brain/forecast/forecast_registrar.py), [`scripts/utils/market_calendar.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/utils/market_calendar.py).
   - **Delivered Capabilities**: Phase 1 input manifest sealing (`forecast_run_inputs`), Phase 2 commitment with asymmetric cutoff gate (pre-cutoff $\rightarrow$ `LIVE_PRODUCTION`, within-grace $\rightarrow$ `FORECAST_LATE_RECEIVED`, post-grace $\rightarrow$ rejected), and 5-class MECE probability sum validation ($1.0 \pm 10^{-4}$).
   - **Verification**: [`tests/test_forecast_registrar.py`](file:///c:/Users/vinay/tvDownloadOHLC/tests/test_forecast_registrar.py) (3 tests passing).

6. **Milestone 0.5: As-Of Signal Opportunity Logger & Strategy Registry V0**
   - **Implemented Files**: [`scripts/trading_brain/signals/opportunity_logger.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/trading_brain/signals/opportunity_logger.py), [`scripts/trading_brain/strategies/registry_v0.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/trading_brain/strategies/registry_v0.py), JSON strategy artifacts (`STRAT_ALN_LPEU_V0_1.json`, `STRAT_FIRECRACKER_V0_1.json`, `STRAT_GOALPOST_BB_V0_1.json`, `STRAT_P12_MID_V0_1.json`).
   - **Delivered Capabilities**: Deduplication key on `(session_date, ticker, strategy_version_id, bar_timestamp_utc)`, forward-window mechanical disposition matching (`EXECUTED`, `PASSED`, `MISSED`, `OFFLINE`), and content-hash drift detection.
   - **Verification**: [`tests/test_opportunity_logger.py`](file:///c:/Users/vinay/tvDownloadOHLC/tests/test_opportunity_logger.py) (2 tests passing).

7. **Milestone 0.6: Hardened NT8 Broker Ingestion Adapter**
   - **Implemented Files**: [`scripts/trading_brain/ingest/nt8_broker_adapter.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/trading_brain/ingest/nt8_broker_adapter.py).
   - **Delivered Capabilities**: Lossless execution fill ingestion, persistent cursor checkpoints in `broker_ingest_state`, Eastern Time trading date derivation (`derive_session_date_from_timestamp`), RiskGuard intervention ingestion, and position drift reconciliation.
   - **Verification**: [`tests/test_nt8_broker_adapter.py`](file:///c:/Users/vinay/tvDownloadOHLC/tests/test_nt8_broker_adapter.py) (3 tests passing).

8. **Milestone 0.7: Measured Tape Actuals Extractor**
   - **Implemented Files**: [`scripts/trading_brain/tape/tape_extractor.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/trading_brain/tape/tape_extractor.py), [`scripts/utils/live_storage_resolver.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/utils/live_storage_resolver.py).
   - **Delivered Capabilities**: Resolves live 1m parquet feeds across all futures and equity tickers with mtime-aware in-memory caching. Extracts Open @ 09:30, RTH High/Low, RTH Close @ 16:00, Session Close @ 16:15, HOD/LOD timestamps, and canonical 5-class Day Type classification with **100% mathematical parity** to `precompute_daily_classification.py`. Supports `SCHEDULED_SHORT_SESSION` for 210-bar half-days.
   - **Verification**: [`tests/test_live_storage_resolver.py`](file:///c:/Users/vinay/tvDownloadOHLC/tests/test_live_storage_resolver.py) & [`tests/test_tape_extractor.py`](file:///c:/Users/vinay/tvDownloadOHLC/tests/test_tape_extractor.py) (4 tests passing).

9. **Milestone 0.8: Operational Verification Gate**
   - **Implemented Files**: [`scripts/trading_brain/testing/operational_soak_gate.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/trading_brain/testing/operational_soak_gate.py).
   - **Delivered Capabilities**: End-to-end multi-table lifecycle verification across 6 distinct operational scenarios. Certified `OPERATIONALLY_ACCEPTED_CAPTURE_V1`.
   - **Verification**: [`tests/test_operational_soak.py`](file:///c:/Users/vinay/tvDownloadOHLC/tests/test_operational_soak.py) (1 test passing).

---

### Phase 1: Daily Process Delta & Post-Mortem Engine
10. **Milestone 1.1: 4-Way Mechanical Reconciler**
    - **Implemented Files**: [`scripts/trading_brain/evaluation/daily_process_delta.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/trading_brain/evaluation/daily_process_delta.py).
    - **Delivered Capabilities**: Reconciles the 4-way institutional quadrant: (1) Pre-Market Plan, (2) Day Type Forecast, (3) Signal Opportunities & Executions, (4) Measured Tape Actuals. Computes single-session multiclass Brier score and log loss, and derives genuine risk budget compliance against `max_intended_risk_bps`.
    - **Verification**: [`tests/test_daily_process_delta.py`](file:///c:/Users/vinay/tvDownloadOHLC/tests/test_daily_process_delta.py) (1 test passing).

11. **Milestone 1.2: Event-First Daily Triage Report Generator**
    - **Implemented Files**: [`scripts/trading_brain/reports/daily_triage_report.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/trading_brain/reports/daily_triage_report.py).
    - **Delivered Capabilities**: Produces concise Markdown (< 5 min read) and JSON reports, persists reports to `data/wargaming/reports/daily_process_delta_{session_date}_{ticker}.md`, and provides programmatic resolution handlers for unmatched execution links (`v_unmatched_links_open`) and information items (`v_information_items_active`).
    - **Verification**: [`tests/test_daily_triage_report.py`](file:///c:/Users/vinay/tvDownloadOHLC/tests/test_daily_triage_report.py) (2 tests passing).

12. **Milestone 1.3: Read-Only Agent Memory Bridge**
    - **Implemented Files**: [`scripts/trading_brain/bridges/agent_memory_bridge.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/trading_brain/bridges/agent_memory_bridge.py).
    - **Delivered Capabilities**: Preserves strict architectural separation between `.agent/memory.db` and `trading_brain.sqlite` with typed read-only query interfaces for LLMs and agents.
    - **Verification**: [`tests/test_agent_memory_bridge.py`](file:///c:/Users/vinay/tvDownloadOHLC/tests/test_agent_memory_bridge.py) (1 test passing).

---

### Phase 2: Minute-Scale Feedback & Blinded Deliberate Practice
13. **Milestone 2.1: Post-Submission Deviation Annotator**
    - **Implemented Files**: [`scripts/trading_brain/guard/deviation_annotator.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/trading_brain/guard/deviation_annotator.py).
    - **Delivered Capabilities**: Consumes broker execution fills post-submission, evaluates them against `get_plan_as_of`, and logs `OBSERVED_DEVIATION_ANNOTATION` events into `intervention_events` for contrary bias or unpermitted strategy execution.
    - **Verification**: [`tests/test_deviation_annotator.py`](file:///c:/Users/vinay/tvDownloadOHLC/tests/test_deviation_annotator.py) (1 test passing).

14. **Milestone 2.3: Blinded Deliberate Practice Replay Engine**
    - **Implemented Files**: [`scripts/trading_brain/practice/drill_engine.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/trading_brain/practice/drill_engine.py).
    - **Delivered Capabilities**: Replays authentic 1m historical sessions from `live_storage_*.parquet`, masks dates and metadata up to 10:30 ET IB close, locks user commitments before outcome reveal, and grades adherence (0–100).
    - **Verification**: [`tests/test_drill_engine.py`](file:///c:/Users/vinay/tvDownloadOHLC/tests/test_drill_engine.py) (1 test passing).

15. **Milestone 2.4: Recurring-Error Targeted Practice Curriculum Generator**
    - **Implemented Files**: [`scripts/trading_brain/practice/drill_generator.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/trading_brain/practice/drill_generator.py).
    - **Delivered Capabilities**: Analyzes `intervention_events` and process delta logs to mine recurring deviation patterns ($\ge 3$ occurrences), generating tailored deliberate practice sessions.
    - **Verification**: [`tests/test_drill_generator.py`](file:///c:/Users/vinay/tvDownloadOHLC/tests/test_drill_generator.py) (1 test passing).

---

### Phase 3: Research Gates, Calibration & Multi-Tier Promotion
16. **Milestone 3.1: Multiclass Proper-Score Loss Engine**
    - **Implemented Files**: [`scripts/trading_brain/research/calibration_engine.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/trading_brain/research/calibration_engine.py).
    - **Delivered Capabilities**: Computes Multiclass Brier Score, log loss, Expected Calibration Error (ECE) across reliability bins, and Brier Skill Scores vs 3 baselines (unconditional prior, rolling 50-session frequency, incumbent champion).
    - **Verification**: [`tests/test_calibration_engine.py`](file:///c:/Users/vinay/tvDownloadOHLC/tests/test_calibration_engine.py) (2 tests passing).

17. **Milestone 3.2: Multi-Fold Purged Walk-Forward Validator**
    - **Implemented Files**: [`scripts/trading_brain/research/walk_forward_gate.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/trading_brain/research/walk_forward_gate.py).
    - **Delivered Capabilities**: Purged K-fold splits preventing lookahead leakage; multiple comparison corrections via Benjamini-Hochberg (BH) FDR, Benjamini-Yekutieli (BY) FDR, and Holm-Bonferroni FWER.
    - **Verification**: [`tests/test_walk_forward_gate.py`](file:///c:/Users/vinay/tvDownloadOHLC/tests/test_walk_forward_gate.py) (2 tests passing).

18. **Milestone 3.3: Preregistered Shadow Validation Gate**
    - **Implemented Files**: [`scripts/trading_brain/research/shadow_gate.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/trading_brain/research/shadow_gate.py).
    - **Delivered Capabilities**: Enforces mandatory discovery-time preregistration, statistical power $\ge 0.80$, sealed benchmark enforcement, and terminal-state locking (`ShadowGateLockedError`) to prevent $p$-hacking.
    - **Verification**: [`tests/test_shadow_gate.py`](file:///c:/Users/vinay/tvDownloadOHLC/tests/test_shadow_gate.py) (3 tests passing).

19. **Milestone 3.4: Decoupled 4-Tier Promotion Orchestrator**
    - **Implemented Files**: [`scripts/trading_brain/research/promotion_orchestrator.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/trading_brain/research/promotion_orchestrator.py).
    - **Delivered Capabilities**: Decoupled multi-tier promotion audits: Tier 1 (Forecast Model), Tier 2 (Signal Model), Tier 3 (Execution Policy), and Tier 4 (Portfolio Deployment).
    - **Verification**: [`tests/test_promotion_orchestrator.py`](file:///c:/Users/vinay/tvDownloadOHLC/tests/test_promotion_orchestrator.py) (2 tests passing).

---

### Phase 4: Universal Typed Intake
20. **Milestone 4.1: Universal Typed Intake Catalog Router**
    - **Implemented Files**: [`scripts/trading_brain/intake/catalog_router.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/trading_brain/intake/catalog_router.py).
    - **Delivered Capabilities**: Ingests the 9 evidence classes (`DOCTRINE`, `QUANT_HYPOTHESIS`, `WARGAME_SCENARIO`, `INDICATOR_CODE`, `MACRO_REPORT`, `JOURNAL`, `CONVERSATION_INSIGHT`, `INCIDENT_RECORD`, `DISCRETIONARY_OBSERVATION`) and enforces temporal as-of boundary queries (`available_at_utc <= decision_cutoff_utc`).
    - **Verification**: [`tests/test_catalog_router.py`](file:///c:/Users/vinay/tvDownloadOHLC/tests/test_catalog_router.py) (2 tests passing).

---

## 3. Backlog: What is Yet to be Implemented

The remaining engineering backlog consists of **4 distinct workstreams**:

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    REMAINING WORK BACKLOG                                        │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘

  WORKSTREAM 1: DAILY OPERATIONAL ORCHESTRATION PIPELINES (PYTHON CLI RUNNERS)
  ├── 1.1: Pre-Market Pipeline (scripts/trading_brain/orchestration/pre_market_pipeline.py)
  │        • Executes autonomously at 08:40 ET.
  │        • Collects provider input manifests -> computes content hashes -> calls create_forecast_run.
  │        • Commits forecast snapshot before 08:45 ET cutoff -> locks LIVE_PRODUCTION state.
  │        • Auto-snapshots pre-market trade plan into plan_snapshots via PlanAdapter.
  │
  └── 1.2: Post-Market Pipeline (scripts/trading_brain/orchestration/post_market_pipeline.py)
           • Executes autonomously at 16:15 ET.
           • Extracts ground truth tape actuals from live parquet storage (TapeMetricsExtractor).
           • Drains and ingests broker fills and interventions (NT8BrokerAdapter).
           • Derives signal dispositions (OpportunityLogger.derive_dispositions).
           • Executes 4-way mechanical reconciliation quadrant (DailyProcessDeltaReconciler).
           • Persists markdown & JSON daily triage reports to data/wargaming/reports/.
           • Emits terminal alert if open unmatched links require review.

  WORKSTREAM 2: LIVE FEATURE WIRING & LEGACY SCRIPT INTEGRATION
  ├── 2.1: Wargame Generator Integration
  │        • Wire scripts/wargaming/generate_daily_wargame.py to register its generated scenario plan
  │          and 5-class day-type predictions directly via ForecastRegistrar and PlanAdapter.
  └── 2.2: Prisma TradePlan Sync
           • Wire Next.js Prisma TradePlan submissions to automatically mirror into plan_snapshots
             via PlanAdapter.snapshot_prisma_plan().

  WORKSTREAM 3: [ON HOLD - DEFERRED] C# RISKGUARD PRE-TRADE ORDER INTERCEPTOR
  ├── Status: ON HOLD / DEFERRED by user directive.
  ├── Rationale:
  │   1. Multi-Platform Execution: Orders are placed across TradingView, Tradovate, and NT8.
  │      A pre-trade interceptor in NT8 cannot intercept orders submitted via TradingView/Tradovate.
  │   2. Latency Penalty in NQ/MNQ: Synchronous 5s modal prompts cause unacceptable slippage.
  │   3. Strategy Specificity: Risk and brackets depend heavily on the specific strategy context.
  └── Future Direction: Post-fill asynchronous deviation classification via DeviationAnnotator
      and non-blocking notifications (Discord/Desktop alerts) when revived.

  WORKSTREAM 4: MILESTONE 4.2 WEB DASHBOARD UI INTEGRATION (web/)
  ├── 4.1: Pre-Market Wargame Studio (Next.js / Tailwind / Shadcn)
  │        • Interactive scenario builder and two-phase sealed forecast submission card.
  ├── 4.2: Daily Process Delta Scorecard
  │        • Real-time visual 4-way reconciliation quadrant, execution ledger, and Brier score badge.
  ├── 4.3: Deliberate Practice Terminal
  │        • Blinded simulation interface with commit-before-reveal lock-in and adherence grading.
  ├── 4.4: Model Governance & Calibration Tab
  │        • Reliability diagrams (ECE), walk-forward fold matrix, and promotion audit trail.
  └── 4.5: Interactive Review Queue Modal
           • One-click triage for unmatched links (v_unmatched_links_open) and information catalog items.
```

---

## 4. Prioritized Execution Sequence

| Priority | Task ID | Description | Target Path | Prerequisite |
|:---:|:---:|---|---|:---:|
| **P1** | **WS-1.1** | Pre-Market Pipeline Runner (08:40 ET automated forecast & plan sealing) | `scripts/trading_brain/orchestration/pre_market_pipeline.py` | Phase 0 & 1 Complete (Done) |
| **P1** | **WS-1.2** | Post-Market Pipeline Runner (16:15 ET automated tape, fills, reconciliation, triage report) | `scripts/trading_brain/orchestration/post_market_pipeline.py` | Phase 0 & 1 Complete (Done) |
| **P2** | **WS-2.1** | Wire `generate_daily_wargame.py` to auto-register forecasts & plans | `scripts/wargaming/generate_daily_wargame.py` | WS-1.1 |
| **P2** | **WS-2.2** | Wire Prisma TradePlan web submissions to `PlanAdapter` | `web/src/` & `scripts/trading_brain/plans/plan_adapter.py` | WS-1.1 |
| **P3** | **WS-4** | Interactive Next.js / Tailwind Web Workspace & Review Queues | `web/` | WS-1.2 |
| **HOLD**| **WS-3** | [ON HOLD] C# RiskGuard Pre-Trade Interceptor | `nt8-riskguard`, `nt8-mcp-bridge` | Deferred |

---

## 5. Verification & Acceptance Battery Reference

To verify the entire Trading Second Brain engine in a single command:

```bash
python -m pytest \
  tests/test_trading_brain_db.py \
  tests/test_plan_adapter.py \
  tests/test_import_legacy_shadow.py \
  tests/test_market_calendar.py \
  tests/test_forecast_registrar.py \
  tests/test_opportunity_logger.py \
  tests/test_outbox_projector.py \
  tests/test_nt8_broker_adapter.py \
  tests/test_live_storage_resolver.py \
  tests/test_tape_extractor.py \
  tests/test_operational_soak.py \
  tests/test_daily_process_delta.py \
  tests/test_daily_triage_report.py \
  tests/test_agent_memory_bridge.py \
  tests/test_deviation_annotator.py \
  tests/test_drill_engine.py \
  tests/test_drill_generator.py \
  tests/test_calibration_engine.py \
  tests/test_walk_forward_gate.py \
  tests/test_shadow_gate.py \
  tests/test_promotion_orchestrator.py \
  tests/test_catalog_router.py -v
```

*Expected Result*: **45 passed in ~7s** (100% passing).
