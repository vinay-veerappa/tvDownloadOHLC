# tvDownloadOHLC Project Guidelines

## Global Rules
See `.agents/AGENTS.md` for fail-fast error handling and GPU/hardware awareness rules. These apply to all agents (Copilot, Antigravity, Claude Code).

## Core Commands
* **Start Next.js App**: `cd web && npm run dev`
* **Prisma Schema Update**: `cd web && npx prisma db push && npx prisma generate`
* **FastAPI Backend**: `start_api.bat`
* **Ollama LLM Server**: `start_llm.bat`
* **Run Options Levels**: `.\.venv\Scripts\python.exe -m scripts.streaming.options.run_options_levels`
* **Test TOS RTD Live**: `.\.venv\Scripts\python.exe -m scripts.streaming.options.tos_rtd.live_test --symbol /ES --duration 15`
* **Trader Narrative (premarket)**: `.\.venv\Scripts\python.exe -m scripts.trader.trader_narrative --mode premarket --ticker ES1`
* **Trader Narrative (open)**: `.\.venv\Scripts\python.exe -m scripts.trader.trader_narrative --mode open --ticker ES1`
* **Trader Narrative (intraday)**: `.\.venv\Scripts\python.exe -m scripts.trader.trader_narrative --mode intraday --ticker ES1`
* **Trader Narrative (close)**: `.\.venv\Scripts\python.exe -m scripts.trader.trader_narrative --mode close --ticker ES1`
* **ICT Features Pipeline (all)**: `.\.venv\Scripts\python.exe -m scripts.context.compute_ict_features`
* **ICT Features Pipeline (specific)**: `.\.venv\Scripts\python.exe -m scripts.context.compute_ict_features --symbols NQ1,ES1 --features imbalance,gaps,kz_pivots,ipda,htf_levels`
* **ICT Features Pipeline (full rebuild)**: `.\.venv\Scripts\python.exe -m scripts.context.compute_ict_features --full-regen`
* **ICT Bias Signal Generation**: `.\.venv\Scripts\python.exe -m scripts.context.generate_bias_signals --symbols NQ1 --analyze --eval-time 09:30`
* **ICT Bias Validation Analysis**: [ICT_BIAS_VALIDATION_ANALYSIS.md](file:///c:/Users/vinay/tvDownloadOHLC/docs/architecture/ICT_BIAS_VALIDATION_ANALYSIS.md) (7 ICT models negative edge, FTFC 92-99% win rate, session-adaptive bias)

## Workspace Context Anchors (Inspect ONLY when required)
* **Architectural Decisions**: [ADR.md](file:///c:/Users/vinay/tvDownloadOHLC/docs/architecture/ADR.md) (Timezones, normalization, vectorized models, prop-firm liquidation)
* **Harmonised Trading Architecture**: [HARMONISED_TRADING_ARCHITECTURE.md](file:///c:/Users/vinay/tvDownloadOHLC/docs/architecture/HARMONISED_TRADING_ARCHITECTURE.md) (3-layer pattern, strategy wrapping adapters)
* **Trading Domain Rules**: [SecondBrain_Trading.md](file:///c:/Users/vinay/tvDownloadOHLC/docs/SecondBrain_Trading.md) (ALN sessions, NQ personalities, IB probabilities)
* **Visual Compliance Standard**: [VISUAL_SYSTEM.md](file:///c:/Users/vinay/tvDownloadOHLC/docs/indicators/DailyNYLevels/VISUAL_SYSTEM.md) (Theme palette, scaling, label registry)
* **Options Infrastructure Inventory**: [OPTIONS_INVENTORY.md](file:///c:/Users/vinay/tvDownloadOHLC/docs/OPTIONS_INVENTORY.md) (Schwab auth, Greeks engine, level scorer, TOS RTD real-time feed)
* **TOS RTD Integration Plan**: [TOS_RTD_INTEGRATION_PLAN.md](file:///c:/Users/vinay/tvDownloadOHLC/docs/architecture/TOS_RTD_INTEGRATION_PLAN.md) (4-phase plan, architecture comparison)
* **Database Schema Reference**: [PRISMA_DATABASE_SCHEMA.md](file:///c:/Users/vinay/tvDownloadOHLC/docs/PRISMA_DATABASE_SCHEMA.md) (SQLite schema catalog)
* **Trader Narrative Plan**: [TRADER_NARRATIVE_PLAN.md](file:///c:/Users/vinay/tvDownloadOHLC/docs/architecture/TRADER_NARRATIVE_PLAN.md) (Session-adaptive narrative, modular signal architecture, range detection)
* **Narrative Engine Current Design**: [NARRATIVE_ENGINE_CURRENT_DESIGN.md](file:///c:/Users/vinay/tvDownloadOHLC/docs/architecture/NARRATIVE_ENGINE_CURRENT_DESIGN.md) (Canonical design + KB integration + prompt principles + known issues + goals)
* **Daily Classification**: [DAILY_CLASSIFICATION.md](file:///c:/Users/vinay/tvDownloadOHLC/docs/DailyClassification/DAILY_CLASSIFICATION.md) (R1/R2/DWP/DNP definitions, OR logic, hierarchy)
* **Herman Master Manual**: [HERMAN_MASTER_MANUAL.md](file:///c:/Users/vinay/tvDownloadOHLC/docs/Herman/HERMAN_MASTER_MANUAL.md) (Asia-London liquidity, sweep probabilities, NY fractal)
* **ICT Concepts KB**: [ICT_CONCEPTS_KB.md](file:///c:/Users/vinay/tvDownloadOHLC/docs/trading/ICT_CONCEPTS_KB.md) (Killzones, Silver Bullets, macros, PD arrays, bias models)
* **ICT Knowledge Base (RAG bridge)**: [KB_BRIDGE.md](file:///c:/Users/vinay/tvDownloadOHLC/docs/architecture/KB_BRIDGE.md) (how this repo consumes the producer `video2pdf` KB via HTTP API on port 8900; concept triggers; current KB state)
* **Knowledge Ingest Handover (canonical, DO NOT edit here)**: [HANDOVER.md](file:///c:/Users/vinay/video2pdf/knowledge_ingest/HANDOVER.md) (producer repo `video2pdf/knowledge_ingest`; read for KB state, schema, LanceDB locations, OPEX validation section 21, cross-repo data flow section 22)
* **ICT Engine Spec**: [ICT_SPEC_V1.md](file:///c:/Users/vinay/tvDownloadOHLC/docs/library/ict/ICT_SPEC_V1.md) (v1.3.0 — unified ICT detection library API reference)
* **ICT Phase 2 Plan**: [ICT_PHASE2_PLAN.md](file:///c:/Users/vinay/tvDownloadOHLC/docs/architecture/ICT_PHASE2_PLAN.md) (Phase 2 scope: OB, MSS/BOS, Judas, SMT, Delivery Triad, bias validation, PineScript)
* **ICT Daily Bias Models**: [ICT_DAILY_BIAS_MODELS.md](file:///c:/Users/vinay/tvDownloadOHLC/docs/library/ict/ICT_DAILY_BIAS_MODELS.md) (7 models implemented, 5 planned for Phase 2)
* **Quarters Theory**: [QUARTERS_THEORY.md](file:///c:/Users/vinay/tvDownloadOHLC/docs/library/QUARTERS_THEORY.md) (Overnight direction combinations, hourly candle quarter structure, Doji detection, instat extremes)
* **Profiler Knowledge Base**: [PROFILER_KNOWLEDGE_BASE.md](file:///c:/Users/vinay/tvDownloadOHLC/docs/library/PROFILER_KNOWLEDGE_BASE.md) (Session boxes, status logic, broken logic, auto-filter engine, reference levels, P12 scenarios, HOD/LOD timing, overnight combinations, data architecture)
* **RiskGuard/Copier Hardening Plan**: [RISKGUARD_COPIER_HARDENING_PLAN.md](file:///c:/Users/vinay/tvDownloadOHLC/docs/architecture/RISKGUARD_COPIER_HARDENING_PLAN.md) (31 NT8 addon defects P0→P3, defect index keyed to file:line, phase-ordered execution plan)
* **RiskGuard Hardening Progress**: [RISKGUARD_HARDENING_HANDOVER.md](file:///c:/Users/vinay/tvDownloadOHLC/docs/architecture/RISKGUARD_HARDENING_HANDOVER.md) (live state of the P0 work on branch `harden/riskguard-copier-p0`; read before touching either addon)
* **Agent Patch Loop**: [AGENT_PATCH_LOOP.md](file:///c:/Users/vinay/tvDownloadOHLC/docs/architecture/AGENT_PATCH_LOOP.md) (implement→gate→review→apply loop; gate ladder, provider shim, anti-reward-hacking guard, known-defective predecessor gates)

## Data Architecture — Two Parquet Systems

There are **two separate parquet stores** for OHLCV data:

| Store | Location | Coverage | Use case |
|---|---|---|---|
| **Live storage** | `data/live/live_storage_-{ticker}.parquet` | ~1 year (2025-01-01 → current bar) | All live/current analysis, narratives, confluence engine, GEX level reads |
| **Historical** | `data/{ticker}_1m.parquet` | 2006-2024 (deep history) | Backtesting, long-term studies, regime analysis |

* **Live storage** is written by the streaming pipeline (`stream_chart.py`) and updated in real-time. Ticker mapping: `ES1` → `live_storage_-ES.parquet`, `NQ1` → `live_storage_-NQ.parquet`.
* **Historical** is a static archive — it does NOT include current-year data.
* **`load_fused_data()`** (`scripts/utils/fused_data_loader.py`) loads both stores, dedupes, and returns the combined DataFrame. Use this when you need deep history + current data.
* **For current/live analysis** (narratives, confluence, weekly briefing): load **live storage directly** — do NOT use `DataLoader.load_price()` (which only reads historical parquet, ending 2025-12-31) or `load_fused_data()` (unnecessary overhead from loading historical).
* **`DataLoader`** (`scripts/shared/data_loader.py`) is the legacy loader that reads historical parquet only. It should NOT be used for current data — use live storage parquet or `load_fused_data()` instead.

## Development Workflow & Guardrails
* **Zero-Loop Constraint (ADR-017)**: All Python data engineering and trading strategies must use fully vectorized NumPy/Pandas models. No `for` loops in calculation paths.
* **Parallel & GPU Sweep (ADR-022)**: Parameter sweeps with ≥32 arms MUST use joblib parallel execution (`run_fvg_cisd_sweep_parallel.py` pattern). Numba `@njit` for bounded per-element loops. CuPy GPU for cumulative ops on >1M element arrays. 24 CPU cores + RTX 4060 8GB available.
* **Prop Firm RTH Liquidation (ADR-020)**: Strategies must restrict intraday positions to a maximum exit at 16:00 ET (close of 15:59 bar).
* **Unified Prop Firm Simulation (ADR-021)**: Use ONLY `scripts/trading_framework/ml/prop_firm_simulator.py` (`PropFirmSimulator`) for prop firm viability evaluation. Never feed per-trade % returns directly as daily P&L to any Monte Carlo. `prop_eval_mc.py`, `06_prop_sim.py`, and `simulate_prop_pass.py` are frozen legacy — do not extend. Firm presets (Apex, TopStep, FTMO) live in `FIRM_PROFILES`. Config overrides live in `sessions.yaml` under `prop_firm:`.
* **Visual Compliance Constraint (ADR-018)**: Indicators must bind to shared templates in `VISUAL_SYSTEM.md`. Zero direct low-level drawing API calls.
* **Timezone Standard (ADR-001)**: Charts take UTC naive inputs; calculations use ET (New York) session windows; storage uses UTC Unix Epoch.
* **Statistical Normalization Standard (ADR-002)**: Performance/statistical metrics must be calculated and reported as price percentage gains/excursions, not absolute points.
* **Strict Context Window Rule**: Never read full files unless necessary. Always utilize line-specific views (`StartLine` & `EndLine` parameters) to load only target blocks (limit to 30–50 lines per turn) to optimize token consumption.
