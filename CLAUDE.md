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
* **Seed User Profile (dry-run)**: `.\.venv\Scripts\python.exe .agent\skills\context_manager\scripts\seed_profile.py`
* **Seed User Profile (apply)**: `.\.venv\Scripts\python.exe .agent\skills\context_manager\scripts\seed_profile.py --apply --render`
* **Write a SKILL.md**: `.\.venv\Scripts\python.exe scripts\skill_writer.py --name <name> --source <draft.md>`

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
* **RiskGuard/Copier Hardening Plan**: [RISKGUARD_COPIER_HARDENING_PLAN.md](file:///c:/Users/vinay/tvDownloadOHLC/docs/architecture/RISKGUARD_COPIER_HARDENING_PLAN.md) (58 NT8 addon defects P0→P3, 45 closed; defect index keyed to file:line. Defect IDs are never renumbered or reused)
* **RiskGuard Hardening Progress**: [RISKGUARD_HARDENING_HANDOVER.md](file:///c:/Users/vinay/tvDownloadOHLC/docs/architecture/RISKGUARD_HARDENING_HANDOVER.md) (live state — **read §0 before touching either addon**, then §4a for what is pending. Deployed to shadow on `harden/riskguard-p0-51` (tip `86c6376f`, unmerged/unpushed); several fixes are **compile+unit only, not validated on a live feed**. SHAs from before session 9 are orphaned by a history rewrite — see §0.0)
* **Self-Learning Layer Design**: [SELF_LEARNING_LAYER_DESIGN.md](file:///c:/Users/vinay/tvDownloadOHLC/docs/architecture/SELF_LEARNING_LAYER_DESIGN.md) (FTS5 search, user_prefs/USER.md profile, outcomes ledger, skill-write gate — Phases 0-3 implemented)
* **NT8 Deployment**: never hand-copy `.cs` into `Documents/NinjaTrader 8/bin/Custom/`. Use `python scripts/utils/sync_nt8_strategies.py --verify --only addons` then `--only addons`, and recompile via `nt_compile`. Rules and traps: [NT8_FILE_ORGANIZATION.md](file:///c:/Users/vinay/tvDownloadOHLC/docs/architecture/NT8_FILE_ORGANIZATION.md)
* **Agent Patch Loop (ARCHIVED)**: [AGENT_PATCH_LOOP.md](file:///c:/Users/vinay/tvDownloadOHLC/docs/architecture/AGENT_PATCH_LOOP.md) (historical doc for the predecessor loop; the code is archived in `scripts/agent_loop/_archive_predecessor/`; do not run it)
* **Agent Loop v2 (current package)**: [agent-loop repo](https://github.com/vinay-veerappa/agent-loop) (language-agnostic package; **v0.2.3** is the pin in `requirements.txt` and is installed in `.venv`; 185/185 tests pass on Python 3.12 and 3.14; 9 phases + docs mode. Do **not** pin `v0.1.0` (14 commits of known defects behind) or `v0.2.0` (raises `TypeError` on Python < 3.13, which kills every ticket at region extraction))
* **Agent Loop v2 Research**: [AGENT_LOOP_RESEARCH.md](file:///c:/Users/vinay/agent-loop/docs/architecture/AGENT_LOOP_RESEARCH.md) (state of the field across 13 coding agent harnesses)
* **Agent Loop v2 Plan**: [AGENT_LOOP_V2_PLAN.md](file:///c:/Users/vinay/agent-loop/docs/architecture/AGENT_LOOP_V2_PLAN.md) (9-phase execution plan, all complete)
* **Agent Loop Decisions**: [IMPLEMENTATION_DECISIONS.md](file:///c:/Users/vinay/agent-loop/docs/architecture/IMPLEMENTATION_DECISIONS.md) (every non-obvious decision recorded)
* **Consumer Profiles**: `scripts/agent_loop_config/` (nt8-riskguard and python-tvdownloadohlc profiles; register via `--profile-module scripts.agent_loop_config`)
* **NT8 Tickets**: `scripts/agent_loop/tickets_p0.json`, `tickets_p0_51.json`, `tickets_p1_56.json` (defect definitions consumed by the new package)
* **Agent Loop Usage**:
  ```powershell
  # NT8 RiskGuard ticket (C#)
  .\.venv\Scripts\python.exe -m agent_loop --profile nt8-riskguard --profile-module scripts.agent_loop_config.nt8_riskguard --tickets scripts/agent_loop/tickets_p0.json --ticket T1

  # Python ticket
  .\.venv\Scripts\python.exe -m agent_loop --profile python-tvdownloadohlc --profile-module scripts.agent_loop_config.python_tvdownloadohlc --tickets tickets.json --ticket T1

  # Plan mode (defect -> ticket JSON)
  .\.venv\Scripts\python.exe -m agent_loop --profile python-tvdownloadohlc --profile-module scripts.agent_loop_config.python_tvdownloadohlc --mode plan --defect "description of the defect"

  # Developer mode (autonomous localization + edit)
  .\.venv\Scripts\python.exe -m agent_loop --profile python-tvdownloadohlc --profile-module scripts.agent_loop_config.python_tvdownloadohlc --mode developer --defect "description of the defect"

  # Docs mode — 4 sub-modes. changelog reads a diff; the other three read the
  # codebase (+ the graph, since both profiles set graph_project).
  .\.venv\Scripts\python.exe -m agent_loop --profile python-tvdownloadohlc --profile-module scripts.agent_loop_config.python_tvdownloadohlc --mode docs --docs-type changelog --review-base HEAD~1
  .\.venv\Scripts\python.exe -m agent_loop --profile python-tvdownloadohlc --profile-module scripts.agent_loop_config.python_tvdownloadohlc --mode docs --docs-type handover
  .\.venv\Scripts\python.exe -m agent_loop --profile python-tvdownloadohlc --profile-module scripts.agent_loop_config.python_tvdownloadohlc --mode docs --docs-type design --defect "feature to design"
  .\.venv\Scripts\python.exe -m agent_loop --profile python-tvdownloadohlc --profile-module scripts.agent_loop_config.python_tvdownloadohlc --mode docs --docs-type prd --defect "defect or feature"

  # Validate a ticket file without spending a model call. READ THE LINE RANGES:
  # a degenerate one-line region also prints OK.
  .\.venv\Scripts\python.exe -m agent_loop --profile nt8-riskguard --profile-module scripts.agent_loop_config.nt8_riskguard --tickets scripts/agent_loop/tickets_p1_56.json --list
  ```
  Docs mode does **not** yet inject the doc-architect skill's conventions into its
  system prompts (the agent-loop README describes that as intended, not done), so
  generated docs will not match this repo's house format without editing.

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

## Memory Store — `.agent/memory.db`

The canonical AI memory store, shared across all 5 agent configs (opencode, VS Code, Claude Code, Continue, Antigravity). Schema owned by `store_schema.py` (single source of truth).

| Table | Purpose | Key columns |
|---|---|---|
| `memories` | Facts, decisions, rules | `category, content, tags` |
| `memories_fts` | FTS5 index over `memories` (bm25 ranked search) | `content, tags` (synced via triggers) |
| `user_prefs` | Structured user profile | `key, value, confidence, source` |
| `outcomes` | Trade/run outcome ledger | `tag, subject, verdict, pnl_local, ticker, entry_price, exit_price` |
| `process_queue` | Staged skill proposals | `type, payload, status` |

**MCP tools** (via `nq-data-bridge`, `mcp/data_server.py`):
`add_memory` · `query_memory` (FTS5+bm25) · `link_memory_to_code` · `render_profile` · `capture_outcome` · `recap_outcomes` · `propose_skill`

**CLI scripts** (`.agent/skills/context_manager/scripts/`):
- `recall.py` — search memories (FTS5-backed, LIKE fallback)
- `remember.py` — add a memory
- `seed_profile.py` — seed `user_prefs` from curated sources (`--apply` to write, `--render` for USER.md)
- `store_schema.py` — single schema owner (all DDL + FTS5 + helpers)

**Skill writer** (`scripts/skill_writer.py`): the only CLI that persists into `.agent/skills/`. Convention, not a filesystem gate.

**Rendered profile**: `.agent/USER.md` — compiled from `user_prefs` + select memories. Consult it when user preferences, trading style, or conventions are relevant.

## Development Workflow & Guardrails
* **Parallel & GPU Sweep (ADR-022)**: Parameter sweeps with ≥32 arms MUST use joblib parallel execution (`run_fvg_cisd_sweep_parallel.py` pattern). Numba `@njit` for bounded per-element loops. CuPy GPU for cumulative ops on >1M element arrays. 24 CPU cores + RTX 4060 8GB available.
* **Prop Firm RTH Liquidation (ADR-020)**: Strategies must restrict intraday positions to a maximum exit at 16:00 ET (close of 15:59 bar).
* **Unified Prop Firm Simulation (ADR-021)**: Use ONLY `scripts/trading_framework/ml/prop_firm_simulator.py` (`PropFirmSimulator`) for prop firm viability evaluation. Never feed per-trade % returns directly as daily P&L to any Monte Carlo. `prop_eval_mc.py`, `06_prop_sim.py`, and `simulate_prop_pass.py` are frozen legacy — do not extend. Firm presets (Apex, TopStep, FTMO) live in `FIRM_PROFILES`. Config overrides live in `sessions.yaml` under `prop_firm:`.
* **Visual Compliance Constraint (ADR-018)**: Indicators must bind to shared templates in `VISUAL_SYSTEM.md`. Zero direct low-level drawing API calls.
* **Timezone Standard (ADR-001)**: Charts take UTC naive inputs; calculations use ET (New York) session windows; storage uses UTC Unix Epoch.
* **Statistical Normalization Standard (ADR-002)**: Performance/statistical metrics must be calculated and reported as price percentage gains/excursions, not absolute points.
* **Strict Context Window Rule**: Never read full files unless necessary. Always utilize line-specific views (`StartLine` & `EndLine` parameters) to load only target blocks (limit to 30–50 lines per turn) to optimize token consumption.
