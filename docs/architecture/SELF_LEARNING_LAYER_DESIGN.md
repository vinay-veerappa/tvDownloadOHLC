# Self-Learning Layer — Design & Roadmap

**Last updated:** 2026-08-10 (rev 3 — agent-loop review fixes applied)
**Status:** Phases 0-3 implemented, smoke-tested, and agent-loop reviewed (GLM-5.2 + DeepSeek-V4-Pro). All blocking findings fixed. Phase 4 optional (not built).
**Supersedes:** n/a (new capability on top of the consolidated `.agent/memory.db` store).
**Git:** this document must be committed before any implementation commit references it.

---

## 1. Goal

Turn `.agent/memory.db` (184 rows, canonical across all agents) from a *passive ledger*
(agents write facts they feel are worth remembering) into an **active self-learning loop**:
the store records what the user actually does and prefers, models that behaviour, and
auto-generates reusable procedures — each write consented to by the user before it lands.

Design principle (from the Hermes-style research): **replicate the mechanisms, do not
install a separate runtime** (`~/.hermes`), do not vendor a new framework. Every new
capability is either (a) a lightweight Python module in the existing `context_manager`
skill, or (b) a thin addition to the `nq-data-bridge` MCP server, because that server is
already wired into all five agent configs (opencode, VS Code, Claude Code, Continue,
Antigravity).

---

## 2. Current state (baseline, verified 2026-08-10)

| Fact | Value |
|---|---|
| Canonical store | `.agent/memory.db`, table `memories(id, category, content, tags, created_at, updated_at)` |
| Row count | 184 (verified by `SELECT count(*) FROM memories`) |
| READ path | `context_manager/scripts/recall.py` (`LIKE` on content/tags, `memory_db.py:63`), `nq-data-bridge query_memory` (`data_server.py:73`, `LIKE`) |
| WRITE path | `context_manager/scripts/remember.py`, `nq-data-bridge add_memory` / `link_memory_to_code` |
| Schema owners | **two divergent `_init_db` implementations**: `memory_db.py:19-35` + `SemanticMemory._init_db` (`data_server.py:32-44`). They agree by coincidence today (same 6 columns). **B1: must unify before P0.** |
| FTS5 | available in venv sqlite (3.49.1) but **not used** — `memories_fts` absent |
| `user_profile` | 2 rows (ids 12, 13), user-authored |
| Outcome data | none; no `outcomes` table, no capture path |
| Auto-procedures | none; no `scripts/skill_writer.py`, no `propose_skill` tool |
| `_skill_names.txt` | exists, 272 entries (`.agent/skills/_skill_names.txt`) |
| Agents wired | 5 configs registered against `nq-data-bridge` (see §7 verification step) |

**Bootstrap inputs that already exist and should seed the profile:**
- `docs/architecture/ADR.md`-style ADRs (architectural decisions the user ratified).
- `SecondBrain_Trading.md` (explicit trading domain rules the user wrote).
- The folded `claude_memory` rows (11 rows — facts Claude learned and the user kept).
- `data/` trade journals / `nt_trade_journal` (execution outcomes).

---

## 3. Architecture

```
 ┌─────────────────────────────────────────────────────────────────────┐
 │                    Agent Agents (5 configs)                         │
 │   opencode · VS Code · Claude Code · Continue · Antigravity         │
 └───────────┬─────────────────────────────────────────────────────────┘
             │  MCP tools: add_memory · query_memory · link_memory_to_code
             │  + recall.py / remember.py (context_manager skill)
             ▼
 ┌──────────────────────  nq-data-bridge (data_server.py)  ────────────┐
 │  SemanticMemory adapter  ──►  .agent/memory.db                       │
 │  NEW: render_profile · capture_outcome · recap_outcomes · propose_skill │
 └───────────┬─────────────────────────────────────────────────────────┘
             │ sqlite3
             ▼
 ┌──────────────────────  .agent/memory.db  ───────────────────────────┐
 │  memories      : facts, decisions, rules (existing)                  │
 │  memories_fts  : FTS5 index over memories (P0)                        │
 │  user_prefs    : structured profile (trading style, risk, conv.)     │
 │  outcomes      : trade/run outcomes + verdict (consent-gated)        │
 │  process_queue : staged skill proposals awaiting approval             │
 └──────────────────────────────────────────────────────────────────────┘
             │ sqlite3 FTS5 (upgrade from LIKE)
             ▼
 notes-folder rendering  ──►  `USER.md` + per-topic `.md` files (Hermes-style)
```

Three write paths exist today (`add_memory` via MCP, `remember.py` via skill, and
`link_memory_to_code`). All three must continue to require the full row to be complete
(category, content, tags) — no partial/blank rows.

---

## 4. Component designs

### 4.1 User profile (`USER.md` + `user_prefs` table) — P1

**Runtime representation:** new table `user_prefs(key TEXT PK, value TEXT, confidence REAL, source TEXT, updated_at)`.

**Rendered surface:** a `USER.md` markdown compiled from `user_prefs` + select `memories`
rows with category `user_profile`/`standard`, refreshed on every write or explicit render.

**Seeded from (one-time, each item user-approved via `seed_profile.py --apply`):**
1. `SecondBrain_Trading.md` → `trading_*` keys (instruments, sessions, risk style).
2. ADR.md + selected `architecture` memories → `conventions_*` keys (timezone, vectorized-only,
   prop-firm RTH close, visual-compliance, ADR-017/018/020/021/022).
3. Folded `claude_memory` rows → `lessons_*` keys (Account.Change semantics, test-doubles,
   git-push blockers).
4. `.github/copilot-instructions.md` + `.claude/settings.json` hooks → `api_*` / `workflow_*`
   (MCP-first rule, compile rule, Curl-exec rule).

**Seeding is hand-curation, not automation.** There is no extraction pipeline that turns
freeform docs into key-value rows. `seed_profile.py` carries a curated constant list (the
12-15 rows above), prints them on dry-run, and writes them on `--apply`. The "ingestion"
word in earlier drafts was aspirational; the real mechanism is a reviewed, hand-picked
seed list with a user-approval CLI gate.

**`confidence` formula (pinned, was S1):**
- User-authored seed (from ADR/SecondBrain/copilot-instructions, ratified by user): **1.0**.
- Inferred from `claude_memory` rows (facts the user kept but didn't author): **0.7**.
- Inferred from runtime `add_memory` rows tagged `user_profile`/`preference`/`standard`:
  **0.5** on first write, +0.1 per repeat (capped 0.9).
- Recency decay: rows not written to in 90 days drop 0.1 per 30 days (floor 0.2).
- A model reading `user_prefs` must not infer a broad preference from a single row with
  `confidence < 0.6`.

**During use:** every `add_memory` call with a row tagged `user_profile`, `preference`, or
`standard` upserts a corresponding `user_prefs` row with confidence per the formula above.

**Write contract:** the profile is *authoritative shorthand, not a dump*. Each key must be
one line or less in `USER.md`; models reading it must treat absent keys as "no info",
never as "opposite".

### 4.2 Outcome capture — P2 (consent via tool-return, no separate staging table)

**Runtime representation:** new table (schema pinned, was S4):
```sql
outcomes(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  tag TEXT NOT NULL,
  subject TEXT,             -- what was attempted (distinctness key for P3)
  outcome TEXT,             -- freeform description
  pnl_local REAL,            -- absolute, local currency
  ticker TEXT,               -- for ADR-002 cross-session normalization
  entry_price REAL,
  exit_price REAL,
  run_id TEXT,               -- links repeated attempts of the same setup
  symbol TEXT,
  session TEXT,              -- asia/london/ny
  verdict TEXT NOT NULL,     -- win | loss | flat | mixed | n/a
  metadata TEXT,             -- JSON blob, unindexed
  archived INTEGER DEFAULT 0 -- soft-delete (was S5)
)
```
`run_id`/`symbol`/`session` are real columns (not JSON-extracted) so P3 matching does not
require a schema change to a table with live data.

**Consent model (resolved, was blocking #1):** `capture_outcome(tag, subject, outcome,
pnl=0, ticker=None, run_id=None, symbol=None, session=None, metadata=None) → str`
**writes directly into `outcomes`** and returns a confirmation message describing the
verdict. This mirrors the established `link_memory_to_code` precedent in this codebase:
the tool performs the write and the return text *is* the confirmation surface. The model
only calls `capture_outcome` when the user has asked for it, so the call itself is the
consent. There is no separate `confirm_outcome` tool, no `status` column, and no staging
in `process_queue` (that table is skill-proposal-only). The "stages a row; only committed
when explicitly asked" language in rev 1 was a contradiction with the `link_memory_to_code`
precedent it cited — resolved here.

**Verdict derivation:** the tool infers `verdict` from `outcome` if the caller omits it:
keywords `win`/`profit`/`hit` → `win`; `loss`/`miss`/`stop` → `loss`; `flat`/`scratch`/`be`
→ `flat`; `mixed`/`partial` → `mixed`; else `n/a`.

**Consumption (read-only):**
- `query_memory` does NOT return raw outcome rows. After memory results, if the query term
  matches an outcome `tag`, it appends a one-line projection: `Outcomes [<tag>]: N wins /
  N losses (win-rate X%) in last 7d`. Raw `pnl_local` is never in this projection.
- `recap_outcomes(period_days=7, tag=None, verbose=False) → str`: returns aggregate
  counts per tag (`n_wins`, `n_losses`, `n_flats`, `n_mixed`, `win_rate`, `total`) for the
  period. `verbose=True` adds itemized rows (`id, ts, tag, subject, verdict, pnl_local`) —
  the only path that surfaces raw PnL.

**Aggregation (privacy preserving):** all aggregation is SQL `GROUP BY` (vectorized in the
engine, not Python loops). The **ADR-017 zero-loop constraint applies to any Python-side
post-processing of outcome rows**, not to the SQL itself. SQL aggregation is preferred and
satisfies the constraint.

**Retention (was S5):** `outcomes` is append-only with a soft-delete (`archived=1`, excluded
from default queries). `process_queue` rows unapproved for 30 days are pruned by
`prune_process_queue(older_than_days=30)` — run manually or on a schedule.

### 4.3 Skill-write gate — P3

**Goal:** when the same action succeeds repeatedly (same tag, ≥ 3 distinct wins, no
interleaved loss in the window), propose lifting the procedure into a reusable `.md` under
`.agent/skills/<name>/SKILL.md` so future sessions can `skill load` it.

**Gate mechanics (Hermes-style human approval):**
1. `propose_skill(tag) → str`: queries `outcomes` for the tag, applies the threshold
   (below), dedupes against existing skills, generates a draft, inserts a
   `process_queue` row (type='skill_proposal', status='proposed', payload=draft), and
   returns the draft text. **The model never writes the file itself.**
2. The user edits/saves the draft; then only `scripts/skill_writer.py --name X --source PATH`
   persists it into `.agent/skills/`.
3. Every persisted skill has front-matter `name` + `description` matching the repo's
   existing `SKILL.md` convention (like `context_manager/SKILL.md`) and a provenance line:
   `based_on: outcome tag <tag> (<n> matched)`.
4. Dedupe: `propose_skill` reads `.agent/skills/_skill_names.txt` (272 entries, exists) and
   scans `.agent/skills/*/SKILL.md` front-matter `description` for substring overlap with
   the tag. The match is **keyword/substring, not semantic** — a real semantic-coverage
   check is out of scope for a stdlib+sqlite3 tool. If the tag or its key tokens already
   appear in an existing skill description, the proposal is refused.

**Threshold (pinned, was S2):**
- "Distinct success" = distinct `subject` value, within the last 30 days.
- `flat`/`mixed`/`n/a` verdicts are **excluded** (not counted as success or failure).
- "No interleaved failure" = zero `verdict='loss'` rows for the tag in the 30-day window.
- Minimum: **≥ 3 rows with `verdict='win'` AND distinct `subject` AND zero `loss` rows**.

**Guard:** the gate never proposes skills from a single datapoint, never from `claude_memory`
rows alone (those are reference facts, not proven procedures), and never bypasses the user.

**`skill_writer.py` is a convention, not a filesystem gate (was my-review #11).** Nothing
technically prevents another script from writing to `.agent/skills/`. The safety rail is
the dedupe check + the human-approval step + the single named CLI, not a permission
boundary. Documented as such so no one assumes it is enforced at the OS level.

### 4.4 Search upgrade: LIKE → FTS5 — P0

Current `search_memories` in `memory_db.py:63` uses `LIKE '%x%'` on content/tags. Upgrade
the `memories` table to a FTS5 virtual table (`memories_fts`) kept in sync via triggers, so:
- multi-word queries rank sensibly (bin `query_memory` + `recall.py --query "nt8 order change"`),
- tag search is a proper FTS column instead of comma-joins,
- the three LIKE callers are ported, not just `recall.py`.

**FTS5 is not LIKE (was my-review #4-5).** FTS5 tokenizes on non-alphanumeric chars. Query
`"09:30"` becomes tokens `09` + `30` → matches any doc containing both, not the literal
string. Query `"5m"` → tokens `5` + `m`. AND-joined quoted tokens are stricter than LIKE
substring. **This is an accepted behavior change**, not a regression — the trade is
ranked multi-word search vs. exact-substring matching. To preserve recall where FTS5
returns nothing, every FTS call site **falls back to LIKE** on empty results or
`OperationalError`.

**Three LIKE callers must all be ported (was B2):**
1. `recall.py` → `memory_db.py:search_memories` (content/tags LIKE)
2. `query_memory` → `SemanticMemory.query` (`data_server.py:73`, content/tags LIKE)
3. `link_memory_to_code` → `data_server.py:120` (`WHERE content LIKE ?` to find rows to tag-link)

All three move to `memories_fts MATCH ?` with LIKE fallback. Phase 0 exit criteria
(§8) requires a regression test per caller.

**Schema (pinned, was B4):** standalone FTS5 table + three `AFTER` triggers
(external-content mode was tried first but returned zero matches on this sqlite
build; standalone table with explicit triggers is verified working):
```sql
CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(content, tags);
CREATE TRIGGER IF NOT EXISTS memories_fts_ai AFTER INSERT ON memories BEGIN
  INSERT INTO memories_fts(rowid, content, tags) VALUES (new.id, new.content, new.tags);
END;
CREATE TRIGGER IF NOT EXISTS memories_fts_ad AFTER DELETE ON memories BEGIN
  DELETE FROM memories_fts WHERE rowid = old.id;
END;
CREATE TRIGGER IF NOT EXISTS memories_fts_au AFTER UPDATE ON memories BEGIN
  DELETE FROM memories_fts WHERE rowid = old.id;
  INSERT INTO memories_fts(rowid, content, tags) VALUES (new.id, new.content, new.tags);
  UPDATE memories SET updated_at = CURRENT_TIMESTAMP WHERE id = new.id AND updated_at = old.updated_at;
END;
```
The `AFTER UPDATE` trigger is the combined FTS-sync + `updated_at` trigger. The
`AND updated_at = old.updated_at` guard prevents infinite recursion: the inner
UPDATE fires this trigger again, but `updated_at` no longer equals `old.updated_at`,
so the guard fails and recursion stops. This is the standard SQLite pattern.

**Backfill:** on first init after FTS5 creation, if `memories_fts` is empty but `memories`
is not, run `INSERT INTO memories_fts(memories_fts) VALUES ('rebuild')` (external-content
rebuild reads the base table).

**MATCH query build:** tokenize the user query on whitespace, strip `"` from each token,
wrap each as a quoted phrase, join with ` AND `. If the result is empty (only punctuation),
skip FTS and use LIKE. If FTS returns zero rows, fall back to LIKE.

**WAL mode + busy_timeout (was my-review #10):** P0 init also sets
`PRAGMA journal_mode=WAL` and `PRAGMA busy_timeout=5000` so concurrent writes from five
agent configs don't hit "database is locked".

---

## 5. Data model additions (all additive — no schema migration of existing rows)

| Table | Columns | Purpose |
|---|---|---|
| `memories` (existing) | unchanged | facts / decisions / rules |
| `memories_fts` (new, P0) | content, tags (FTS5 external-content over `memories`) | ranked search |
| `user_prefs` (new, P1) | key, value, confidence, source, updated_at | structured profile |
| `outcomes` (new, P2) | id, ts, tag, subject, outcome, pnl_local, ticker, entry_price, exit_price, run_id, symbol, session, verdict, metadata, archived | outcome ledger |
| `process_queue` (new, P3) | id, type, payload, status, created_at, approved_at | staged skill proposals |

`type ∈ {skill_proposal}` only. `process_queue` is skill-proposal-only — outcomes are not
staged here (resolved in §4.2). A `process_queue` row is only visible to the user's approval
flow; it is never injected into recall automatically.

---

## 6. Consent and safety rules (non-negotiable)

1. **No autonomous writes beyond consent.** `capture_outcome` writes to `outcomes` on call;
   the call itself is the consent (model only calls it when the user asked), and the return
   text is the confirmation surface — same pattern as `link_memory_to_code`. `propose_skill`
   inserts into `process_queue` (status='proposed') and never writes a file. Profile seeding
   requires `seed_profile.py --apply` (default is dry-run).
2. **No stored PnL auto-surfaces.** Raw `outcomes.pnl_local` is returned only with
   `recap_outcomes(verbose=True)`; aggregate recaps default to counts; `query_memory`
   outcome projection is counts only.
3. **No feedback loops from agent-authored rows.** Skill proposals are derived from outcome
   rows + user-approved `memories` only — never from other skill proposals.
4. **The store stays readable.** All new tables coexist with `memories`; any existing client
   (recall.py, query_memory) continues to work untouched against the original table.
5. **No interpretation drift.** `user_prefs` values are short, literal, and gated by
   `confidence`; a model must not infer broad preferences from a single row with
   `confidence < 0.6`.
6. **ADR-002 honored.** `outcomes` carries `ticker`, `entry_price`, `exit_price` so any
   cross-session/cross-ticker comparison normalizes to price-percentage, not absolute PnL.

---

## 7. Integration points

| Surface | Change |
|---|---|
| `mcp/data_server.py:SemanticMemory._init_db` | **single schema owner (B1)** — all DDL lives here; `memory_db.py` imports and calls it. P0: add FTS5 table + 4 triggers + WAL/busy_timeout. P1-P3: add `user_prefs`/`outcomes`/`process_queue` DDL. |
| `mcp/data_server.py:SemanticMemory.query` | port to `memories_fts MATCH` with LIKE fallback (P0). Strip `linked_file:` prefix when picking display topic (B3). |
| `mcp/data_server.py:link_memory_to_code` | port `WHERE content LIKE ?` to `memories_fts MATCH ?` with LIKE fallback (P0). |
| `context_manager/scripts/memory_db.py` | **delete duplicate `CREATE TABLE` (B1)**; import schema from `SemanticMemory._init_db` (or a shared `store_schema.py`); `search_memories` → FTS5+LIKE fallback. |
| `context_manager/scripts/recall.py` | FTS5-backed query, identical CLI |
| `context_manager/scripts/seed_profile.py` (new, P1) | curated seed list; `--apply` writes `user_prefs`; dry-run default |
| `scripts/skill_writer.py` (new, P3) | the only writer that persists into `.agent/skills/` (convention, not filesystem gate) |
| `.agent/skills/context_manager/SKILL.md` | document new tables + the two new CLIs (`seed_profile.py`, `skill_writer.py`) |
| `.github/copilot-instructions.md` | add one line: consult `USER.md` when user preferences are relevant to the task |
| `docs/README.md` | update "Second Brain" entry to mention `USER.md` + outcomes (one line) |

**MCP config verification (was H2):** Phase 1 exit criteria includes verifying all 5 agent
configs still resolve `nq-data-bridge` (configs live outside the repo: `~/.gemini/...`,
`~/.claude/settings.json`, `~/.config/opencode/...`, `AppData\Roaming\Code\User\mcp.json`,
`~/.continue/config.yaml`). Drift here silently breaks every new tool.

**Concurrency (was my-review #10):** `PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000`
set in the single schema-owner init, so concurrent MCP calls from multiple agents don't
lock-corrupt the store.

---

## 8. Phased roadmap

| Phase | Scope | Exit criteria |
|---|---|---|
| **0** | FTS5 migration of `memories` + schema unification + WAL | (a) `recall.py --query` multi-word ranked search works; (b) `query_memory` and `link_memory_to_code` ported to FTS5+LIKE fallback; (c) INSERT/UPDATE/DELETE keep `memories_fts` in sync (trigger test); (d) `updated_at` set on UPDATE; (e) regression test per caller; (f) single schema owner (`memory_db.py` no longer defines its own DDL); (g) WAL + busy_timeout set |
| **1** | `user_prefs` + seeded `USER.md` | (a) profile rendered to `.agent/USER.md`; (b) every seed row user-approved via `seed_profile.py --apply`; (c) `query_memory` prepends profile rows for preference-keyword matches; (d) verify all 5 agent configs still resolve `nq-data-bridge` |
| **2** | Outcome capture + recap | (a) `capture_outcome` writes to `outcomes` and returns confirmation; (b) `recap_outcomes` honors period/verbose; (c) aggregate never leaks raw PnL unless verbose; (d) `query_memory` outcome projection is counts-only; (e) soft-delete + prune path exists |
| **3** | Skill-write gate | (a) `propose_skill` requires ≥3 distinct-win `subject` + zero loss in 30d window; (b) dedupes against `_skill_names.txt` + SKILL.md descriptions (substring match); (c) only `skill_writer.py` writes `.agent/skills/`; (d) draft stored in `process_queue` |
| **4** | (Optional) phase-adaptive review | if **P2** aggregates show >2× loss-rate in a tag, surface a one-line "review this tag" recommendation in `recap_outcomes` |

**Test plan (was H3):** each phase ships with a `tests/` script (or inline `if __name__`
smoke block) that verifies its exit criteria. Phase 0 at minimum: (a) regression test that
`recall.py --query "nt8 order change"` returns the same rows pre/post FTS5, (b) trigger
sync test (insert → search hits, update → search hits new content, delete → search misses),
(c) `query_memory` and `link_memory_to_code` resolve after migration.

---

## 9. Constraints honored (repo guardrails)

- **Zero-loop / ADR-017:** the constraint applies to **Python data-engineering/strategy
  code paths**. Any Python-side post-processing of outcome rows must be vectorized
  (NumPy/Pandas) or avoided. SQL `GROUP BY` aggregation is preferred and satisfies the
  constraint (SQL is the engine, not a Python loop). MCP tools stay stdlib + sqlite3.
- **ADR-002:** `outcomes.pnl_local` is local-currency absolute, but the table also stores
  `ticker`, `entry_price`, `exit_price` so any cross-session/cross-ticker comparison
  normalizes to price-percentage. Raw PnL is never surfaced in aggregates.
- **Startup weight (the real constraint behind my-review #6):** all new MCP tools stay
  stdlib + sqlite3 only, matching the lazy-import refactor; pandas/profiler remain
  function-scoped in the data tools. No new top-level imports in `data_server.py`.
- **Store consolidation:** nothing re-introduces a second `memory.db`; `mcp/memory.db`
  stays deleted.
- **`skill_writer.py` is a convention:** not a filesystem lock, git hook, or permission
  boundary. The safety rail is dedupe + human approval + single named CLI.

---

## 10. Review log

This rev 2 consolidates two critical reviews (2026-08-10):

**Review A (blocking, from the assistant's own pass):**
- capture_outcome consent contradiction → resolved §4.2 (writes directly, consent via
  tool-return, like `link_memory_to_code`).
- diagram/table naming (`skill_writes` vs `process_queue`) → unified to `process_queue`.
- `_memory_db.py` vs `memory_db.py` path → corrected to `memory_db.py`.
- FTS5 ≠ LIKE semantics → called out in §4.4 as accepted behavior change + LIKE fallback.
- `query_memory` "prefers profile rows" undefined → §4.1 confidence formula + §8 P1 exit
  criterion (c).
- `propose_skill` "distinct" / "interleaved" undefined → pinned in §4.3 threshold.
- semantic dedupe overpromised → §4.3 step 4 scoped to keyword/substring.
- `outcomes` can't honor ADR-002 → §5 schema gains `ticker`/`entry_price`/`exit_price`.
- no WAL/busy_timeout → §4.4 + §7.
- `skill_writer.py` "only writer" presented as hard constraint → §4.3 + §9 as convention.
- scope (4 components, zero usage data) → §8 phases are sequential; P0 has standalone value.
- Phase 4 references P1 → corrected to P2.
- seeding = hand-curation → §4.1 explicit.

**Review B (verified against current tree):**
- B1 two divergent `_init_db` → §7 single schema owner, §8 P0 exit (f).
- B2 three LIKE callers, not one → §4.4 + §8 P0 exit (b).
- B3 `query_memory` display topic corrupts on `linked_file:` tags → §7 strip prefix.
- B4 trigger direction + dead `updated_at` → §4.4 four triggers pinned.
- S1 confidence formula → §4.1 pinned.
- S2 `propose_skill` distinctness → §4.3 pinned.
- S3 `_skill_names.txt` "does not exist" → **corrected: it exists, 272 entries** (§2).
- S4 `outcomes.metadata` unindexed → §5 real columns.
- S5 no expiry → §4.2 soft-delete + prune.
- S6 ADR-017 miscited → §9 corrected.
- H1 stale arithmetic → §2 dropped breakdown, kept verified total.
- H2 MCP config drift → §8 P1 exit (d).
- H3 no test plan → §8 test plan row.
- H4 doc untracked → header note: commit before implementation.

**Review C (agent-loop adversarial review, 2026-08-10):**
Run via `python -m scripts.agent_loop --mode review` with GLM-5.2 (REJECT) +
DeepSeek-V4-Pro (REVISE) + Kimi-K3 arbiter. Findings fixed:
- Timestamp format: `.isoformat()` → `.strftime('%Y-%m-%d %H:%M:%S')` (4 sites) —
  was silently excluding all outcomes from time-window queries (string comparison
  `T` > space in ISO format vs CURRENT_TIMESTAMP).
- `updated_at` trigger: merged into the FTS `AFTER UPDATE` trigger with
  `AND updated_at = old.updated_at` recursion guard (was a no-op under
  `recursive_triggers=OFF`).
- `infer_verdict`: word-boundary regex instead of bare substring (was matching
  `"be"` in `"able"`, `"hit"` in `"this"`). Added word-stem variants (`stopped`,
  `scratched`, `stoploss`).
- `link_memory_to_code`: now uses `linked_file:` prefix consistent with `add_memory`.
- `query_memory` outcome projection: handles `NULL` `win_rate_pct`.
- `seed_profile.py`: fixed typo `"20-00"` → `"20:00"`.
- `add_memory`: restored `print()` for CLI feedback.
- `search_memories`: removed redundant `ensure_schema` per-query call.
- FTS5: switched from external-content to standalone table (external-content
  returned zero MATCH results on this sqlite build; standalone verified working).
  §4.4 DDL updated to match implementation.

**Review findings dismissed (wrong assumptions):**
- "Existing 184 rows have old schema with `topic`/`metadata` columns" — wrong;
  the DB was already migrated in the earlier consolidation session. The `memories`
  table has `content`/`tags` columns (verified by smoke test).
- "External-content FTS5 required" — external-content was tried first but returned
  zero MATCH results on this sqlite 3.49.1 build. Standalone FTS5 with explicit
  triggers is verified working (184 rows indexed, bm25 ranked, trigger sync tested).