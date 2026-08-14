# Skill Audit — 2026-08-10

## Overview

The project has skills in multiple directories, read by different tools. This
audit consolidated them into a single source of truth and fixed all skills to
meet the standard format.

## Before the audit

| Location | Tool | Skills | Status |
|---|---|---|---|
| `tvDownloadOHLC\.agent\skills\` | opencode | 30 | Active, but no `## When to use` or `applyTo` |
| `tvDownloadOHLC\.agents\skills\` | Claude Code | 6 | Active, but only 6 of the 30 skills |
| `tvDownloadOHLC\.agent\skills_backup\` | Nobody | ~200 | Archive of community skills, never loaded |

**Problem**: opencode saw 30 skills, Claude Code saw 6 (different ones). 38 of
42 skills had no `## When to use` section. None had `applyTo`. The backup had
~200 community skills, 12 of which were useful.

## What was done

### 1. Centralized skills — junction

Deleted `tvDownloadOHLC\.agents\skills\` (6 skills, all duplicates or subsets).
Created a Windows junction: `.agents\skills\` → `.agent\skills\`.

**Result**: both opencode and Claude Code now read from the same source of
truth. Both see all 42 skills.

### 2. Copied 12 useful backup skills

From `.agent\skills_backup\` to `.agent\skills\`:

| Skill | Why |
|---|---|
| `code-review-checklist` | Comprehensive code review checklist |
| `production-code-audit` | Autonomous deep-scan of codebase |
| `verification-before-completion` | Verification before claiming work is done |
| `skill-creator` | Creating and managing skills (needed for learning loop) |
| `requesting-code-review` | Before merging to verify work |
| `receiving-code-review` | Handling code review feedback |
| `finishing-a-development-branch` | Clean up before merging |
| `python-patterns` | Python development patterns |
| `performance-profiling` | Performance profiling for trading code |
| `prompt-caching` | LLM prompt caching strategies |
| `context-window-management` | Context window optimization |
| `lint-and-validate` | Auto QC, linting, static analysis |

### 3. Fixed all 42 skills

Added `## When to use` section to 38 skills that lacked it.
Added `applyTo` to 38 skills that lacked it.

**Result**: every skill now has:
- A `## When to use` section explaining when to load it
- An `applyTo` pattern specifying which file types trigger auto-load

### 4. Deleted the backup

Deleted `.agent\skills_backup\` (19.5 MB, 1971 files, ~188 irrelevant community
skills). The 12 useful ones were already copied to the active directory.

### 5. Created junctions in agent-loop repo

Created `.agent\skills\` and `.agents\skills\` junctions in the agent-loop
repo, both pointing to `tvDownloadOHLC\.agent\skills\`. Both tools see the
same 42 skills in both repos.

## After the audit

| Location | Tool | Skills | Status |
|---|---|---|---|
| `tvDownloadOHLC\.agent\skills\` | opencode + Claude Code (via junction) | 42 | All have `## When to use` + `applyTo` |
| `agent-loop\.agent\skills\` | opencode (junction to tvDownloadOHLC) | 42 | Same |
| `agent-loop\.agents\skills\` | Claude Code (junction to tvDownloadOHLC) | 42 | Same |

## Skill inventory (42 skills)

### Trading-specific (15)
- `backtest_commander` — run/validate trading strategy backtests
- `daily_analysis` — daily market analysis pipeline
- `daily_classification` — R1/R2/DWP/DNP classification
- `data_explorer` — inspect Parquet data files
- `data_management` — regenerate derived data files
- `data_pipeline_doctor` — diagnose data quality issues
- `ict-concepts-reference` — ICT/SMC concepts reference
- `ict_trader` — key price levels and bias context
- `market_analysis_suite` — full technical analysis pipeline
- `nqstats_analyzer` — NQStats verification and bias briefings
- `rth_gaps_manager` — RTH gap data management
- `stats_trader` — statistical trade plan generation
- `sync-trading-brain` — startup synchronization with Second Brain
- `tos_expected_moves` — TOS Expected Move extraction
- `trading-indicator-development` — cross-platform indicator development

### Engineering quality (12)
- `clean-code` — pragmatic coding standards
- `code_guardian` — quality checks before workflows
- `code-review-checklist` — comprehensive code review
- `production-code-audit` — autonomous codebase scan
- `verification-before-completion` — verify before claiming done
- `requesting-code-review` — verify before requesting review
- `receiving-code-review` — handle review feedback
- `finishing-a-development-branch` — clean up before merging
- `lint-and-validate` — auto QC and linting
- `performance-profiling` — performance optimization
- `python-patterns` — Python development patterns
- `systematic-debugging` — systematic debugging methodology

### Testing (3)
- `test-driven-development` — RED-GREEN-REFACTOR cycle
- `test-fixing` — smart error grouping for test fixes
- `webapp-testing` — Playwright web app testing

### Planning & documentation (5)
- `concise-planning` — actionable plans for coding tasks
- `writing-plans` — structured plans with dependencies
- `documentation_architect` — auto-create/update architecture docs
- `executing-plans` — not copied (duplicate of concise-planning)
- `plan-writing` — not copied (duplicate of writing-plans)

### Context & memory (3)
- `context_manager` — persistent memory across sessions
- `context-window-management` — LLM context window optimization
- `prompt-caching` — LLM prompt caching strategies

### Agent/tooling (4)
- `agentic-maker-checker-protocol` — maker-checker implementation
- `skill-creator` — creating and managing skills
- `smart-model-delegation` — token-saving model routing
- `smart_commit` — automated git staging and commits

### UI & Pine Script (2)
- `ui_engineer` — Next.js/TypeScript/Tailwind UIs
- `pinescript-v6-tradingview` — Pine Script v6 reference

### Workflow & misc (3)
- `discord_notifier` — Discord webhook notifications
- `using-superpowers` — skill discovery and setup
- `pinescript-v6-tradingview` — Pine Script v6 reference

## What's not here (and why)

- **Antigravity built-in skills** (`agy-customizations`, `antigravity_guide`,
  `permissioned-github`) — tool-specific, managed by Antigravity. Left in
  `.gemini/antigravity/builtin/skills/`.
- **VSCode extension skills** (Pylance, etc.) — plugin-managed, not
  user-controllable.
- **~188 community skills** (Shopify, WordPress, game dev, pentesting, CRO,
  etc.) — deleted. Available on GitHub if needed again.

## Learning loop integration

The learning loop (Phase 9) can now write new skills to
`tvDownloadOHLC\.agent\skills\` and they will be immediately available to
both opencode and Claude Code in both repos (via junctions).

The `skill-creator` skill was specifically copied from the backup to support
this — it documents the format conventions for creating new skills.