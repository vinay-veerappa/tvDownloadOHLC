---
name: compact-context
description: Strategic conversation context compaction and state checkpointing. Compresses active conversation history into a structured checkpoint, records persistent decisions to memory DB, and produces a lean handoff. Use when the user types /compact, asks to compact or compress context, requests a session checkpoint, or when conversation context is bloated.
applyTo: "**"
---

# Compact Context & Checkpoint Protocol

This skill executes a deterministic context compaction routine. It distills the active conversation history into an actionable state checkpoint, writes persistent learnings to memory, and produces a lean handoff so work can continue with minimal token overhead and zero context rot.

## When to Trigger
* User explicitly types `/compact`, `/checkpoint`, or asks to "compact context", "summarize session", or "clean context".
* After completing a major milestone or multi-step plan before embarking on the next task.
* When working memory is cluttered with large backtest logs, compiler traces, or raw data outputs.

---

## Compaction Execution Steps

### 1. State & History Audit
Quickly scan the current conversation history and extract:
1. **Primary Goal / Active Objective**: What problem was being solved?
2. **Completed Actions**: Key implementations, refactors, tests, or backtests completed in this session.
3. **Modified & Created Files**: Exact filepaths that were changed or created.
4. **Architectural & Technical Decisions**: Key choices made (e.g. models, schemas, indicators, rules).
5. **Immediate Pending Next Steps**: What remains to be done.

---

### 2. Generate Context Checkpoint Artifact
Write or overwrite the context checkpoint markdown file at:
`c:\Users\vinay\tvDownloadOHLC\.agent\context_checkpoint.md`

Structure of `context_checkpoint.md`:
```markdown
# Context Checkpoint: [Brief Feature / Task Name]
*Timestamp: [Current ISO Timestamp]*

## 1. Executive Summary
[1-2 sentences on what was achieved and current status]

## 2. Key Files & State
- `path/to/modified_file.py`: [Summary of changes]
- `path/to/new_file.pine`: [Summary of changes]

## 3. Critical Decisions & Invariants
- [Decision 1]
- [Decision 2]

## 4. Current Blockers & Unresolved Items
- [None / Item 1]

## 5. Next Actions
1. [Next immediate step]
2. [Follow-up step]
```

---

### 3. Persist Long-Term Knowledge (Context Manager)
If any permanent user preferences, coding patterns, or architectural rules were established during the session, store them in the persistent SQLite memory:

```bash
python .agent/skills/context_manager/scripts/remember.py --category "architecture" --content "[Key technical finding/decision]" --tags "checkpoint,context"
```

---

### 4. Render the Lean User Handoff
Output a clean, concise response to the user:
- State that context has been successfully compacted and checkpointed to [`.agent/context_checkpoint.md`](file:///c:/Users/vinay/tvDownloadOHLC/.agent/context_checkpoint.md).
- Display a 3-4 bullet summary:
  - **Completed So Far**
  - **Active Files**
  - **Immediate Next Step**
- Remind the user: *"You can either continue directly from here with clean focus, or start a new conversation and mention `@context_checkpoint.md` for a 100% clean token slate."*
