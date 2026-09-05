---
applyTo: "**"
---

# Copilot Chat Startup Protocol

## STRATEGY WORK OUTRANKS THE STARTUP SEQUENCE BELOW

If the task involves a trading strategy — writing, backtesting, validating in
NT8, comparing, reporting on or promoting one — read
[AGENTS.md](../AGENTS.md) and then
[docs/architecture/STRATEGY_WORKFLOW.md](../docs/architecture/STRATEGY_WORKFLOW.md)
**before** doing anything else, including before the startup sequence.

`STRATEGY_WORKFLOW.md` is the ONLY strategy document; ten others were subsumed
into it and deleted. Three things to carry even if you read nothing else:

* **One entry point.** `python -m scripts.trading_framework.workflow --strategy
  <key> --ticker <T> --price-adjustment <basis>`. **Never write a new backtest
  runner** — 32 exist, they are frozen, and a 33rd fails
  `scripts/trading_framework/tests/test_no_new_runners.py`.
* **NT8 is authoritative.** When Python and NT8 disagree, presume Python is
  wrong. Parity is judged on the **trade set**, per leg, on signed points.
* **Never promote an ENFORCED marker without naming the enforcer**, and never
  quote a count you did not just measure.


**Purpose:** Mirror Antigravity's `using-superpowers` + `sync-trading-brain` startup
chain so that GitHub Copilot Chat and Antigravity share the same startup sequence,
the same memory store (`.agent/memory.db`), and the same skill catalog
(`.agent/skills/*/SKILL.md`).

## MANDATORY STARTUP SEQUENCE (every new conversation)

Run these steps at the start of **every** session, before any substantive work.

### "sync" keyword convention
If the user's first message is exactly `sync` (case-insensitive), treat it as a
request to run the full Mandatory Startup Sequence below and announce the
result. Do not ask for clarification — just execute steps 1-4.

### 1. Load global rules
Read `.agents/AGENTS.md` — global rules (fail-fast on stale errors, GPU/hardware
awareness). These supplement `CLAUDE.md` (which is auto-loaded).

### 2. Recall memories from the shared memory store
Run the context_manager recall script to load saved learnings into context:

```bash
.\.venv\Scripts\python.exe .agent\skills\context_manager\scripts\recall.py --category INSTRUCTION --limit 20
```

Then recall any task-relevant categories (e.g., `architecture`, `trading_rule`,
`ALN_CONCEPT`, `ICT_CONCEPT`, `NQSTATS_CONCEPT`, `workflow`):

```bash
.\.venv\Scripts\python.exe .agent\skills\context_manager\scripts\recall.py --category architecture --limit 20
```

Load the returned memories into your working context.

### 3. Announce synchronization
State: "Synchronized with AGENTS.md, memory.db (N entries recalled), and the
following ADRs/concepts are active: [list the key ones from recalled memories]."

### 4. Verify codebase-memory MCP default project
Before any code-search task, ensure the codebase-memory MCP is usable. If
`mcp_codebase-memo_search_graph` returns `"no project loaded"`, the
`default_project` config has been lost. The CLI `config set` command does NOT
reliably persist to disk — use the persistence helper script instead:

```bash
.\.venv\Scripts\python.exe scripts\utils\persist_mcp_default_project.py
```

To just check the current value:

```bash
.\.venv\Scripts\python.exe scripts\utils\persist_mcp_default_project.py --verify
```

The config is stored in `~\.cache\codebase-memory-mcp\_config.db` (SQLite
`config(key, value)` table). The CLI `config list` display omits `default_project`
even when set — use `config get default_project` or the helper's `--verify`
flag to confirm the value.

**IMPORTANT**: The project slug is case-sensitive. The correct value is
`C-Users-vinay-tvDownloadOHLC` (capital C), NOT `c-Users-vinay-tvDownloadOHLC`.
A lowercase `c` causes `"no project loaded"` errors silently.

### 4. Verify codebase-memory MCP default project
Before any code-search task, ensure the codebase-memory MCP is usable. If
`mcp_codebase-memo_search_graph` returns `"no project loaded"`, the
`default_project` config has been lost. The CLI `config set` command does NOT
reliably persist to disk — use the persistence helper script instead:

```bash
.\.venv\Scripts\python.exe scripts\utils\persist_mcp_default_project.py
```

To just check the current value:

```bash
.\.venv\Scripts\python.exe scripts\utils\persist_mcp_default_project.py --verify
```

The config is stored in `~\.cache\codebase-memory-mcp\_config.db` (SQLite
`config(key, value)` table). The CLI `config list` display omits `default_project`
even when set — use `config get default_project` or the helper's `--verify`
flag to confirm the value.

### 5. Check skills before responding
Skill catalog: `.agent/skills/*/SKILL.md` (same as Antigravity).

- If a skill applies to the user's task (even a 1% chance), read its `SKILL.md`
  via `read_file` before responding.
- **Mandatory skills:**
  - `sync-trading-brain` — before any trading logic, data pipeline, or indicator
    work. Announce: "Using sync-trading-brain to align with trading rules."
  - `context_manager` — for any memory read/write (use the scripts, not the
    `/memories/` tool).

## MEMORY — READ AND WRITE TO `.agent/memory.db`

**Do NOT use the `/memories/` tool for shared knowledge.** The `/memories/` tool
writes to a Copilot-private path that Antigravity cannot see. Instead, use the
shared `context_manager` scripts so both tools read/write the same store.

### Write a new memory (learn something)
```bash
.\.venv\Scripts\python.exe .agent\skills\context_manager\scripts\remember.py \
  --category "architecture" \
  --content "Description of the learning" \
  --tags "tag1,tag2,tag3"
```

### Read/search memories
```bash
.\.venv\Scripts\python.exe .agent\skills\context_manager\scripts\recall.py --query "IB pipeline"
.\.venv\Scripts\python.exe .agent\skills\context_manager\scripts\recall.py --category trading_rule
```

### When to write a memory
- User explicitly says "remember this" or "learn this"
- You solve a tricky setup that would save time next session
- User corrects your behavior/preferences
- Architectural decision is made that future sessions should respect

### Categories in use (from existing memory.db)
`test`, `architecture`, `data_inventory`, `database`, `market_stats`,
`user_profile`, `standard`, `trading_rule`, `ALN_CONCEPT`, `ALN_ALGORITHM`,
`ALN_STAT`, `INSTRUCTION`, `ICT_CONCEPT`, `NQSTATS_CONCEPT`, `NQSTATS_HOUR`,
`NQSTATS_IB`, `NQSTATS_NOON`, `NQSTATS_SDEV`, `NQSTATS_1H`, `NQSTATS_TIMING`,
`NQSTATS_VERIFIED`, `workflow`, `data_architecture`

## SKILLS — SAME CATALOG AS ANTIGRAVITY

Both tools discover and read skills from the same paths:
- `.agent/skills/*/SKILL.md` (Antigravity native)
- `.agents/skills/*/SKILL.md` (cross-tool)
- `.claude/skills/*/SKILL.md` (Claude Code)

Key skills in this repo:
- `sync-trading-brain` — mandatory startup for trading logic alignment
- `context_manager` — memory.db read/write
- `using-superpowers` — skill invocation protocol
- `ict-concepts-reference` — ICT concept lookup
- `nqstats_analyzer` — NQ statistics
- `backtest_commander` — backtesting
- `daily_analysis` — daily analysis workflow

## CODE SEARCH — USE CODEBASE-MEMORY MCP FIRST (mandatory)

**Consult `.agent/USER.md` when user preferences, trading style, risk rules, or
project conventions are relevant to the task.** This file is auto-rendered from
the `user_prefs` table — it is authoritative shorthand for what the user wants.

For **any** code-exploration task — finding a function/class/route, who-calls-what,
architecture questions, refactor-impact analysis, dead-code detection — you MUST
use the `codebase-memory-mcp` tools **first**, not `grep_search` / `file_search`.

Preferred tools (in order):
1. `mcp_codebase-memo_search_graph` — find functions/classes/routes by name pattern
2. `mcp_codebase-memo_trace_call_path` — who calls what, dependency chains
3. `mcp_codebase-memo_get_architecture` — high-level package/service overview
4. `mcp_codebase-memo_search_code` — grep + graph enrichment (fallback)

Only fall back to `grep_search` / `file_search` if:
- The MCP returns no results, OR
- You need a plain-text substring match with no structural meaning (e.g. a literal
  string in a config file), OR
- The user explicitly asks for a grep.

**Rationale**: the code graph (27k+ nodes) gives precise definitions, call edges,
and ranked results. grep is a flat text scan and misses structural relationships.
Using the MCP first is faster and more accurate for code questions.

## NT8 / NINJATRADER TOOLING (MANDATORY)

- **Compile**: ALWAYS use the `mcp_nt-mcp-server_nt_compile` MCP tool. NEVER use curl, PowerShell `Invoke-RestMethod`, Python `requests`, or any manual HTTP call to `http://localhost:7890/api/compile`. The MCP tool handles the connection-reset/hot-swap correctly via the `/api/compile/result` polling fallback. Manual HTTP calls crash because the bridge's HTTP listener thread is not the WPF UI thread.
- **All NT8 operations**: Use MCP tools (prefixed `mcp_nt-mcp-server_nt_*`) for everything — compile, backtest, accounts, quotes, bars, search, logs, indicator values, draw levels, open chart, script execute, riskguard. The MCP server (`nt-mcp-server.js`) handles the HTTP bridge correctly. Only use direct `curl` to `http://localhost:7890/api/*` as a fallback if the MCP tool is unavailable.
- **Sync**: Use `.\.venv\Scripts\python.exe scripts\utils\sync_nt8_strategies.py` to push repo source to NT8 Custom folder. This covers **strategies and indicators only** — the addons moved out (2026-08-12) and deploy from `nt8-riskguard` (`tools/sync_nt8.py`) and `nt8-mcp-bridge` (`tools/deploy.py`). After syncing new files, NT8 may need a restart to detect them (hot-swap only updates existing files, not new ones).
- **Stale cache**: If the MCP compile returns errors referencing line numbers beyond the file's actual length, or referencing code you've already fixed, NT8 is caching a stale version. Restart NT8 to clear the Roslyn cache.
- **Bridge port**: 7890 (NOT 51328 — that port is stale).
- **Indicator values fix**: The `indicator_values` endpoint uses `AppDomain.CurrentDomain.GetAssemblies()` to find `NinjaTrader.Custom` (Type.GetType fails because it's in a separate AssemblyLoadContext). If it still fails, the indicator needs to be hosted on a chart or strategy instead.
- **DevMode**: Create `mcp_dev.on` in NT8 UserDataDir to enable `script_execute` and dev endpoints. Currently enabled.
- **Audit other bridge endpoints**: Before using any `/api/*` endpoint, check whether it marshals to the WPF Dispatcher. Endpoints that call NT8 APIs (compile, backtest, indicator operations) MUST run on the UI thread via `Dispatcher.Invoke()`. The `McpBridgeAddOn.cs` source **left this repo in the 2026-08-12 split** — it is now `addons/McpBridgeAddOn.cs` in the [nt8-mcp-bridge](https://github.com/vinay-veerappa/nt8-mcp-bridge) repo (`C:\Users\vinay\nt8-mcp-bridge`). Read it there before assuming an endpoint works.

## CONTEXT ANCHORS (same as Antigravity's sync-trading-brain)

These files are the "source of truth" — do targeted, line-specific reads on demand:
- `docs/architecture/ADR.md` — Architectural Decision Records
- `docs/SecondBrain_Trading.md` — Trading domain logic (ALN, IB, NQ personalities)
- `docs/indicators/DailyNYLevels/VISUAL_SYSTEM.md` — Visual compliance standard
- `docs/library/ict/ICT_SPEC_V1.md` — ICT engine API reference
- `docs/architecture/STRATEGY_WORKFLOW.md` — THE strategy document: three pillars (§1.1), the `hunt()` contract, backtest → NT8 → parity → reports → promotion

## WHAT'S SHARED vs COPILOT-PRIVATE

| Store | Shared with Antigravity? | Use for |
|---|---|---|
| `.agent/memory.db` | ✅ Yes (both read/write) | All shared learnings, rules, preferences |
| `CLAUDE.md` | ✅ Yes (both auto-load) | Project commands, data architecture, ADR refs |
| `.agents/AGENTS.md` | ✅ Yes (Antigravity auto-loads; Copilot reads via this instruction) | Global rules (fail-fast, GPU) |
| `.agent/skills/*/SKILL.md` | ✅ Yes (both discover + read) | Skill-based workflows |
| `codebase-memory-mcp` | ✅ Yes (same MCP server) | Code structure knowledge graph |
| `/memories/` tool | ❌ Copilot-private | **Deprecated for shared knowledge.** Use only for Copilot-private ephemeral notes if ever needed. |