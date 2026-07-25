---
applyTo: "**"
---

# Copilot Chat Startup Protocol

**Purpose:** Mirror Antigravity's `using-superpowers` + `sync-trading-brain` startup
chain so that GitHub Copilot Chat and Antigravity share the same startup sequence,
the same memory store (`.agent/memory.db`), and the same skill catalog
(`.agent/skills/*/SKILL.md`).

## MANDATORY STARTUP SEQUENCE (every new conversation)

Run these steps at the start of **every** session, before any substantive work:

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

### 4. Check skills before responding
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

## CONTEXT ANCHORS (same as Antigravity's sync-trading-brain)

These files are the "source of truth" — do targeted, line-specific reads on demand:
- `docs/architecture/ADR.md` — Architectural Decision Records
- `docs/SecondBrain_Trading.md` — Trading domain logic (ALN, IB, NQ personalities)
- `docs/indicators/DailyNYLevels/VISUAL_SYSTEM.md` — Visual compliance standard
- `docs/library/ict/ICT_SPEC_V1.md` — ICT engine API reference
- `docs/architecture/HARMONISED_TRADING_ARCHITECTURE.md` — 3-layer strategy pattern

## WHAT'S SHARED vs COPILOT-PRIVATE

| Store | Shared with Antigravity? | Use for |
|---|---|---|
| `.agent/memory.db` | ✅ Yes (both read/write) | All shared learnings, rules, preferences |
| `CLAUDE.md` | ✅ Yes (both auto-load) | Project commands, data architecture, ADR refs |
| `.agents/AGENTS.md` | ✅ Yes (Antigravity auto-loads; Copilot reads via this instruction) | Global rules (fail-fast, GPU) |
| `.agent/skills/*/SKILL.md` | ✅ Yes (both discover + read) | Skill-based workflows |
| `codebase-memory-mcp` | ✅ Yes (same MCP server) | Code structure knowledge graph |
| `/memories/` tool | ❌ Copilot-private | **Deprecated for shared knowledge.** Use only for Copilot-private ephemeral notes if ever needed. |