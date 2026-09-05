# tvDownloadOHLC Project Guidelines

## ⚠️ STRATEGY WORK — READ THIS FIRST

**Any task that writes, runs, backtests, validates, compares, reports on, or promotes a
trading strategy is governed by [STRATEGY_WORKFLOW.md](file:///c:/Users/vinay/tvDownloadOHLC/docs/architecture/STRATEGY_WORKFLOW.md).**
Read it before starting, not after. It is the canonical procedure and supersedes, for
procedure, the deleted `NT8_PYTHON_PARITY_STANDARD.md` and
`STRATEGY_DESIGN_STANDARD.md`, whose content it absorbed (its §12 records what moved
where). The user should never have to restate any of it.

It covers, end to end: what a strategy IS (Python hunter + C# bot + parameter document),
the `hunt()` contract and the enforced signal geometry, which libraries to reuse, the one
sanctioned entry point and its required flags, the run record and stage gates, NT8 deploy →
compile → frozen profile → backtest → trade extraction, the **three layers of parity**
(rule / signal / trade-set), the leg convention, which reports answer which question and
what the metrics mean, where results are stored and what is committed, and the checklist
that defines "validated".

**The one command** (everything else in that document is reference for what it does):

```powershell
.\.venv\Scripts\python.exe -m scripts.trading_framework.workflow `
    --strategy <registry_key> --ticker NQ1 --price-adjustment unadjusted `
    --optimize --trials 200 --oos-start 2025-01-01 `
    --nt8 --nt8-trades scripts/parity/fixtures/<capture>.csv
```

`scripts/trading_framework/workflow.py` runs every stage under ONE run record and ends by printing the promotion checklist (§9) with each criterion PASS / FAIL / **NOT EVALUATED**. Exit 0 = all passed, 1 = a criterion failed, 2 = a required stage raised. It refuses to guess a price basis or a timezone, refuses `--optimize` without `--oos-start`, and records a skipped stage WITH ITS REASON rather than omitting it. **Do not assemble a pipeline by hand** — **32** bespoke engine-drivers already exist and are frozen. (Only 6 are named `run_*`; the count and the naming are both measured in `tests/frozen_runners.py`, and §4.1 explains why matching on the filename would freeze 6 and let 26 keep breeding.)

**A strategy must report the criteria it evaluated** (§5.5). A trade list says *what*
happened; only the strategy can say *why*, and no MCP change can supply it. Python hunters
set `self.last_decisions` from `GateRecorder`; the C# side uses the generated
`DecisionLog.cs`, which writes `mcp_decisions_*.csv` where `nt_get_export` already serves it.
**The gate roster is layer 0 of parity** — `mean_reversion` evaluates 2 conditions and its
paired `BBMRReversionBot` has 20 parameters, so they are two strategies and no recall figure
between them means anything. Record *every* gate (not the first failure), record the *value*,
and use `measure()` for a magnitude.

**A new C# bot inherits `GovernedStrategy`** (§3.4), implements
`OnEvaluate(SetupEvaluation e)` and writes no logging code. `CheckForSignal()` is
**sealed** and the verdict is computed from the declared gates, so an unlogged criterion
cannot reach a trade — that is the difference from a helper the bot may ignore, which is
what the ten bots inheriting `RiskManagerBase` directly demonstrate (B1–B6). The base also
owns ADR-020's hard exit, the frozen defaults, unique entry names, and logging
`CanEnterTrade`'s nine previously-invisible refusals. Instrumentation is enforced by a
**shrink-only** inventory (`tests/uninstrumented.py`), so a new strategy is instrumented
from its first commit.

Three things to carry even if nothing else is read:
* **NT8 is authoritative for behaviour.** When Python and NT8 disagree, presume Python is wrong.
* **Parity is defined on the TRADE SET**, and judged on trade **geometry** (signed points travelled), not absolute price — a constant price offset *is* the adjustment basis, so back-adjustment is not a gate.
* **Leg counting follows NT8**: a queen/runner bracket is **two trades**, one row per leg.

Every rule in that document is marked 🟢 ENFORCED (something fails — the enforcer is named),
🟡 CONVENTION (checked by nobody), or 🔴 NOT BUILT. **Never promote a marker without naming
the enforcer in the same edit.** Open decisions and known gaps are §11; do not silently
work around one, and do not claim a strategy is validated while any 🔴 in §9 stands.

**Never write a new backtest runner.** 32 exist, they are frozen, and a 33rd fails
`scripts/trading_framework/tests/test_no_new_runners.py` — which matches on *behaviour*
(names an engine + is executable), not on the filename. Only `workflow.py` and
`run_backtest.py` are sanctioned. §4.1 has the reasoning.

**Only `--strategy` is required**, and two defaults are traps: `--price-adjustment`
defaults to `undeclared` (which FAILS `attributable`, by design) and `--ticker` defaults
to `NQ1` (it picks the point-value multiplier). Full measured table: §0.1.

## Global Rules
`AGENTS.md` at the repo root carries these same strategy rules for every other agent
(Copilot, Codex, Cursor, Gemini, Antigravity) — keep the two in sync when either changes.
See `.agents/AGENTS.md` for fail-fast error handling, GPU/hardware awareness, and repository directory organization standards. These apply to all agents (Copilot, Antigravity, Claude Code).

### Repository Directory & Script Organization Standard
- **Pine Scripts**: `scripts/indicators-pine/<feature_subfolder>/` (e.g. `scripts/indicators-pine/range_probability/`). Never drop loose `.pine` files in root or `indicators/`.
- **NinjaTrader 8**: `scripts/ninjatrader/indicators/<feature_or_author>/` and `scripts/ninjatrader/strategies/<feature_or_author>/`.
- **Python Scripts**: `scripts/<domain>/` (e.g. `scripts/range_probability/`, `scripts/ranges/`, `scripts/trader/`). Reusable packages in `src/<package_name>/`.
- **Data & Feeds**: `data/live/` (raw market data), `data/<domain>/` (derived matrices/feeds).
- **Documentation**: `docs/<domain>/` (feature docs), `docs/architecture/` (ADRs).

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
* **⭐ Strategy Workflow (CANONICAL — read before any strategy task)**: [STRATEGY_WORKFLOW.md](file:///c:/Users/vinay/tvDownloadOHLC/docs/architecture/STRATEGY_WORKFLOW.md) (write → backtest → NT8 validate → compare → report → store → promote; enforced vs convention vs not-built markers). **It is the ONLY strategy document** — **ten documents** were subsumed into it and deleted, nine on 2026-09-04 and the engine code-generation spec on 2026-09-05 (procedure, reasoning, build order, metric spec, engine spec, package/CLI overviews); its §13 records what moved where. Three companions, none a procedure: `scripts/trading_framework/README.md` (a package *map*), [BOT_FIX_BACKLOG.md](file:///c:/Users/vinay/tvDownloadOHLC/docs/architecture/BOT_FIX_BACKLOG.md) (a C# bot *worklist*, **B1–B9**, with a loop prompt whose step 0 is a first-principles read of which layer the change belongs in), and [HANDOVER.md](file:///c:/Users/vinay/tvDownloadOHLC/docs/architecture/HANDOVER.md) (**state only, and REWRITTEN rather than appended to** — start a new session there, but it is a pointer: where it disagrees with the workflow doc or the backlog, they win, and never quote a count from it). Plus [NT8_STRATEGY_OWNERSHIP.md](file:///c:/Users/vinay/tvDownloadOHLC/docs/architecture/NT8_STRATEGY_OWNERSHIP.md) (ADR-025, one-artifact-one-owner). If you find any other document describing how to build, run or judge a strategy here, it is stale.
* **Architectural Decisions**: [ADR.md](file:///c:/Users/vinay/tvDownloadOHLC/docs/architecture/ADR.md) (Timezones, normalization, vectorized models, prop-firm liquidation)
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
* **⚠️ THE NT8 ADDONS ARE NOT IN THIS REPO ANY MORE** (split executed 2026-08-12). RiskGuard, the trade copier and the MCP bridge live in two repos of their own, with their full history:
  * **[nt8-riskguard](https://github.com/vinay-veerappa/nt8-riskguard)** (`C:\Users\vinay\nt8-riskguard`) — guard + copier, the C# suite, the mutation batteries, the gates, the deploy tool, and the agent-loop profile + tickets (`agent/`). **The canonical record is `docs/RISKGUARD_HARDENING_HANDOVER.md` and `docs/RISKGUARD_COPIER_HARDENING_PLAN.md`** — read the handover's **§0, then §5 starting at §5.6, then the highest `§5.x`**. That file accretes; **§0 is stale by many sessions and §4a is historical, explicitly not a plan.** ⚠️ **Do not summarise defect history here.** This entry used to carry ~43KB of closure narrative for defects that were all closed and all recorded in the plan under their own IDs; it was loaded into every session and its headline numbers had rotted. Closure records go in the plan, under the ID they close — never at EOF, and never here.
    * **State measured 2026-08-18 (session 59):** `v1.44.0` deployed and live in `shadow`, armed, guarding. Suite **3170 / 0**, **46** mutation batteries, **516 anchors / 0 broken**, **11** gates green, CI green in **19m16s** at 13 bins. ⚠️ **A crash used to score as a detection.** Until `P1-153` the runner called all 677 tests as bare statements, so the first to THROW killed the process before `RESULTS:` printed — and every battery scores `NO RESULT LINE` as KILLED. 7 mutants across 5 bins were mis-scored that way. A throw is now a `[FAIL]` and the run continues. ⚠️ Run the suite the way CI does — `dotnet build tests/RiskGuardTests.csproj` then **`dotnet run --project tests/RiskGuardTests.csproj --no-build`**. `dotnet test` on this csproj exits **0 having run nothing**, which reads exactly like a pass.
    * ⚠️ **Do not put an open/closed defect count here.** The last one read `117 / 104 / 13` while its own breakdown summed to something else and the source disagreed with both, because nothing re-derived it. `tools/check_next_list_ids.py` computes it mechanically and refuses to do so vacuously — **run the gate, do not quote a number.**
    * ⚠️ **Run `gh run list` in each repo at the START of a session.** CI has run red for 7 and then 10 consecutive pushes while the docs claimed green. It costs five seconds.
    * ⚠️ **A broken NT8 Custom assembly is INVISIBLE.** `nt_compile` can return hundreds of errors while `nt_health` reads healthy, because NT8 keeps running the **last good assembly** — the only symptom is a deploy having no effect, which looks exactly like one that worked. `--verify` proves the FILES match, not that they compile.
    * ⚠️ **The bridge pins this repo by TAG** and deploys the vendored core alongside itself, so a stale pin makes `deploy.py` silently REVERT a live core. What matters is the tag's **RANGE**, not its own commit: `git diff --name-only <pin>..<main> -- addons/`.
    * ⚠️ **BROKERS DIFFER — do not build a compatibility matrix** (handover §5.84). Measured on one box: `Order.OrderId` is a submission GUID that Provider31 **replaces on accept** and `Sim101` never does; a resting stop is `Working` on Provider31 and `Accepted` on the Simulator; `Account.Change()` is echoed back by the Simulator. Three standing rules make the difference *unobservable* instead: **never key on a value the broker owns**; **never enumerate the LIVE order states — ask a question and close the TERMINAL set**, so an unrecognised state falls into the safe branch; and **evidence names its provider** — "live-validated" without one means `Sim101`.
  * **[nt8-mcp-bridge](https://github.com/vinay-veerappa/nt8-mcp-bridge)** (`C:\Users\vinay\nt8-mcp-bridge`) — `McpBridgeAddOn.cs` plus the Node MCP wrapper at `mcp/`; consumes nt8-riskguard as a submodule pinned to a tag. **State measured 2026-09-04:** harness **684 / 0**, wrapper **94 / 0**, **17** mutation batteries, **208 anchors / 0 broken**, **9** gates green, pin `v1.67.0` (current). ⚠️ **`nt_backtest` used to run a strategy nobody asked for.** The Strategy Analyzer window is REUSED and the strategy was applied with the lenient `SetP`, so an unresolvable name failed silently and the window kept whatever it already had — a request for `@SampleMACrossOver` ran `_McpTestBot` and returned `totalTrades: 0`, indistinguishable from that strategy simply not having traded. NT8 names its stock sample FILES with a leading `@` while the CLASS has none. Fixed and deployed 2026-09-04 (`7f13699`): the name is resolved *before* the shared window is touched, the selection is READ BACK and compared to the resolved `Type.Name`, and a mismatch fails closed through `paramErrors`. **The response now echoes `effectiveStrategy` and `effectiveGlobals` — a backtest is attributable only if what came back is what you asked for.** The wrapper lives here because **the wrapper and the addon are two halves of ONE contract** — the wrapper advertises tool schemas, the addon decides what it accepts — and a contract with its two sides in two repos cannot be pinned in one commit; every wrapper defect so far has been contract drift. ⚠️ **Run the wrapper tests the way CI does: `cd mcp && node --test`.** `node --test mcp/tests/` from the repo root is a *module* path on Node 24 and fails `MODULE_NOT_FOUND`, which reads exactly like a test failure. ⚠️ **New MCP tools do not appear in a running client until it RESTARTS**, and schemas are read at startup. ⚠️ **A gate script can be on disk and wired to nothing** — `tools/check_bridge_parses.py`, the only automated reader of `McpBridgeAddOn.cs`, had never run in CI (fixed 2026-08-18). Both repos' `check_ci_runs_every_battery.py` globbed `mutation/` only, so no *gate* in either repo was required to be wired anywhere; both now cover `check_*.py` too, matched on repo-relative path.
  * Do **not** re-add addon `.cs`, the csproj, the tickets or an addons sync path here. The split record is [NT8_REPO_SPLIT_PLAN.md](file:///c:/Users/vinay/nt8-riskguard/docs/NT8_REPO_SPLIT_PLAN.md) (now in the nt8-riskguard repo).
* **Self-Learning Layer Design**: [SELF_LEARNING_LAYER_DESIGN.md](file:///c:/Users/vinay/tvDownloadOHLC/docs/architecture/SELF_LEARNING_LAYER_DESIGN.md) (FTS5 search, user_prefs/USER.md profile, outcomes ledger, skill-write gate — Phases 0-3 implemented)
* **NT8 Deployment**: never hand-copy `.cs` into `Documents/NinjaTrader 8/bin/Custom/`. Rules and traps: [NT8_FILE_ORGANIZATION.md](file:///c:/Users/vinay/tvDownloadOHLC/docs/architecture/NT8_FILE_ORGANIZATION.md). Recompile via `nt_compile` after any of these.
  * **Strategies / indicators (this repo)**: `python scripts/utils/sync_nt8_strategies.py --verify` then without `--verify`. `--only addons` now exits 2 — there are no addon sources here. ⚠️ **Indicators sync to `Indicators/Vinay/` and `Indicators/RedTail/`, NOT a flat `Indicators/`** — fixed 2026-08-14, and the flat version was an armed trap: NT8 compiles `Indicators/` **recursively** (eleven vendor subfolders live there), so a second copy in a *different* subfolder still collides. All 23 repo indicators were already deployed by hand into those subfolders; the tool looked only at the top level, found none, and a plain sync would have written **23 duplicate class definitions** beside them. The orphan `Strategies/Vinay/ICTFVGBoS.cs` is hash-identical to the `From_NT8/` capture and benign. ⚠️ **A drift report does not say which side is stale — read the diff and its DIRECTION before syncing.** `NtDrawingCore.cs` reported `content-differs` for days, and the NT8 copy was the **newer** one: two `[System.CLSCompliant(false)]` attributes added by hand there and never backported. Running the sync — the obvious response — would have **reverted a live fix**, with returning warnings as the only symptom. Backported instead (`e038c1f0`). **Re-run the tool rather than trusting this line**; a sync claim in a doc is a claim about the day it was written.
  * **Addons (other repos)**: `nt8-riskguard` → `python tools/sync_nt8.py`; `nt8-mcp-bridge` → `python tools/deploy.py`, which deploys the bridge **and** its vendored core. Deploying either addon repo alone fails the whole NT8 Custom assembly, which stops **every** addon loading — the risk guard included.
* **Agent Patch Loop (ARCHIVED)**: [AGENT_PATCH_LOOP.md](file:///c:/Users/vinay/tvDownloadOHLC/docs/architecture/AGENT_PATCH_LOOP.md) (historical doc for the predecessor loop; the code is archived in `scripts/agent_loop/_archive_predecessor/`; do not run it)
* **Agent Loop v2 (current package)**: [agent-loop repo](https://github.com/vinay-veerappa/agent-loop) — language-agnostic harness; 9 phases + docs mode. Findings from driving it live are recorded as `CF-n` in [CONSUMER_FINDINGS.md](file:///c:/Users/vinay/agent-loop/docs/architecture/CONSUMER_FINDINGS.md); read that before filing a new one.
  * ⚠️ **`v0.6.7` is the pin in `requirements.txt` and is NOT what runs here.** `.venv` carries an **editable install pointing at `C:\Users\vinay\agent-loop`**, so whatever that checkout is on is what executes — thousands of insertions past the tag, while `pip show` still reports `0.6.7` because the constant has not moved. **Check the resolved path, not the number**: `python -m agent_loop --version` prints both. A colleague running `pip install -r requirements.txt` gets materially different code.
  * **State measured 2026-08-18 (session 58):** **749 pass, 36 skipped** and **selftest 13/13** at `beb108d`. ⚠️ **There are TWO harnesses.** `pytest -q` is the unit suite; `python -m agent_loop.selftest` drives the whole loop against stubbed models and asserts a verdict per scenario (source checkout only, never the installed package). It was found at **11/13**, red for an unknown number of sessions on a verdict name the ticket path does not produce, while pytest was green and CI ran only pytest (`CF-24`). **Run both.** ✅ It has CI now (added 2026-08-16; it had **none**, while three repos install it editable) — **Windows-only and deliberately so**, since the fixtures shell out with cmd.exe `cd /d` and every encoding defect this project ships is a cp1252 decode that cannot reproduce on Linux (`CF-22`).
  * ⚠️ **The suite prints one `PytestUnhandledThreadExceptionWarning` naming a cp1252 `UnicodeDecodeError` — that is a deliberate negative control, not a defect.** `test_subprocess_capture_encoding.py` reproduces the hazard on purpose to prove it still exists on this platform.
  * ⚠️ **Read a fix commit here before trusting it.** Two consecutive ones landed with **no tests**, in a repo whose convention is one acceptance test per finding, and a read of them found **six** defects (`CF-16`…`CF-21`). The one to carry is `CF-18`: a new detector computed its diagnosis correctly and wrote it to `GateResult.summary`, while the implementer is handed `feedback or summary` and the test gate **always** sets `feedback` — so on the only path that could produce the condition, the field was dead and the diagnosis reached nobody. **An alarm wired to an output nobody is listening on.**
  * **Panel**: `glm-5.2` + `deepseek-v4-flash`. An **uncorroborated REJECT is downgraded to REVISE**, and the arbiter **cannot recommend SHIP while any reviewer's BLOCKER stands dismissed** (that run ends `ESCALATED`, which is not promotable). ⚠️ `deepseek-v4-flash` **degenerates**, twice measured returning 373 then 853 findings against a cap of 60; that is scored `UNPARSEABLE` and the member is dropped. `CF-23` fixed the quorum that made dropping it impossible on a two-model panel — if a run still ends `PANEL_OUTAGE` with every gate green, arbitrate by hand and file it.
  * Do **not** pin below `v0.3.0`: `v0.1.0` is 14 commits of known defects behind, and `v0.2.0` raises `TypeError` on Python < 3.13, which kills every ticket at region extraction.
* **Agent Loop v2 Research**: [AGENT_LOOP_RESEARCH.md](file:///c:/Users/vinay/agent-loop/docs/architecture/AGENT_LOOP_RESEARCH.md) (state of the field across 13 coding agent harnesses)
* **Agent Loop v2 Plan**: [AGENT_LOOP_V2_PLAN.md](file:///c:/Users/vinay/agent-loop/docs/architecture/AGENT_LOOP_V2_PLAN.md) (9-phase execution plan, all complete)
* **Agent Loop Decisions**: [IMPLEMENTATION_DECISIONS.md](file:///c:/Users/vinay/agent-loop/docs/architecture/IMPLEMENTATION_DECISIONS.md) (every non-obvious decision recorded)
* **Consumer Profiles**: `scripts/agent_loop_config/` (python-tvdownloadohlc only; register via `--profile-module scripts.agent_loop_config`). The **nt8-riskguard profile and its tickets moved** to the `nt8-riskguard` repo as `agent/nt8_riskguard.py` + `agent/tickets_*.json` — run the loop from there, not here.
* **Agent Loop Usage**:
  ```powershell
  # NT8 RiskGuard ticket (C#) — run from C:\Users\vinay\nt8-riskguard, NOT here
  #   agent-loop --profile nt8-riskguard --profile-module agent.nt8_riskguard --tickets agent/tickets_p0.json --ticket T1

  # Python ticket
  .\.venv\Scripts\python.exe -m agent_loop --profile python-tvdownloadohlc --profile-module scripts.agent_loop_config.python_tvdownloadohlc --tickets tickets.json --ticket T1

  # Plan mode (defect -> ticket JSON)
  .\.venv\Scripts\python.exe -m agent_loop --profile python-tvdownloadohlc --profile-module scripts.agent_loop_config.python_tvdownloadohlc --mode plan --defect "description of the defect"

  # Developer mode (autonomous localization + edit)
  .\.venv\Scripts\python.exe -m agent_loop --profile python-tvdownloadohlc --profile-module scripts.agent_loop_config.python_tvdownloadohlc --mode developer --defect "description of the defect"

  # Docs mode — 4 sub-modes. changelog reads a diff; the other three read the
  # codebase (+ the graph, since this profile sets graph_project).
  .\.venv\Scripts\python.exe -m agent_loop --profile python-tvdownloadohlc --profile-module scripts.agent_loop_config.python_tvdownloadohlc --mode docs --docs-type changelog --review-base HEAD~1
  .\.venv\Scripts\python.exe -m agent_loop --profile python-tvdownloadohlc --profile-module scripts.agent_loop_config.python_tvdownloadohlc --mode docs --docs-type handover
  .\.venv\Scripts\python.exe -m agent_loop --profile python-tvdownloadohlc --profile-module scripts.agent_loop_config.python_tvdownloadohlc --mode docs --docs-type design --defect "feature to design"
  .\.venv\Scripts\python.exe -m agent_loop --profile python-tvdownloadohlc --profile-module scripts.agent_loop_config.python_tvdownloadohlc --mode docs --docs-type prd --defect "defect or feature"

  # Validate a ticket file without spending a model call. READ THE LINE RANGES:
  # a degenerate one-line region also prints OK. (NT8 tickets now live in the
  # nt8-riskguard repo; run this from there.)
  .\.venv\Scripts\python.exe -m agent_loop --profile python-tvdownloadohlc --profile-module scripts.agent_loop_config.python_tvdownloadohlc --tickets tickets.json --list
  ```
  Docs mode does **not** yet inject the doc-architect skill's conventions into its
  system prompts (the agent-loop README describes that as intended, not done), so
  generated docs will not match this repo's house format without editing.
* **Agent Loop Configuration**: every tunable (which model does which job, token
  budgets, whether a role thinks, round limits, panel deadlines) lives in
  `agent_loop/config.py`, which records *why* each default has its value. Override
  per-repo by creating `agent_loop.config.json` here (or `--config PATH` /
  `$AGENT_LOOP_CONFIG`); see `agent_loop.config.example.json` in the package repo.
  Unknown keys are rejected rather than ignored. **On a reasoning model,
  chain-of-thought is spent from the same budget as the answer** — if you set
  `think: true`, raise `max_tokens` in the same edit, or the model can burn the
  whole budget reasoning and return empty content.

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
* **`DataLoader`** reads **historical parquet only** and must NOT be used for current data — use live storage parquet or `load_fused_data()` instead. ⚠️ **Name the module, never just the class.** This line cited `scripts/shared/data_loader.py`, **which does not exist**; there are three classes called `DataLoader` (`scripts/libs_py/data/loader.py`, `scripts/edgeful/lib/data_loader.py`, and one inside `scripts/strategies/nine_thirty_breakout/utils/extract_or_retests.py`). The one the backtest pipeline uses is `scripts/libs_py/data/loader.py` (`load_enriched` → price + internals + sessions + 5m resample + VIX/VVIX), and for deep-history backtesting that is the correct choice.

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
* **Evidence-Chain Integrity (ADR-024)**: `trading_brain` receipt overrides, historical re-certification, and planned-family corrections are capability-gated or strictly identity-bound — never bypass via caller-supplied timestamps/indexes/callbacks. Services must call `assert_next_process_is_migration()` at startup; `FIXTURE_REPLAY_ACCEPTED` is a fixture battery, not live operational acceptance. Known limits (registered-artifact isolated eval, artifact-derived promotion metrics, live-soak ledger) are separate workstreams — do not claim them implemented.
* **Strict Context Window Rule**: Never read full files unless necessary. Always utilize line-specific views (`StartLine` & `EndLine` parameters) to load only target blocks (limit to 30–50 lines per turn) to optimize token consumption.
