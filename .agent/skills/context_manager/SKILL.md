---
name: Context Manager
description: Persistent memory system for the agent to store and retrieve context, preferences, and architectural decisions across sessions.
---

# Context Manager Skill

This skill allows the agent to store and retrieve information from a persistent SQLite database. This "memory" is useful for keeping track of user preferences, architectural patterns, decision logs, and active task states across different chats and days.

## Capabilities

1.  **Remember**: Store a new piece of information with a category and tags.
2.  **Recall**: Search for information using full-text search or filter by category.

## usage

### Python Scripts

The core logic resides in `scripts/memory_db.py`.
Convenience wrappers are provided:

-   `scripts/remember.py`: Add a memory.
-   `scripts/recall.py`: Search memories.

### Examples

**Adding a Memory:**
```bash
python scripts/remember.py --category "preference" --content "User prefers Tailwind CSS for all new web projects." --tags "css,ui,frontend"
```

**Recalling a Memory:**
```bash
python scripts/recall.py --query "Tailwind"
# Or by category
python scripts/recall.py --category "preference"
```

## Database Schema

The database is located at `.agent/memory.db`.

### `memories` (existing)
- `id`: INTEGER PRIMARY KEY
- `category`: TEXT
- `content`: TEXT
- `tags`: TEXT
- `created_at`: DATETIME
- `updated_at`: DATETIME

### `memories_fts` (P0 — FTS5 virtual table)
- `content`, `tags`: indexed columns
- Kept in sync via AFTER INSERT/UPDATE/DELETE triggers
- `search_memories` uses FTS5 MATCH with bm25 ranking, falls back to LIKE on empty/error

### `user_prefs` (P1 — structured profile)
- `key`: TEXT PRIMARY KEY
- `value`: TEXT
- `confidence`: REAL (1.0 user-authored, 0.7 inferred, 0.5 runtime)
- `source`: TEXT
- `updated_at`: DATETIME

### `outcomes` (P2 — outcome ledger)
- `id`, `ts`, `tag`, `subject`, `outcome`, `pnl_local`, `ticker`, `entry_price`, `exit_price`, `run_id`, `symbol`, `session`, `verdict`, `metadata`, `archived`
- Consent via tool-call (same pattern as `link_memory_to_code`)
- Raw PnL only surfaced via `recap_outcomes(verbose=True)`

### `process_queue` (P3 — staged skill proposals)
- `id`, `type`, `payload`, `status`, `created_at`, `approved_at`
- `type ∈ {skill_proposal}` only

## New CLIs

### `seed_profile.py` — seed user_prefs from curated sources
```bash
python .agent/skills/context_manager/scripts/seed_profile.py           # dry-run
python .agent/skills/context_manager/scripts/seed_profile.py --apply   # write
python .agent/skills/context_manager/scripts/seed_profile.py --apply --render  # write + render USER.md
```

### `skill_writer.py` — the only writer into `.agent/skills/`
```bash
python scripts/skill_writer.py --name my-skill --source path/to/draft.md
```
Convention, not a filesystem gate. Dedupes against `_skill_names.txt` + existing SKILL.md descriptions.

## MCP Tools (via nq-data-bridge)

| Tool | Phase | Purpose |
|---|---|---|
| `render_profile()` | P1 | Renders USER.md from user_prefs + select memories |
| `capture_outcome(tag, subject, outcome, ...)` | P2 | Records an outcome (consent via call) |
| `recap_outcomes(period_days, tag, verbose)` | P2 | Aggregate outcome stats (verbose=True for raw PnL) |
| `propose_skill(tag)` | P3 | Proposes a SKILL.md from ≥3 distinct wins; never writes file |
